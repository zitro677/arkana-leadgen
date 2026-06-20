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
