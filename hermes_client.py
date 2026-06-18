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
- Email: {email}
- Tiene website: {has_web}
- Website: {website}
- Chatbot detectado en su web: {has_chatbot}
- Rating: {rating}
- Total reseñas: {reviews}
- Ciudad: {ciudad}
- Categoría: {categoria}
- Descripción GMB: {descripcion}

Scoring v2 (suma los puntos que apliquen):
- no_website (NO tiene website): +40
- no_site_chatbot (tiene website pero "Chatbot detectado"=No): +35
- no_booking_system (sin URL de reserva/booking visible): +15
- email_found (tiene email): +10
Nota: "no_website" y "no_site_chatbot" son excluyentes (si no hay web, no se evalúa chatbot).
Prioridad: score>=55 -> alta, 30-54 -> media, <30 -> baja.

El pitch_angle: frase corta del dolor detectado + servicio Arkana sugerido.

Devuelve exactamente este esquema (rellena los valores):
{{"empresa":"","categoria":"{categoria}","ciudad":"{ciudad}","telefono":"","email":"","website":null,"google_maps_url":"","rating":0.0,"total_reviews":0,"señales":[],"score":0,"pitch_angle":"","prioridad":"baja"}}"""


def qualify_lead(lead, ciudad, categoria, retries=1):
    """Califica un lead (ya enriquecido) vía Hermes. Devuelve dict o None."""
    website = lead.get("website")
    prompt = QUALIFY_PROMPT.format(
        nombre=lead.get("title", "N/A"),
        telefono=lead.get("phone", "N/A"),
        email=lead.get("email") or "ninguno",
        has_web="Sí" if website else "No",
        website=website or "ninguno",
        has_chatbot="Sí" if lead.get("has_site_chatbot") else "No",
        rating=lead.get("totalScore", "N/A"),
        reviews=lead.get("reviewsCount", 0),
        ciudad=ciudad, categoria=categoria,
        descripcion=(lead.get("description") or "")[:300],
    )
    for attempt in range(retries + 1):
        try:
            text = _chat([{"role": "user", "content": prompt}])
            data = _extract_json(text)
            # Rellenar desde el raw/enriquecido si el modelo los dejó vacíos.
            data["google_maps_url"] = data.get("google_maps_url") or lead.get("url", "")
            data["rating"] = data.get("rating") or lead.get("totalScore", 0)
            data["total_reviews"] = data.get("total_reviews") or lead.get("reviewsCount", 0)
            data["email"] = data.get("email") or lead.get("email", "")
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
        l.get("telefono", ""), l.get("email", ""), l.get("website") or "",
        l.get("rating", ""), l.get("total_reviews", ""), l.get("score", ""),
        l.get("prioridad", ""), ", ".join(l.get("señales", [])),
        l.get("pitch_angle", ""), l.get("google_maps_url", ""),
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
