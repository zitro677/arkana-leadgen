# Arkana Lead Gen con Hermes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pipeline diario que scrapea negocios en Google Maps (Apify), los califica con Hermes/openai-codex, y entrega los leads a Google Sheets (skill google-workspace) + Top-5 a Telegram.

**Architecture:** Enfoque B — Python orquesta la parte determinista (scrape Apify, dedupe, filtrado, backup) y llama a la API local de Hermes (OpenAI-compatible, `localhost:8642`) para (a) calificar cada lead y (b) escribir en Sheets. Telegram se envía directo vía Bot API reutilizando las credenciales ya configuradas.

**Tech Stack:** Python 3 (`requests`, `python-dotenv`, `pytest`), Apify Google Maps actor (`compass~crawler-google-places`), Hermes local API, skills `arkana_lead_gen` + `google-workspace`.

## Global Constraints

- Todo corre en el VPS como `root`. Proyecto en `/root/arkana_leadgen/`.
- Hermes ya está instalado y su gateway corre como `hermes-gateway.service`.
- Python: usar venv en `/root/arkana_leadgen/.venv`.
- v1 **sin reviews** de Apify (`includeReviews=False`). Solo 3 señales: `no_website` (+30), `no_whatsapp_bot` (+25), `no_booking_system` (+15).
- Umbrales: score ≥ 55 → `alta`, 30–54 → `media`, < 30 → `baja`. `MIN_SCORE=55` para incluir en Sheets.
- Primera corrida real: solo **Bogotá** (8 categorías), `MAX_BATCH=30`.
- Cron diario **08:00 America/Bogota**.
- **No** usar `ANTHROPIC_API_KEY` ni `credentials.json`.
- Cada archivo Python una responsabilidad: `lead_gen.py` (orquestación), `hermes_client.py` (integración Hermes), `notify.py` (Telegram).
- Los comandos se ejecutan en el VPS por SSH (el usuario los pega).

---

## File Structure

```
/root/arkana_leadgen/
├── lead_gen.py          # orquestador: scrape + dedupe + filter + backup + entrypoint CLI
├── hermes_client.py     # llamadas a la API local de Hermes: qualify_lead, write_leads_to_sheet
├── notify.py            # send_telegram (Bot API directo)
├── tests/
│   ├── test_hermes_client.py   # unit: _extract_json
│   └── test_lead_gen.py        # unit: filter_qualified, lead_key, dedupe
├── requirements.txt
├── .env                 # config (no se commitea)
├── .gitignore
└── seen_leads.json      # store de dedupe (runtime, no se commitea)

/root/.hermes/skills/arkana_lead_gen/
├── SKILL.md
└── skill-card.md
```

---

### Task 1: Activar y verificar la API local de Hermes

**Files:**
- Modify: `/root/.hermes/.env` (añadir 2 líneas)

**Interfaces:**
- Produces: API HTTP en `http://127.0.0.1:8642/v1` autenticada con `API_SERVER_KEY`.

- [ ] **Step 1: Generar una clave secreta para la API**

Run:
```bash
openssl rand -hex 24
```
Expected: imprime una cadena hex de 48 chars (guárdala; será `HERMES_API_KEY`).

- [ ] **Step 2: Añadir la config de la API al `.env` de Hermes**

Run (reemplaza `PEGA_LA_CLAVE` por la del paso 1):
```bash
cat >> /root/.hermes/.env <<'EOF'
API_SERVER_ENABLED=true
API_SERVER_KEY=PEGA_LA_CLAVE
EOF
```

- [ ] **Step 3: Reiniciar el gateway**

Run:
```bash
systemctl restart hermes-gateway
sleep 5
systemctl is-active hermes-gateway
```
Expected: `active`

- [ ] **Step 4: Verificar que la API responde y ver el nombre del modelo**

Run (reemplaza `PEGA_LA_CLAVE`):
```bash
curl -s http://127.0.0.1:8642/v1/models -H "Authorization: Bearer PEGA_LA_CLAVE"
```
Expected: JSON con una lista de modelos. **Anota el `id`** (será `HERMES_MODEL`; suele ser `hermes-agent` o el nombre del perfil).

- [ ] **Step 5: Verificar una completion mínima**

Run (reemplaza `PEGA_LA_CLAVE` y `MODELO`):
```bash
curl -s http://127.0.0.1:8642/v1/chat/completions \
  -H "Authorization: Bearer PEGA_LA_CLAVE" \
  -H "Content-Type: application/json" \
  -d '{"model":"MODELO","messages":[{"role":"user","content":"Responde solo: OK"}],"max_tokens":10}'
```
Expected: JSON con `choices[0].message.content` que contiene `OK`.

---

### Task 2: Autenticar la skill `google-workspace` y crear la hoja destino

**Files:** (ninguno de código; setup en Hermes + Google)

**Interfaces:**
- Produces: `GOOGLE_SHEETS_ID` (id de la hoja destino) + permiso OAuth de Hermes para escribir en ella.

- [ ] **Step 1: Crear la hoja de Google Sheets**

En tu navegador: crea una hoja nueva en https://sheets.google.com (con la **misma cuenta Google** que usarás para el OAuth de Hermes). Nómbrala "Arkana Leads". Copia el ID de la URL:
`https://docs.google.com/spreadsheets/d/<ESTE_ES_EL_ID>/edit`

- [ ] **Step 2: Iniciar el login OAuth de google-workspace en Hermes**

Run en el VPS:
```bash
hermes setup tools
```
Navega a la sección de Google Workspace / google-workspace y sigue el flujo OAuth (te dará una URL para abrir en tu navegador y autorizar). Autoriza con la cuenta dueña de la hoja.

- [ ] **Step 3: Verificar que Hermes puede leer la hoja**

Run (reemplaza claves/modelo/ID):
```bash
curl -s http://127.0.0.1:8642/v1/chat/completions \
  -H "Authorization: Bearer PEGA_LA_CLAVE" \
  -H "Content-Type: application/json" \
  -d '{"model":"MODELO","messages":[{"role":"user","content":"Usa google-workspace para leer la celda A1 de la hoja con id ID_DE_LA_HOJA, pestaña leads. Si la pestaña no existe dilo. Responde brevemente."}],"max_tokens":200}'
```
Expected: respuesta indicando que leyó la hoja (o que la pestaña `leads` no existe todavía — ambas son OK; confirma que el OAuth funciona).

---

### Task 3: Crear la skill `arkana_lead_gen` en Hermes

**Files:**
- Create: `/root/.hermes/skills/arkana_lead_gen/SKILL.md`
- Create: `/root/.hermes/skills/arkana_lead_gen/skill-card.md`

**Interfaces:**
- Produces: skill `arkana_lead_gen` cargable por Hermes (rúbrica de calificación).

- [ ] **Step 1: Crear el directorio de la skill**

Run:
```bash
mkdir -p /root/.hermes/skills/arkana_lead_gen
```

- [ ] **Step 2: Escribir `SKILL.md`**

Run:
```bash
cat > /root/.hermes/skills/arkana_lead_gen/SKILL.md <<'EOF'
---
name: arkana_lead_gen
description: Califica negocios locales por su madurez para automatización con IA (señales + scoring) y devuelve JSON estructurado para Arkana Tech.
version: 1.0.0
platforms: [linux]
metadata:
  hermes:
    category: sales
    tags: [leads, sales, qualification, arkana]
---

# SKILL: arkana_lead_gen

## Purpose
Califica negocios locales (previamente scrapeados de Google Maps) por su
disposición a automatización con IA, y devuelve JSON estructurado.

## CATEGORIES
- restaurantes
- inmobiliarias
- administracion_conjuntos
- talleres_mecanicos
- clinicas_dentales
- firmas_juridicas
- car_detailing
- landscaping_irrigation

## Qualification Signals (v1 — solo estas 3 son evaluables sin reviews)
1. no_website: campo website vacío o null
2. no_whatsapp_bot: la descripción GMB no menciona chatbot/WhatsApp/bot
3. no_booking_system: no hay URL de reserva/booking visible

(Las señales poor_review_response y outdated_hours son v2; NO sumarlas en v1.)

## Output Schema (devolver SOLO este JSON, sin markdown)
{
  "empresa": string,
  "categoria": string,
  "ciudad": string,
  "telefono": string,
  "website": string | null,
  "google_maps_url": string,
  "rating": float,
  "total_reviews": int,
  "señales": [string],
  "score": int,
  "pitch_angle": string,
  "prioridad": "alta" | "media" | "baja"
}

## Scoring Logic (v1)
- no_website: +30
- no_whatsapp_bot: +25
- no_booking_system: +15
Score >= 55 -> alta | 30-54 -> media | <30 -> baja

## pitch_angle
Frase corta y específica del dolor detectado + servicio Arkana sugerido
(ej. "Sin web con 80 reseñas — bot de reservas por WhatsApp 24/7").
EOF
```

- [ ] **Step 3: Escribir `skill-card.md`**

Run:
```bash
cat > /root/.hermes/skills/arkana_lead_gen/skill-card.md <<'EOF'
# arkana_lead_gen
Califica negocios locales por madurez de automatización IA. Devuelve JSON
con score (0-100), señales y pitch para Arkana Tech.
EOF
```

- [ ] **Step 4: Reiniciar gateway y verificar que la skill carga**

Run:
```bash
systemctl restart hermes-gateway
hermes skills list | grep -i arkana
```
Expected: una fila con `arkana_lead_gen ... local ... enabled`.

---

### Task 4: Scaffold del proyecto Python en el VPS

**Files:**
- Create: `/root/arkana_leadgen/requirements.txt`
- Create: `/root/arkana_leadgen/.gitignore`
- Create: `/root/arkana_leadgen/.env`

**Interfaces:**
- Produces: venv con deps + `.env` con config; repo git inicializado.

- [ ] **Step 1: Crear el directorio y el venv**

Run:
```bash
mkdir -p /root/arkana_leadgen/tests
cd /root/arkana_leadgen && python3 -m venv .venv && .venv/bin/pip install --upgrade pip
```
Expected: pip actualizado sin errores.

- [ ] **Step 2: Crear `requirements.txt` e instalar**

Run:
```bash
cat > /root/arkana_leadgen/requirements.txt <<'EOF'
requests>=2.31
python-dotenv>=1.0
pytest>=8.0
EOF
/root/arkana_leadgen/.venv/bin/pip install -r /root/arkana_leadgen/requirements.txt
```
Expected: instala requests, python-dotenv, pytest.

- [ ] **Step 3: Crear `.gitignore`**

Run:
```bash
cat > /root/arkana_leadgen/.gitignore <<'EOF'
.venv/
.env
seen_leads.json
leads_*.json
leads_*.csv
__pycache__/
*.pyc
EOF
```

- [ ] **Step 4: Crear `.env`** (reemplaza los valores reales)

Run:
```bash
cat > /root/arkana_leadgen/.env <<'EOF'
APIFY_KEY=PEGA_TU_APIFY_KEY
HERMES_API_URL=http://127.0.0.1:8642/v1
HERMES_API_KEY=PEGA_LA_CLAVE_DE_TASK1
HERMES_MODEL=PEGA_EL_MODELO_DE_TASK1
GOOGLE_SHEETS_ID=PEGA_EL_ID_DE_TASK2
SHEET_TAB=leads
MIN_SCORE=55
MAX_BATCH=30
TELEGRAM_TOKEN=PEGA_TOKEN_DEL_BOT
TELEGRAM_CHAT_ID=PEGA_TU_CHAT_ID
EOF
```
Nota: el `TELEGRAM_TOKEN` es el mismo que usa Hermes; está en `/root/.hermes/.env` (búscalo con `grep -i telegram /root/.hermes/.env`).

- [ ] **Step 5: Inicializar git y primer commit**

Run:
```bash
cd /root/arkana_leadgen && git init && git add requirements.txt .gitignore && git -c user.email=arkana@vps -c user.name=arkana commit -m "chore: scaffold arkana_leadgen project"
```
Expected: commit creado (`.env` excluido por `.gitignore`).

---

### Task 5: `hermes_client.py` — calificación vía Hermes

**Files:**
- Create: `/root/arkana_leadgen/hermes_client.py`
- Test: `/root/arkana_leadgen/tests/test_hermes_client.py`

**Interfaces:**
- Consumes: env `HERMES_API_URL`, `HERMES_API_KEY`, `HERMES_MODEL`.
- Produces:
  - `qualify_lead(lead: dict, ciudad: str, categoria: str, retries: int = 1) -> dict | None`
  - `write_leads_to_sheet(leads: list[dict], sheet_id: str, tab: str = "leads") -> bool`
  - `_extract_json(text: str) -> dict` (helper, testeable)

- [ ] **Step 1: Escribir el test que falla (parseo de JSON)**

Run:
```bash
cat > /root/arkana_leadgen/tests/test_hermes_client.py <<'EOF'
import hermes_client as hc

def test_extract_json_plain():
    assert hc._extract_json('{"score": 55}') == {"score": 55}

def test_extract_json_with_markdown_fences():
    txt = '```json\n{"score": 30, "prioridad": "media"}\n```'
    assert hc._extract_json(txt) == {"score": 30, "prioridad": "media"}

def test_extract_json_with_surrounding_text():
    txt = 'Aquí tienes el lead:\n{"empresa": "X"}\nGracias.'
    assert hc._extract_json(txt) == {"empresa": "X"}
EOF
```

- [ ] **Step 2: Ejecutar el test para ver que falla**

Run:
```bash
cd /root/arkana_leadgen && .venv/bin/python -m pytest tests/test_hermes_client.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'hermes_client'`.

- [ ] **Step 3: Escribir `hermes_client.py`**

Run:
```bash
cat > /root/arkana_leadgen/hermes_client.py <<'EOF'
"""Cliente para la API local de Hermes (OpenAI-compatible) — Arkana Lead Gen."""
import os
import json
import time
import subprocess
import requests

HERMES_API_URL = os.getenv("HERMES_API_URL", "http://127.0.0.1:8642/v1")
HERMES_API_KEY = os.getenv("HERMES_API_KEY", "")
HERMES_MODEL   = os.getenv("HERMES_MODEL", "hermes-agent")

_HEADERS = {
    "Authorization": f"Bearer {HERMES_API_KEY}",
    "Content-Type": "application/json",
}


def _chat(messages, max_tokens=800, timeout=120):
    """Llamada a /chat/completions. Devuelve el texto de la respuesta."""
    payload = {"model": HERMES_MODEL, "messages": messages, "max_tokens": max_tokens}
    resp = requests.post(
        f"{HERMES_API_URL}/chat/completions",
        headers=_HEADERS, json=payload, timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _extract_json(text):
    """Limpia markdown y parsea el primer objeto JSON del texto."""
    text = text.strip().replace("```json", "").replace("```", "").strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON en respuesta: {text[:200]}")
    return json.loads(text[start:end + 1])


QUALIFY_PROMPT = """Eres el analista de ventas de Arkana Tech. Aplica la rúbrica de la skill `arkana_lead_gen`.
Califica este negocio y devuelve SOLO JSON válido (sin markdown, sin texto extra, NO uses herramientas).

Negocio:
- Nombre: {nombre}
- Teléfono: {telefono}
- Website: {website}
- Rating: {rating}
- Total reseñas: {reviews}
- Ciudad: {ciudad}
- Categoría: {categoria}
- Descripción GMB: {descripcion}

Scoring v1 (solo estas 3 señales):
- Sin website (null/vacío): +30  -> señal "no_website"
- Descripción sin WhatsApp/chatbot/bot: +25 -> señal "no_whatsapp_bot"
- Sin URL de reserva/booking visible: +15 -> señal "no_booking_system"
Prioridad: score>=55 -> alta, 30-54 -> media, <30 -> baja.

Devuelve exactamente este esquema (rellena los valores):
{{"empresa":"","categoria":"{categoria}","ciudad":"{ciudad}","telefono":"","website":null,"google_maps_url":"","rating":0.0,"total_reviews":0,"señales":[],"score":0,"pitch_angle":"","prioridad":"baja"}}"""


def qualify_lead(lead, ciudad, categoria, retries=1):
    """Califica un lead vía Hermes. Devuelve dict del esquema o None si falla."""
    prompt = QUALIFY_PROMPT.format(
        nombre=lead.get("title", "N/A"),
        telefono=lead.get("phone", "N/A"),
        website=lead.get("website") or "ninguno",
        rating=lead.get("totalScore", "N/A"),
        reviews=lead.get("reviewsCount", 0),
        ciudad=ciudad, categoria=categoria,
        descripcion=(lead.get("description") or "")[:300],
    )
    for attempt in range(retries + 1):
        try:
            text = _chat([{"role": "user", "content": prompt}])
            data = _extract_json(text)
            data.setdefault("google_maps_url", lead.get("url", ""))
            data.setdefault("rating", lead.get("totalScore", 0))
            data.setdefault("total_reviews", lead.get("reviewsCount", 0))
            return data
        except Exception as e:
            if attempt < retries:
                time.sleep(1.5)
                continue
            print(f"  !  qualify_lead falló para '{lead.get('title')}': {e}")
            return None


# Script de la skill google-workspace (usa el token OAuth ya autenticado).
GWS_GAPI = os.getenv(
    "GWS_GAPI",
    "/root/.hermes/skills/productivity/google-workspace/scripts/google_api.py",
)


def write_leads_to_sheet(leads, sheet_id, tab="leads"):
    """Añade filas a Google Sheets llamando DIRECTO al script google_api.py.
    Determinista, sin agente, sin gate de aprobación. Devuelve True/False."""
    if not leads:
        return True
    rows = [[
        l.get("empresa", ""), l.get("ciudad", ""), l.get("categoria", ""),
        l.get("telefono", ""), l.get("website") or "", l.get("rating", ""),
        l.get("total_reviews", ""), l.get("score", ""), l.get("prioridad", ""),
        ", ".join(l.get("señales", [])), l.get("pitch_angle", ""),
        l.get("google_maps_url", ""),
    ] for l in leads]
    values = json.dumps(rows, ensure_ascii=False)
    try:
        r = subprocess.run(
            ["python3", GWS_GAPI, "sheets", "append", sheet_id, f"{tab}!A1",
             "--values", values],
            capture_output=True, text=True, timeout=120,
        )
        if r.returncode != 0:
            print(f"  X  Sheets append falló: {r.stderr.strip()[:200]}")
            return False
        print(f"  OK Sheets: {r.stdout.strip()[:80]}")
        return True
    except Exception as e:
        print(f"  X  Sheets append error: {e}")
        return False
EOF
```

- [ ] **Step 4: Ejecutar los tests para verificar que pasan**

Run:
```bash
cd /root/arkana_leadgen && .venv/bin/python -m pytest tests/test_hermes_client.py -v
```
Expected: PASS (3 passed).

- [ ] **Step 5: Verificación de integración — calificar 1 lead real**

Run:
```bash
cd /root/arkana_leadgen && .venv/bin/python -c "
from dotenv import load_dotenv; load_dotenv()
import importlib, hermes_client; importlib.reload(hermes_client)
from hermes_client import qualify_lead
lead = {'title':'Pizzería Demo','phone':'+57 300 1112233','website':None,'totalScore':4.1,'reviewsCount':87,'url':'https://maps.google.com/?cid=1','description':'Pizza artesanal'}
import json; print(json.dumps(qualify_lead(lead,'Bogotá Colombia','restaurantes'), ensure_ascii=False, indent=2))
"
```
Expected: imprime un JSON con `score` (debería ser ~55, señales `no_website` + `no_whatsapp_bot`) y `prioridad: alta`.

- [ ] **Step 6: Commit**

Run:
```bash
cd /root/arkana_leadgen && git add hermes_client.py tests/test_hermes_client.py && git -c user.email=arkana@vps -c user.name=arkana commit -m "feat: hermes_client con qualify_lead y write_leads_to_sheet"
```

---

### Task 6: `notify.py` — envío a Telegram

**Files:**
- Create: `/root/arkana_leadgen/notify.py`

**Interfaces:**
- Consumes: env `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID`.
- Produces: `send_telegram(message: str) -> bool`

- [ ] **Step 1: Escribir `notify.py`**

Run:
```bash
cat > /root/arkana_leadgen/notify.py <<'EOF'
"""Envío de notificaciones a Telegram vía Bot API — Arkana Lead Gen."""
import os
import requests

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")


def send_telegram(message):
    """Envía un mensaje Markdown a Telegram. Devuelve True si se entregó."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print(f"\n📱 [Telegram no configurado]\n{message}")
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        r = requests.post(url, json=data, timeout=10)
        r.raise_for_status()
        return True
    except requests.RequestException as e:
        print(f"  !  Telegram error: {e}")
        return False
EOF
```

- [ ] **Step 2: Verificar el envío a Telegram**

Run:
```bash
cd /root/arkana_leadgen && .venv/bin/python -c "
from dotenv import load_dotenv; load_dotenv()
import importlib, notify; importlib.reload(notify)
print('enviado:', notify.send_telegram('*Arkana* — prueba de notify.py ✅'))
"
```
Expected: imprime `enviado: True` y llega el mensaje a tu Telegram.

- [ ] **Step 3: Commit**

Run:
```bash
cd /root/arkana_leadgen && git add notify.py && git -c user.email=arkana@vps -c user.name=arkana commit -m "feat: notify.py envío a Telegram"
```

---

### Task 7: `lead_gen.py` — scrape, dedupe, filtrado y orquestación

**Files:**
- Create: `/root/arkana_leadgen/lead_gen.py`
- Test: `/root/arkana_leadgen/tests/test_lead_gen.py`

**Interfaces:**
- Consumes: `hermes_client.qualify_lead`, `hermes_client.write_leads_to_sheet`, `notify.send_telegram` (Task 6).
- Produces:
  - `scrape_google_maps(query: str, max_results: int) -> list[dict]`
  - `lead_key(raw: dict) -> str`
  - `filter_qualified(qualified: list[dict], min_score: int) -> list[dict]`
  - `load_seen()/save_seen(seen)` (dedupe persistente)
  - `run_pipeline(targets: list[tuple], min_score: int) -> list[dict]`
  - CLI: `--ciudad`, `--categoria`, `--score`, `--test`

- [ ] **Step 1: Escribir los tests que fallan (lógica pura)**

Run:
```bash
cat > /root/arkana_leadgen/tests/test_lead_gen.py <<'EOF'
import lead_gen as lg

def test_filter_qualified_keeps_high_scores():
    leads = [{"score": 55}, {"score": 40}, {"score": 70}]
    out = lg.filter_qualified(leads, min_score=55)
    assert [l["score"] for l in out] == [55, 70]

def test_lead_key_prefers_url():
    assert lg.lead_key({"url": "u1", "phone": "p1"}) == "u1"

def test_lead_key_falls_back_to_phone():
    assert lg.lead_key({"phone": "p1"}) == "p1"

def test_mock_data_shape():
    rows = lg._mock_data("restaurantes Bogotá")
    assert len(rows) >= 1
    assert "title" in rows[0] and "url" in rows[0]
EOF
```

- [ ] **Step 2: Ejecutar para verificar que falla**

Run:
```bash
cd /root/arkana_leadgen && .venv/bin/python -m pytest tests/test_lead_gen.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'lead_gen'`.

- [ ] **Step 3: Escribir `lead_gen.py`**

Run:
```bash
cat > /root/arkana_leadgen/lead_gen.py <<'EOF'
"""Arkana Tech — Lead Gen v1 (Apify scrape -> Hermes qualify -> Sheets/Telegram)."""
import os
import json
import time
import csv
import argparse
from datetime import datetime

import requests
from dotenv import load_dotenv

load_dotenv()

from hermes_client import qualify_lead, write_leads_to_sheet
from notify import send_telegram

APIFY_KEY = os.getenv("APIFY_KEY", "")
SHEETS_ID = os.getenv("GOOGLE_SHEETS_ID", "")
SHEET_TAB = os.getenv("SHEET_TAB", "leads")
MIN_SCORE = int(os.getenv("MIN_SCORE", "55"))
MAX_BATCH = int(os.getenv("MAX_BATCH", "30"))
SEEN_FILE = os.getenv("SEEN_FILE", "seen_leads.json")

TARGETS = [
    ("Bogotá Colombia", "restaurantes",             "restaurantes Bogotá"),
    ("Bogotá Colombia", "inmobiliarias",            "inmobiliarias Bogotá"),
    ("Bogotá Colombia", "administracion_conjuntos", "administración conjuntos residenciales Bogotá"),
    ("Bogotá Colombia", "talleres_mecanicos",       "talleres mecánicos Bogotá"),
    ("Bogotá Colombia", "clinicas_dentales",        "clínicas dentales Bogotá"),
    ("Bogotá Colombia", "firmas_juridicas",         "firmas jurídicas abogados Bogotá"),
    ("Bogotá Colombia", "car_detailing",            "car detailing lavado autos Bogotá"),
    ("Bogotá Colombia", "landscaping_irrigation",   "jardinería riego paisajismo Bogotá"),
]


def scrape_google_maps(query, max_results=MAX_BATCH):
    """Llama al Google Maps Scraper de Apify. v1: sin reviews."""
    if not APIFY_KEY:
        print("  !  APIFY_KEY no configurado — usando datos de prueba")
        return _mock_data(query)
    actor = "compass~crawler-google-places"
    url = f"https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items"
    payload = {
        "searchStringsArray": [query],
        "maxCrawledPlacesPerSearch": max_results,
        "language": "es",
        "includeReviews": False,
        "includeImages": False,
    }
    try:
        r = requests.post(url, json=payload, params={"token": APIFY_KEY}, timeout=180)
        r.raise_for_status()
        return r.json()
    except requests.RequestException as e:
        print(f"  X  Apify error: {e}")
        return []


def _mock_data(query):
    return [{
        "title": f"Negocio Demo #{i} — Bogotá",
        "phone": f"+57 300 000 000{i}",
        "website": None if i % 2 == 0 else f"http://demo{i}.com",
        "totalScore": 4.0,
        "reviewsCount": 10 + i * 7,
        "url": f"https://maps.google.com/?cid=demo{i}",
        "description": "",
    } for i in range(1, 6)]


def lead_key(raw):
    """Clave de dedupe: url de Maps > teléfono > título."""
    return raw.get("url") or raw.get("phone") or raw.get("title", "")


def load_seen():
    try:
        with open(SEEN_FILE, encoding="utf-8") as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def save_seen(seen):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(seen), f, ensure_ascii=False, indent=2)


def filter_qualified(qualified, min_score=MIN_SCORE):
    return [l for l in qualified if l.get("score", 0) >= min_score]


def _backup_local(leads):
    if not leads:
        return
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    with open(f"leads_{stamp}.json", "w", encoding="utf-8") as f:
        json.dump(leads, f, ensure_ascii=False, indent=2)
    cols = ["empresa", "ciudad", "categoria", "telefono", "website", "rating",
            "total_reviews", "score", "prioridad", "pitch_angle", "google_maps_url"]
    with open(f"leads_{stamp}.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(leads)
    print(f"  💾 Backup local: leads_{stamp}.json / .csv")


def _notify(qualified, total_raw):
    hoy = datetime.now().strftime("%d/%m/%Y %H:%M")
    top5 = sorted(qualified, key=lambda x: x.get("score", 0), reverse=True)[:5]
    msg = f"*Arkana Lead Gen — {hoy}*\n"
    msg += f"Scrapeados: {total_raw} | Calificados (>= {MIN_SCORE}): {len(qualified)}\n\n"
    if not top5:
        msg += "_Sin leads nuevos hoy._"
    else:
        msg += "*Top 5:*\n"
        for i, l in enumerate(top5, 1):
            msg += (f"*{i}. {l.get('empresa','N/A')}* — {l.get('categoria','')}\n"
                    f"   {l.get('telefono','N/A')} | score {l.get('score')} "
                    f"({l.get('prioridad','').upper()})\n"
                    f"   {l.get('pitch_angle','')}\n")
    send_telegram(msg)


def run_pipeline(targets, min_score=MIN_SCORE):
    seen = load_seen()
    all_leads = []
    total_raw = 0
    print(f"\n🚀 Arkana Lead Gen v1 — {datetime.now():%Y-%m-%d %H:%M}")
    for ciudad, categoria, query in targets:
        print(f"🔍 {query}")
        raw = scrape_google_maps(query)
        nuevos = [r for r in raw if lead_key(r) not in seen]
        total_raw += len(raw)
        print(f"   -> {len(raw)} negocios ({len(nuevos)} nuevos)")
        for r in nuevos:
            q = qualify_lead(r, ciudad, categoria)
            if q:
                all_leads.append(q)
            seen.add(lead_key(r))
            time.sleep(0.3)
        time.sleep(1)
    save_seen(seen)
    qualified = filter_qualified(all_leads, min_score)
    print(f"\n📊 {total_raw} scrapeados -> {len(qualified)} con score>={min_score}")
    if qualified:
        write_leads_to_sheet(qualified, SHEETS_ID, SHEET_TAB)
    _backup_local(all_leads)
    _notify(qualified, total_raw)
    return qualified


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Arkana Lead Gen v1")
    parser.add_argument("--ciudad",    help="Filtrar por ciudad")
    parser.add_argument("--categoria", help="Filtrar por categoría")
    parser.add_argument("--score", type=int, default=MIN_SCORE, help="Min score")
    parser.add_argument("--test", action="store_true", help="Solo 1 target")
    args = parser.parse_args()

    targets = TARGETS
    if args.ciudad:
        targets = [t for t in targets if args.ciudad.lower() in t[0].lower()]
    if args.categoria:
        targets = [t for t in targets if args.categoria.lower() in t[1].lower()]
    if args.test:
        targets = targets[:1]

    leads = run_pipeline(targets=targets, min_score=args.score)
    print(f"\n✅ Completado — {len(leads)} leads calificados")
EOF
```

- [ ] **Step 4: Ejecutar los tests para verificar que pasan**

Run:
```bash
cd /root/arkana_leadgen && .venv/bin/python -m pytest tests/test_lead_gen.py -v
```
Expected: PASS (4 passed). (`notify` y `hermes_client` ya existen de Tasks 5 y 6, así que el import funciona.)

- [ ] **Step 5: Correr toda la suite de tests**

Run:
```bash
cd /root/arkana_leadgen && .venv/bin/python -m pytest tests/ -v
```
Expected: PASS (7 passed en total).

- [ ] **Step 6: Commit**

Run:
```bash
cd /root/arkana_leadgen && git add lead_gen.py tests/test_lead_gen.py && git -c user.email=arkana@vps -c user.name=arkana commit -m "feat: lead_gen orquestación con scrape, dedupe y filtrado"
```

---

### Task 8: Verificación de escritura en Sheets (integración)

**Files:** (ninguno; valida `write_leads_to_sheet` end-to-end)

**Interfaces:**
- Consumes: `hermes_client.write_leads_to_sheet`, hoja de Task 2.

- [ ] **Step 1: Escribir 2 filas de prueba en la hoja**

Run:
```bash
cd /root/arkana_leadgen && .venv/bin/python -c "
from dotenv import load_dotenv; load_dotenv()
import os, importlib, hermes_client; importlib.reload(hermes_client)
from hermes_client import write_leads_to_sheet
demo = [
 {'empresa':'Test A','ciudad':'Bogotá','categoria':'restaurantes','telefono':'+57 1','website':None,'rating':4.2,'total_reviews':50,'score':55,'prioridad':'alta','señales':['no_website','no_whatsapp_bot'],'pitch_angle':'demo A','google_maps_url':'http://x/a'},
 {'empresa':'Test B','ciudad':'Bogotá','categoria':'talleres_mecanicos','telefono':'+57 2','website':'http://b.co','rating':3.9,'total_reviews':20,'score':40,'prioridad':'media','señales':['no_whatsapp_bot'],'pitch_angle':'demo B','google_maps_url':'http://x/b'},
]
print('ok:', write_leads_to_sheet(demo, os.getenv('GOOGLE_SHEETS_ID'), os.getenv('SHEET_TAB','leads')))
"
```
Expected: imprime `ok: True` y aparecen 2 filas (con encabezados) en la pestaña `leads` de tu hoja. **Verifícalo abriendo la hoja en el navegador.**

- [ ] **Step 2: Borrar las filas de prueba**

Manual: en la hoja, elimina las filas `Test A` / `Test B` (deja los encabezados).

---

### Task 9: Corrida completa de validación (Bogotá)

**Files:** (ninguno; ejecución end-to-end)

- [ ] **Step 1: Corrida de prueba con 1 categoría**

Run:
```bash
cd /root/arkana_leadgen && .venv/bin/python lead_gen.py --ciudad Bogotá --categoria restaurantes
```
Expected: scrapea restaurantes, califica, escribe a Sheets, manda Top-5 a Telegram, deja `leads_*.json/.csv` y actualiza `seen_leads.json`.

- [ ] **Step 2: Verificar idempotencia (dedupe)**

Run de nuevo el mismo comando:
```bash
cd /root/arkana_leadgen && .venv/bin/python lead_gen.py --ciudad Bogotá --categoria restaurantes
```
Expected: dice `(0 nuevos)` o muy pocos — confirma que el dedupe funciona y no re-inserta.

- [ ] **Step 3: Corrida completa de Bogotá (8 categorías)**

Run:
```bash
cd /root/arkana_leadgen && .venv/bin/python lead_gen.py --ciudad Bogotá
```
Expected: procesa las 8 categorías; resumen final con total scrapeado y calificados; leads en Sheets + Telegram.

---

### Task 10: Programar el cron diario

**Files:**
- Create: `/root/arkana_leadgen/run_daily.sh`
- Modify: crontab de root

**Interfaces:**
- Produces: ejecución automática diaria 08:00 America/Bogota.

- [ ] **Step 1: Crear el script wrapper**

Run:
```bash
cat > /root/arkana_leadgen/run_daily.sh <<'EOF'
#!/usr/bin/env bash
cd /root/arkana_leadgen || exit 1
/root/arkana_leadgen/.venv/bin/python lead_gen.py --ciudad Bogotá >> /root/arkana_leadgen/cron.log 2>&1
EOF
chmod +x /root/arkana_leadgen/run_daily.sh
```

- [ ] **Step 2: Probar el wrapper manualmente**

Run:
```bash
/root/arkana_leadgen/run_daily.sh && tail -n 15 /root/arkana_leadgen/cron.log
```
Expected: el log muestra la corrida completa sin errores.

- [ ] **Step 3: Añadir la entrada de cron (08:00 America/Bogota)**

Run:
```bash
( crontab -l 2>/dev/null; echo "CRON_TZ=America/Bogota"; echo "0 8 * * * /root/arkana_leadgen/run_daily.sh" ) | crontab -
crontab -l
```
Expected: el `crontab -l` muestra `CRON_TZ=America/Bogota` y la línea `0 8 * * * /root/arkana_leadgen/run_daily.sh`.

- [ ] **Step 4: Commit final**

Run:
```bash
cd /root/arkana_leadgen && git add run_daily.sh && git -c user.email=arkana@vps -c user.name=arkana commit -m "feat: cron wrapper run_daily.sh (08:00 America/Bogota)"
```

---

## Notas de operación

- **Ver logs del cron:** `tail -f /root/arkana_leadgen/cron.log`
- **Forzar una corrida ya:** `/root/arkana_leadgen/run_daily.sh`
- **Resetear dedupe** (re-procesar todo): `rm /root/arkana_leadgen/seen_leads.json`
- **Añadir Nashville (v2):** descomentar/añadir sus targets en `TARGETS` de `lead_gen.py`.

## Roadmap v2 (fuera de alcance)
- Apify `includeReviews=true` → señal `poor_review_response`.
- Enriquecimiento con Scrapling (web propia del negocio) para `no_booking_system`/`no_whatsapp_bot`.
- Señal `outdated_hours`. Nashville + más ciudades. Reporte semanal agregado.
