# Diseño — Outreach de propuestas (borradores en Gmail)

**Fecha:** 2026-06-19
**Autor:** zitro677 + Claude
**Estado:** Aprobado (pendiente review del spec)
**Proyecto:** arkana-leadgen (extensión)

---

## 1. Objetivo

Generar **borradores de propuesta personalizados en Gmail** para los leads
calificados que tienen email, de forma que el usuario los revise y envíe
manualmente. NO se envían correos automáticamente (protege la reputación del
dominio y permite control humano).

- **CTA:** ofrecer una **demo gratis personalizada** del chatbot/automatización
  para el negocio concreto.
- **Disparo:** comando manual (`outreach.py`), cuando el usuario quiera.
- **Filtro:** leads con email **y** score ≥ 50, que no tengan ya un borrador.

## 2. Arquitectura

Script nuevo `outreach.py`, independiente del pipeline de scraping:

```
outreach.py [--limit N] [--to-self] [--dry-run]
  1. Lee la pestaña `leads` del Google Sheet (fuente de verdad) vía google_api.py
  2. Filtra: email presente + score>=50 + email NO en drafted.json
  3. Por cada lead (hasta --limit, default 15):
       a. draft_writer.write_proposal(lead) -> {asunto, cuerpo} (vía Hermes)
       b. gmail_client.create_draft(to, asunto, cuerpo)
       c. registra el email en drafted.json
  4. Resumen: cuántos borradores creados, saltados, fallidos
```

## 3. Componentes

- **`outreach.py`** — orquestador: leer Sheet, parsear filas, filtrar, dedupe,
  bucle de generación, CLI (`--limit`, `--to-self` para pruebas, `--dry-run`).
- **`sheet_reader.py`** — `read_leads() -> list[dict]`: llama
  `google_api.py sheets get` y mapea filas (según el orden de columnas del
  pipeline: Empresa, Ciudad, Categoria, Telefono, Email, Website, Rating,
  Reseñas, Score, Prioridad, Señales, Pitch, MapsURL) a dicts.
- **`draft_writer.py`** — `write_proposal(lead) -> dict`: prompt a Hermes (API
  local) en español, tono Arkana, oferta de demo gratis, CTA suave, línea de
  baja. Devuelve `{"asunto": str, "cuerpo": str}`.
- **`gmail_client.py`** — `create_draft(to, subject, body) -> bool`: usa
  `google_api.py gmail` (scope `gmail.modify` ya autorizado).
- **`drafted.json`** — store local (set de emails ya drafteados; como
  `seen_leads.json`).

## 4. Contenido del correo y cumplimiento

- Personalizado por lead: nombre del negocio, categoría, **señal detectada**
  (ej. "vi que tienen muchas reseñas pero sin chatbot en su web"), oferta de
  **demo gratis** específica para ese rubro.
- Corto, cálido, español, firmado **Arkana Tech (Luis)**.
- Incluye **identidad clara del remitente** y **línea de baja** ("si no te
  interesa, respóndeme y no te vuelvo a escribir") → buenas prácticas anti-spam.
- Como son **borradores que el usuario envía a mano**, la responsabilidad final
  de envío/consentimiento es del usuario.

## 5. Manejo de errores y dedupe

- Hermes falla en un lead → se salta, se loguea, no rompe el lote.
- Creación de borrador falla → se loguea y **NO** se marca como drafteado
  (se reintenta en la próxima corrida).
- `drafted.json` evita borradores duplicados entre corridas.
- `--dry-run` imprime los borradores sin crearlos en Gmail.
- `--to-self` dirige el borrador al propio usuario (prueba sin tocar leads).

## 6. Mecanismo de borrador (CONFIRMADO)

`google_api.py gmail` expone `{search, get, send, reply, labels, modify}` —
**no** tiene subcomando de borradores. Por tanto `gmail_client.create_draft`
usará la **API de Gmail directamente** (`users().drafts().create()`) con el
token OAuth ya autorizado (`/root/.hermes/google_token.json`, scope
`gmail.modify`). Requiere `google-api-python-client` + `google-auth` en el venv
del proyecto (se instalan en el plan). Si el token no incluye `client_id/secret`,
se completan desde `/root/.hermes/google_client_secret.json`.

## 7. Estrategia de pruebas

1. Verificar capacidad de borradores de `google_api.py gmail` (paso 0).
2. `draft_writer.write_proposal` sobre 1 lead mock → asunto+cuerpo coherentes.
3. `outreach.py --to-self --limit 1` → 1 borrador dirigido a tu propio correo;
   verificar que aparece en Gmail.
4. `outreach.py --limit 2` real → 2 borradores en Gmail + registrados en
   `drafted.json`; re-correr → 0 nuevos (dedupe).

## 8. Fuera de alcance (después)

- Leads **solo con teléfono** (sin email): outreach por WhatsApp/llamada — se
  diseñará aparte.
- Envío automático, seguimiento de aperturas/respuestas, secuencias multi-toque.
