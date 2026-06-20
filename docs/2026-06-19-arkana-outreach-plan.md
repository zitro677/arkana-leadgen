# Outreach de propuestas (borradores Gmail) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Comando manual `outreach.py` que lee leads del Google Sheet (email + score≥50), redacta una propuesta personalizada por lead con Hermes, y crea un BORRADOR en Gmail para que el usuario revise y envíe.

**Architecture:** Script independiente del pipeline. Lee la pestaña `leads` vía `google_api.py sheets get`; filtra y deduplica (`drafted.json`); por cada lead Hermes redacta `{asunto, cuerpo}`; se crea el borrador con la API de Gmail (`drafts.create`) reutilizando el token OAuth ya autorizado. No envía.

**Tech Stack:** Python 3 (venv), `requests`, `google-api-python-client` + `google-auth` (Gmail drafts), API local de Hermes, skill google-workspace (token OAuth).

## Global Constraints

- Proyecto en VPS: `/root/arkana_leadgen` (clon de github.com/zitro677/arkana-leadgen). Repo local: `E:\Projects Claude\Hermes-leads`.
- venv: `/root/arkana_leadgen/.venv`. Config en `.env` (ya existe).
- Filtro: leads con `email` no vacío **y** `score >= MIN_SCORE` (env, =50) **y** email no en `drafted.json`.
- Orden de columnas del Sheet (13): empresa, ciudad, categoria, telefono, email, website, rating, total_reviews, score, prioridad, senales, pitch, maps_url.
- Borradores vía Gmail API `users().drafts().create()`. Token: `/root/.hermes/google_token.json`; client secret: `/root/.hermes/google_client_secret.json`.
- NO se envían correos. Cada correo incluye identidad del remitente + línea de baja.
- Idioma: español. Firma: "Arkana Tech — Luis".
- `outreach.py` flags: `--limit N` (default 15), `--to-self`, `--dry-run`.

---

## File Structure

```
/root/arkana_leadgen/
├── sheet_reader.py     # read_leads(): lee la pestaña leads del Sheet -> list[dict]
├── draft_writer.py     # write_proposal(lead) -> {asunto, cuerpo} (Hermes)
├── gmail_client.py     # create_draft(to, subject, body); get_self_email()
├── outreach.py         # orquestador + CLI (filtro, dedupe, bucle)
├── drafted.json        # store local de emails ya drafteados (runtime)
└── tests/
    ├── test_sheet_reader.py
    ├── test_gmail_client.py
    └── test_outreach.py
```

---

### Task 1: `sheet_reader.py` — leer leads del Sheet

**Files:**
- Create: `/root/arkana_leadgen/sheet_reader.py`
- Test: `/root/arkana_leadgen/tests/test_sheet_reader.py`

**Interfaces:**
- Consumes: env `GWS_GAPI`, `GOOGLE_SHEETS_ID`, `SHEET_TAB`.
- Produces:
  - `COLS: list[str]` (13 nombres de campo, en orden)
  - `rows_to_leads(rows: list[list]) -> list[dict]` (salta encabezado)
  - `read_leads() -> list[dict]`

- [ ] **Step 1: Escribir el test que falla**

```python
import sheet_reader as sr

def test_rows_to_leads_skips_header_and_maps():
    rows = [
        ["Empresa", "Ciudad", "Categoria", "Telefono", "Email", "Website",
         "Rating", "Reseñas", "Score", "Prioridad", "Señales", "Pitch", "MapsURL"],
        ["Pizza X", "Bogotá", "restaurantes", "+57 1", "a@x.com", "", "4.2",
         "80", "55", "alta", "no_website", "pitch", "http://m/x"],
    ]
    leads = sr.rows_to_leads(rows)
    assert len(leads) == 1
    assert leads[0]["email"] == "a@x.com"
    assert leads[0]["score"] == "55"
    assert leads[0]["empresa"] == "Pizza X"

def test_rows_to_leads_handles_short_rows():
    rows = [["Empresa"], ["Solo Nombre"]]
    leads = sr.rows_to_leads(rows)
    assert leads[0]["empresa"] == "Solo Nombre"
    assert leads[0]["email"] == ""
```

- [ ] **Step 2: Ejecutar para ver que falla**

Run: `cd /root/arkana_leadgen && .venv/bin/python -m pytest tests/test_sheet_reader.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sheet_reader'`.

- [ ] **Step 3: Escribir `sheet_reader.py`**

```python
"""Lee la pestaña de leads del Google Sheet vía google_api.py."""
import os
import json
import subprocess
from dotenv import load_dotenv

load_dotenv()

GWS_GAPI = os.getenv("GWS_GAPI",
                     "/root/.hermes/skills/productivity/google-workspace/scripts/google_api.py")
SHEETS_ID = os.getenv("GOOGLE_SHEETS_ID", "")
SHEET_TAB = os.getenv("SHEET_TAB", "leads")

COLS = ["empresa", "ciudad", "categoria", "telefono", "email", "website",
        "rating", "total_reviews", "score", "prioridad", "senales", "pitch", "maps_url"]


def rows_to_leads(rows):
    """Mapea filas (con encabezado en la 1a) a dicts según COLS."""
    leads = []
    for row in rows[1:]:
        if not row or not any(str(c).strip() for c in row):
            continue
        d = {COLS[i]: (row[i] if i < len(row) else "") for i in range(len(COLS))}
        leads.append(d)
    return leads


def read_leads():
    """Lee la pestaña SHEET_TAB y devuelve la lista de leads."""
    r = subprocess.run(
        ["python3", GWS_GAPI, "sheets", "get", SHEETS_ID, f"{SHEET_TAB}!A1:M5000"],
        capture_output=True, text=True, timeout=120,
    )
    if r.returncode != 0:
        print(f"  X  sheet get falló: {r.stderr.strip()[:200]}")
        return []
    try:
        data = json.loads(r.stdout or "[]")
    except json.JSONDecodeError:
        print(f"  X  no pude parsear el get: {r.stdout[:200]}")
        return []
    rows = data.get("values", data) if isinstance(data, dict) else data
    if not isinstance(rows, list):
        return []
    return rows_to_leads(rows)
```

- [ ] **Step 4: Ejecutar el test (pasa)**

Run: `cd /root/arkana_leadgen && .venv/bin/python -m pytest tests/test_sheet_reader.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Verificación de integración (lee tu Sheet real)**

Run:
```bash
cd /root/arkana_leadgen && .venv/bin/python -c "
import sheet_reader as sr
leads = sr.read_leads()
print('leads:', len(leads))
con_email = [l for l in leads if l.get('email')]
print('con email:', len(con_email))
print(con_email[:2])
"
```
Expected: imprime cuántos leads hay y los que tienen email (de tu hoja real).

- [ ] **Step 6: Commit**

```bash
cd /root/arkana_leadgen && git add sheet_reader.py tests/test_sheet_reader.py && git commit -m "feat(outreach): sheet_reader lee leads del Google Sheet"
```

---

### Task 2: `gmail_client.py` — crear borradores vía Gmail API

**Files:**
- Create: `/root/arkana_leadgen/gmail_client.py`
- Test: `/root/arkana_leadgen/tests/test_gmail_client.py`
- Modify: `/root/arkana_leadgen/requirements.txt` (añadir deps Google)

**Interfaces:**
- Consumes: token OAuth `/root/.hermes/google_token.json`, client secret `/root/.hermes/google_client_secret.json`.
- Produces:
  - `build_mime(to: str, subject: str, body: str, sender: str | None = None) -> dict` (dict `{"message": {"raw": <b64>}}`)
  - `create_draft(to: str, subject: str, body: str) -> bool`
  - `get_self_email() -> str`

- [ ] **Step 1: Añadir deps de Google al venv**

Run:
```bash
cd /root/arkana_leadgen && .venv/bin/pip install google-api-python-client google-auth google-auth-oauthlib google-auth-httplib2
```
Expected: instala sin errores.

- [ ] **Step 2: Escribir el test que falla (build_mime es puro)**

```python
import base64
from email import message_from_bytes

import gmail_client as gc

def test_build_mime_roundtrips_to_subject_and_utf8_body():
    # MIMEText utf-8 codifica el cuerpo en base64; hay que decodificarlo.
    payload = gc.build_mime("dest@x.com", "Asunto Demo", "Hola cuerpo áéíóú ñ")
    raw = base64.urlsafe_b64decode(payload["message"]["raw"].encode())
    msg = message_from_bytes(raw)
    assert msg["To"] == "dest@x.com"
    assert msg["Subject"] == "Asunto Demo"
    body = msg.get_payload(decode=True).decode("utf-8")
    assert "Hola cuerpo áéíóú ñ" in body
```

- [ ] **Step 3: Ejecutar para ver que falla**

Run: `cd /root/arkana_leadgen && .venv/bin/python -m pytest tests/test_gmail_client.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'gmail_client'`.

- [ ] **Step 4: Escribir `gmail_client.py`**

```python
"""Crea borradores en Gmail con la API (drafts.create) reutilizando el token OAuth."""
import os
import json
import base64
from email.mime.text import MIMEText

GOOGLE_TOKEN = os.getenv("GOOGLE_TOKEN", "/root/.hermes/google_token.json")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET",
                                 "/root/.hermes/google_client_secret.json")
_SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


def build_mime(to, subject, body, sender=None):
    """Arma el MIME y lo codifica en base64url para la API de Gmail."""
    msg = MIMEText(body, "plain", "utf-8")
    msg["to"] = to
    msg["subject"] = subject
    if sender:
        msg["from"] = sender
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    return {"message": {"raw": raw}}


def _load_creds():
    from google.oauth2.credentials import Credentials
    with open(GOOGLE_TOKEN, encoding="utf-8") as f:
        tok = json.load(f)
    if not tok.get("client_id") or not tok.get("client_secret"):
        with open(GOOGLE_CLIENT_SECRET, encoding="utf-8") as f:
            cs = json.load(f)
        inst = cs.get("installed") or cs.get("web") or {}
        tok.setdefault("client_id", inst.get("client_id"))
        tok.setdefault("client_secret", inst.get("client_secret"))
        tok.setdefault("token_uri", inst.get("token_uri", "https://oauth2.googleapis.com/token"))
    tok.setdefault("scopes", _SCOPES)
    return Credentials.from_authorized_user_info(tok)


def _service():
    from googleapiclient.discovery import build
    return build("gmail", "v1", credentials=_load_creds(), cache_discovery=False)


def get_self_email():
    """Email de la cuenta autenticada (para --to-self)."""
    try:
        prof = _service().users().getProfile(userId="me").execute()
        return prof.get("emailAddress", "")
    except Exception as e:
        print(f"  X  getProfile falló: {e}")
        return ""


def create_draft(to, subject, body):
    """Crea un borrador en Gmail. Devuelve True si se creó."""
    try:
        svc = _service()
        svc.users().drafts().create(
            userId="me", body=build_mime(to, subject, body)
        ).execute()
        return True
    except Exception as e:
        print(f"  X  draft error ({to}): {e}")
        return False
```

- [ ] **Step 5: Ejecutar el test (pasa)**

Run: `cd /root/arkana_leadgen && .venv/bin/python -m pytest tests/test_gmail_client.py -v`
Expected: PASS (1 passed).

- [ ] **Step 6: Actualizar `requirements.txt`**

```bash
cat >> /root/arkana_leadgen/requirements.txt <<'EOF'
google-api-python-client>=2.0
google-auth>=2.0
google-auth-oauthlib>=1.0
google-auth-httplib2>=0.2
EOF
```

- [ ] **Step 7: Verificación de integración — crear 1 borrador a ti mismo**

Run:
```bash
cd /root/arkana_leadgen && .venv/bin/python -c "
import gmail_client as gc
me = gc.get_self_email()
print('cuenta:', me)
print('draft creado:', gc.create_draft(me, 'Prueba Arkana outreach', 'Esto es un borrador de prueba.'))
"
```
Expected: imprime tu email y `draft creado: True`. **Revisa Gmail → Borradores**: debe aparecer.

- [ ] **Step 8: Commit**

```bash
cd /root/arkana_leadgen && git add gmail_client.py tests/test_gmail_client.py requirements.txt && git commit -m "feat(outreach): gmail_client crea borradores vía Gmail API"
```

---

### Task 3: `draft_writer.py` — redactar la propuesta con Hermes

**Files:**
- Create: `/root/arkana_leadgen/draft_writer.py`
- Test: `/root/arkana_leadgen/tests/` (no unit nuevo; se valida por integración)

**Interfaces:**
- Consumes: `hermes_client._chat`, `hermes_client._extract_json`.
- Produces: `write_proposal(lead: dict) -> dict` con claves `asunto`, `cuerpo`.

- [ ] **Step 1: Escribir `draft_writer.py`**

```python
"""Redacta una propuesta personalizada (asunto + cuerpo) vía Hermes."""
from hermes_client import _chat, _extract_json

PROPOSAL_PROMPT = """Eres Luis, de Arkana Tech (agencia de automatización con IA en Colombia).
Escribe un email CORTO y cálido en español para ofrecerle a este negocio una DEMO GRATIS
personalizada (chatbot/automatización). Devuelve SOLO JSON válido, sin markdown.

Negocio:
- Nombre: {empresa}
- Categoría: {categoria}
- Ciudad: {ciudad}
- Señales detectadas: {senales}
- Ángulo de venta: {pitch}

Requisitos del email:
- Asunto corto y concreto (sin clickbait).
- Saludo al negocio por su nombre.
- Menciona de forma natural el dolor detectado (la señal) sin sonar intrusivo.
- Ofrece montar una DEMO GRATIS específica para su negocio.
- CTA suave: pídele responder este correo si le interesa.
- Cierra con: "Si no te interesa, respóndeme y no te vuelvo a escribir."
- Firma: "Arkana Tech — Luis".
- Tono humano, máximo ~120 palabras. Sin emojis excesivos.

Devuelve exactamente:
{{"asunto": "", "cuerpo": ""}}"""


def write_proposal(lead):
    """Genera {asunto, cuerpo} para un lead. Lanza excepción si Hermes falla."""
    prompt = PROPOSAL_PROMPT.format(
        empresa=lead.get("empresa", "N/A"),
        categoria=lead.get("categoria", ""),
        ciudad=lead.get("ciudad", ""),
        senales=lead.get("senales", ""),
        pitch=lead.get("pitch", ""),
    )
    text = _chat([{"role": "user", "content": prompt}], max_tokens=700)
    data = _extract_json(text)
    return {"asunto": data.get("asunto", "").strip(),
            "cuerpo": data.get("cuerpo", "").strip()}
```

- [ ] **Step 2: Verificación de integración — propuesta para 1 lead mock**

Run:
```bash
cd /root/arkana_leadgen && .venv/bin/python -c "
from dotenv import load_dotenv; load_dotenv()
from draft_writer import write_proposal
lead = {'empresa':'Pizzería La Esquina','categoria':'restaurantes','ciudad':'Bogotá',
        'senales':'no_site_chatbot, no_booking_system','pitch':'Web con reseñas pero sin chatbot ni reservas'}
p = write_proposal(lead)
print('ASUNTO:', p['asunto'])
print('CUERPO:\n', p['cuerpo'])
"
```
Expected: imprime un asunto y un cuerpo en español, personalizados, con oferta de demo gratis y línea de baja.

- [ ] **Step 3: Commit**

```bash
cd /root/arkana_leadgen && git add draft_writer.py && git commit -m "feat(outreach): draft_writer redacta propuesta personalizada vía Hermes"
```

---

### Task 4: `outreach.py` — orquestador + CLI + dedupe

**Files:**
- Create: `/root/arkana_leadgen/outreach.py`
- Test: `/root/arkana_leadgen/tests/test_outreach.py`
- Modify: `/root/arkana_leadgen/.gitignore` (añadir `drafted.json`)

**Interfaces:**
- Consumes: `sheet_reader.read_leads`, `draft_writer.write_proposal`, `gmail_client.create_draft`, `gmail_client.get_self_email`.
- Produces:
  - `to_int(x) -> int`
  - `candidates(leads: list[dict], drafted: set, min_score: int) -> list[dict]`
  - `load_drafted()/save_drafted(s: set)`
  - `main(limit, to_self, dry_run)`

- [ ] **Step 1: Escribir el test que falla (filtro puro)**

```python
import outreach as o

def test_to_int():
    assert o.to_int("55") == 55
    assert o.to_int("55.0") == 55
    assert o.to_int("") == 0
    assert o.to_int("abc") == 0

def test_candidates_filters_email_score_and_drafted():
    leads = [
        {"email": "a@x.com", "score": "60"},   # ok
        {"email": "",        "score": "90"},   # sin email -> fuera
        {"email": "b@x.com", "score": "40"},   # score bajo -> fuera
        {"email": "c@x.com", "score": "55"},   # ya drafteado -> fuera
    ]
    out = o.candidates(leads, drafted={"c@x.com"}, min_score=50)
    assert [l["email"] for l in out] == ["a@x.com"]
```

- [ ] **Step 2: Ejecutar para ver que falla**

Run: `cd /root/arkana_leadgen && .venv/bin/python -m pytest tests/test_outreach.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'outreach'`.

- [ ] **Step 3: Escribir `outreach.py`**

```python
"""Outreach: genera borradores de propuesta en Gmail para leads con email."""
import os
import json
import time
import argparse
from dotenv import load_dotenv

load_dotenv()

from sheet_reader import read_leads
from draft_writer import write_proposal
from gmail_client import create_draft, get_self_email

MIN_SCORE = int(os.getenv("MIN_SCORE", "50"))
DRAFTED_FILE = os.getenv("DRAFTED_FILE", "drafted.json")


def to_int(x):
    try:
        return int(float(str(x).strip()))
    except (ValueError, TypeError):
        return 0


def load_drafted():
    try:
        with open(DRAFTED_FILE, encoding="utf-8") as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def save_drafted(s):
    with open(DRAFTED_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(s), f, ensure_ascii=False, indent=2)


def candidates(leads, drafted, min_score=MIN_SCORE):
    out = []
    for l in leads:
        email = (l.get("email") or "").strip().lower()
        if not email or email in drafted:
            continue
        if to_int(l.get("score")) < min_score:
            continue
        out.append(l)
    return out


def main(limit, to_self, dry_run):
    drafted = load_drafted()
    leads = read_leads()
    cands = candidates(leads, drafted)
    print(f"Leads totales: {len(leads)} | candidatos: {len(cands)} | límite: {limit}")
    self_email = get_self_email() if to_self else None
    creados = fallidos = 0
    for lead in cands[:limit]:
        email = lead["email"].strip().lower()
        try:
            prop = write_proposal(lead)
        except Exception as e:
            print(f"  !  proposal falló ({lead.get('empresa')}): {e}")
            fallidos += 1
            continue
        dest = self_email if to_self else email
        if dry_run:
            print(f"\n--- {lead.get('empresa')} -> {dest} ---")
            print("ASUNTO:", prop["asunto"])
            print(prop["cuerpo"])
            continue
        if create_draft(dest, prop["asunto"], prop["cuerpo"]):
            drafted.add(email)
            save_drafted(drafted)
            creados += 1
            print(f"  OK borrador: {lead.get('empresa')} -> {dest}")
        else:
            fallidos += 1
        time.sleep(0.5)
    print(f"\nBorradores creados: {creados} | fallidos: {fallidos}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Arkana outreach (borradores Gmail)")
    p.add_argument("--limit", type=int, default=15)
    p.add_argument("--to-self", action="store_true", help="dirigir borradores a tu propio correo (prueba)")
    p.add_argument("--dry-run", action="store_true", help="imprime sin crear borradores")
    args = p.parse_args()
    main(args.limit, args.to_self, args.dry_run)
```

- [ ] **Step 4: Ejecutar el test (pasa)**

Run: `cd /root/arkana_leadgen && .venv/bin/python -m pytest tests/test_outreach.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Ignorar `drafted.json`**

```bash
echo "drafted.json" >> /root/arkana_leadgen/.gitignore
```

- [ ] **Step 6: Toda la suite**

Run: `cd /root/arkana_leadgen && .venv/bin/python -m pytest tests/ -v`
Expected: PASS (todos).

- [ ] **Step 7: Commit**

```bash
cd /root/arkana_leadgen && git add outreach.py tests/test_outreach.py .gitignore && git commit -m "feat(outreach): outreach.py orquestador con filtro, dedupe y CLI"
```

---

### Task 5: Validación end-to-end

**Files:** (ninguno; ejecución)

- [ ] **Step 1: Dry-run (sin crear nada)**

Run: `cd /root/arkana_leadgen && .venv/bin/python outreach.py --dry-run --limit 2`
Expected: imprime 2 propuestas (asunto+cuerpo) de leads reales con email, sin crear borradores.

- [ ] **Step 2: Borradores de prueba a ti mismo**

Run: `cd /root/arkana_leadgen && .venv/bin/python outreach.py --to-self --limit 2`
Expected: crea 2 borradores dirigidos a TU correo. Revisa Gmail → Borradores. (No marca como drafteado a los leads reales porque van a ti — ver nota.)

- [ ] **Step 3: Corrida real pequeña**

Run: `cd /root/arkana_leadgen && .venv/bin/python outreach.py --limit 2`
Expected: 2 borradores dirigidos a los leads reales; quedan registrados en `drafted.json`.

- [ ] **Step 4: Verificar dedupe**

Run: `cd /root/arkana_leadgen && .venv/bin/python outreach.py --limit 2`
Expected: crea borradores para los SIGUIENTES candidatos (no repite los ya drafteados).

---

## Notas de operación
- Generar borradores: `cd /root/arkana_leadgen && .venv/bin/python outreach.py --limit 10`
- Ver candidatos sin crear nada: `... outreach.py --dry-run --limit 5`
- Resetear historial de drafteados: `rm /root/arkana_leadgen/drafted.json`
- **Nota `--to-self`:** dirige el correo a ti pero igualmente NO marca al lead como drafteado (se usa solo para probar el formato). Para outreach real usa sin `--to-self`.

## Self-Review
- **Cobertura del spec:** leer Sheet→T1; gmail draft (mecanismo confirmado §6)→T2; redacción Hermes→T3; orquestación+dedupe+CLI (--limit/--to-self/--dry-run)→T4; pruebas (to-self, real, dedupe)→T5. Filtro email+score≥50→`candidates`. Cumplimiento (línea de baja, firma)→PROPOSAL_PROMPT. ✅
- **Placeholders:** ninguno (código completo en cada paso).
- **Consistencia de tipos:** `read_leads`/`rows_to_leads`, `write_proposal`→{asunto,cuerpo}, `create_draft`/`build_mime`/`get_self_email`, `candidates`/`to_int`/`load_drafted`/`save_drafted` coherentes entre tasks. Columnas (13) coinciden con el Sheet.
