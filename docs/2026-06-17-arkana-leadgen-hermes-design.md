# Diseño — Arkana Lead Gen con Hermes (v1)

**Fecha:** 2026-06-17
**Autor:** zitro677 + Claude
**Estado:** Aprobado (pendiente review del spec)
**Enfoque:** B — "Python orquesta (determinista), Hermes piensa (LLM + Sheets + Telegram)"

---

## 1. Objetivo

Automatizar la generación de leads para **Arkana Tech** (agencia de automatización con IA):
descubrir negocios locales en Google Maps, calificarlos por su "madurez para automatización"
con una rúbrica de señales, y entregar los leads calificados a Google Sheets + un Top-5 diario
a Telegram. Todo corre **desatendido por cron** en el VPS donde ya está instalado Hermes.

**Diferenciador clave vs. el script original:** la calificación (LLM) se hace a través de
**Hermes / openai-codex (suscripción ChatGPT Pro)** en lugar de la API de Anthropic por token
→ **cero `ANTHROPIC_API_KEY`, cero coste por token** para calificar.

---

## 2. Arquitectura (visión general)

```
cron del sistema (diario 08:00 America/Bogota)
   │
   ▼
lead_gen.py  ──(1) Apify scrape──► negocios crudos (por cada target)
   │
   ├─(2) por lead → POST http://127.0.0.1:8642/v1/chat/completions
   │        Hermes/openai-codex califica usando la skill `arkana_lead_gen`
   │        → JSON estricto (score, señales, pitch, prioridad)
   │        Python filtra score>=55, deduplica
   │
   ├─(3) 1 run de agente → Hermes escribe filas en Google Sheet (skill google-workspace)
   │
   └─(4) Hermes envía Top-5 a Telegram + backup local CSV/JSON en el VPS
```

**Principio:** la parte determinista y costosa (scrape de Apify, orquestación, dedupe, filtrado)
vive en Python para ser fiable y depurable. La parte "inteligente" (calificar, escribir en Sheets,
notificar) la hace Hermes con sus capacidades nativas.

---

## 3. Componentes

### 3.1 `lead_gen.py` (orquestador, en el VPS)
- `scrape_google_maps(query)` — **sin cambios**: usa Apify (`compass~crawler-google-places`),
  `APIFY_KEY`. v1 con `includeReviews=false`.
- `qualify_lead_via_hermes(lead, ciudad, categoria)` — **NUEVO**: reemplaza la llamada a
  `anthropic`. Hace `POST` a la API local de Hermes (OpenAI-compatible) en `localhost:8642`,
  referenciando la skill `arkana_lead_gen`. Devuelve el JSON del esquema de salida. Con reintento.
- Filtrado (`score >= 55`) y **dedupe** por `google_maps_url` — en Python.
- `write_to_sheets_via_hermes(leads)` — **NUEVO**: una sola llamada (agent run) instruyendo a
  Hermes a añadir las filas a la hoja vía `google-workspace`.
- `notify_telegram(top5)` — Top-5 entregado vía Hermes (reutiliza el chat ya configurado).
- Backup local `leads_YYYYMMDD_HHMM.{json,csv}` en el VPS.

### 3.2 Hermes (el "cerebro")
- **API local OpenAI-compatible** (`API_SERVER_ENABLED=true`, puerto 8642) para las llamadas de
  calificación y el run que escribe en Sheets.
- **Skill `arkana_lead_gen`** (nueva, ver §5): rúbrica + esquema de salida.
- **Skill `google-workspace`** (builtin, requiere login OAuth): escribe en Google Sheets.
- **Telegram**: entrega del Top-5.
- **Modelo:** openai-codex (ChatGPT Pro).

### 3.3 Scheduling
- **System cron** (no cron de Hermes): diario **08:00 America/Bogota**. Determinista para correr
  un script. El cron de Hermes queda como alternativa documentada.

---

## 4. Alcance v1 — Señales y scoring

v1 usa **scrape básico (sin reviews)** → 3 señales fiables activas:

| Señal | Dato | Puntos | v1 |
|-------|------|--------|----|
| `no_website` | campo website vacío/null | +30 | ✅ |
| `no_whatsapp_bot` | descripción GMB sin chatbot/WhatsApp | +25 | ✅ |
| `no_booking_system` | sin URL de reserva/booking visible | +15 | ✅ (best-effort) |
| `poor_review_response` | reviews + respuestas del dueño | +25 | ⛔ v2 |
| `outdated_hours` | última actualización > 6 meses | +5 | ⛔ v2 |

**Umbrales (sin cambios):** score ≥ 55 → `alta` · 30–54 → `media` · < 30 → `baja`.
Un negocio *sin web + sin bot* = 30 + 25 = **55 = alta** (funciona natural).
Score máximo realista en v1 ≈ 70.

**Categorías (8):** restaurantes, inmobiliarias, administracion_conjuntos, talleres_mecanicos,
clinicas_dentales, firmas_juridicas, car_detailing, landscaping_irrigation.

**Parámetros:** `city`, `category`, `min_reviews` (default 10), `max_batch` (default 30).

**Primera corrida de validación:** solo **Bogotá** (8 categorías). Nashville se añade tras validar.

---

## 5. Skill `arkana_lead_gen` (formato Hermes)

El contenido funcional lo aporta el usuario; se formaliza con el frontmatter YAML que Hermes
requiere. Se instala en `/root/.hermes/skills/arkana_lead_gen/SKILL.md`.

```yaml
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
```
+ cuerpo con: Purpose, CATEGORIES, Qualification Signals, Output Schema, Scoring Logic
(según lo definido por el usuario; en v1 solo se evalúan las 3 señales disponibles).

**Esquema de salida (JSON estricto):**
```json
{
  "empresa": "string", "categoria": "string", "ciudad": "string",
  "telefono": "string", "website": "string | null", "google_maps_url": "string",
  "rating": 0.0, "total_reviews": 0, "señales": ["string"],
  "score": 0, "pitch_angle": "string", "prioridad": "alta | media | baja"
}
```

---

## 6. Integración con Hermes (API local)

- **Calificar (sin tools):** `POST http://127.0.0.1:8642/v1/chat/completions`
  con `Authorization: Bearer <API_SERVER_KEY>`, formato OpenAI. Devuelve el JSON del lead.
- **Escribir en Sheets (con tools):** agent run que invoca `google-workspace`.
- **Modelo:** se consulta con `GET /v1/models` (perfil o `hermes-agent`).
- Robustez JSON: limpiar posible markdown (```json), `json.loads`, reintento por lead.

---

## 7. Configuración (`.env` del proyecto en el VPS)

```
APIFY_KEY=...
HERMES_API_URL=http://127.0.0.1:8642/v1
HERMES_API_KEY=...            # = API_SERVER_KEY de Hermes
HERMES_MODEL=hermes-agent     # o el nombre de perfil que devuelva /v1/models
GOOGLE_SHEETS_ID=...          # hoja destino (la crea el usuario)
SHEET_TAB=leads
```
**Ya NO se necesita:** `ANTHROPIC_API_KEY`, `credentials.json` (service-account).

---

## 8. Manejo de errores y robustez

- **Calificación por lead:** try/except + 1 reintento; si falla, se salta y se loguea (no rompe el lote).
- **Dedupe:** set de `google_maps_url` (y teléfono como respaldo) persistido en
  `seen_leads.json` local; no re-insertar negocios ya vistos en corridas previas.
- **Hermes API caída:** el script avisa y **guarda el JSON/CSV local** (no se pierde el scrape de Apify).
- **Sheets falla:** fallback a CSV local + alerta a Telegram "Sheets falló, leads en /ruta".

---

## 9. Piezas nuevas a montar (una sola vez)

- **A. API local de Hermes:** añadir `API_SERVER_ENABLED=true` y `API_SERVER_KEY=<secreto>` a
  `/root/.hermes/.env`; reiniciar `hermes-gateway`; verificar con `curl`.
- **B. Skill `google-workspace`:** hacer login OAuth con la cuenta de Google dueña de la hoja;
  crear la hoja destino y copiar su `GOOGLE_SHEETS_ID`.
- **C. Skill `arkana_lead_gen`:** crear `SKILL.md` en `/root/.hermes/skills/arkana_lead_gen/`.
- **D. Proyecto Python:** subir/crear `lead_gen.py` + `.env` + deps (`requests`, `python-dotenv`).

---

## 10. Estrategia de pruebas (incremental, antes del cron)

1. `curl` a la API de Hermes → responde 200.
2. Calificar **1 lead** vía Hermes → imprime JSON válido del esquema.
3. Escribir **2 filas** de prueba en la hoja vía Hermes → verificar en Sheets.
4. Run completo de **1 ciudad** (`--ciudad Bogotá`) → Sheets + Top-5 a Telegram + backup local.
5. Activar **cron** diario 08:00 America/Bogota.

---

## 11. Roadmap v2 (anotado, fuera de alcance v1)

- Activar `includeReviews=true` en Apify → señal `poor_review_response`.
- Enriquecimiento con **Scrapling**: visitar la web propia del negocio para detectar mejor
  `no_booking_system` / `no_whatsapp_bot` sin gastar créditos de Apify.
- Señal `outdated_hours` (si Apify expone fecha de actualización fiable).
- Añadir **Nashville** y más ciudades/categorías.
- Dashboard / reporte semanal agregado.
```
