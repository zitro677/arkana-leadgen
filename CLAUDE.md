# CLAUDE.md — Hermes Leads (Arkana Tech)

Guía para trabajar en este proyecto. Léela antes de tocar código.

# Rules

Never open responses with filler phrases like "Great question!", "Of course!", "Certainly!", or similar warmups. Start every response with the actual answer. No preamble, no acknowledgment of the question.

Match response length to task complexity. Simple questions get direct, short answers. Complex tasks get full, detailed responses. Never pad responses with restatements of the question or closing sentences that repeat what you just said.

Before any significant task, show me 2-3 ways you could approach this work. Wait for me to choose before proceeding.

If you are uncertain about any fact, statistic, date, or piece of technical information: say so explicitly before including it. Never fill gaps in your knowledge with plausible-sounding information. When in doubt, say so.

About me: [Luis] / Role: [Dev] / Background in: [Information science]. Strong in: [Architecture models]. Still learning: [agentic, RAGS]. Adjust the depth of every response to match this. Never over-explain what I already know. Never skip context I need.

What I'm working on: [Sistema automatizacion leads con Hermes agent] / Goal: [automatizar leads para arkana tech] / Audience: [empleados Arkana tech] / Stack context: [null] / What to avoid: [null]. Apply this context to every task. When something doesn't fit, flag it before proceeding.


# Behaviour

Only modify files, functions, and lines of code directly related to the current task. Do not refactor, rename, reorganize, reformat, or "improve" anything I did not explicitly ask you to change. If you notice something worth fixing elsewhere, mention it in a note at the end. Do not touch it. Ever.

Before making any change that significantly alters content I've already created (rewriting sections, removing paragraphs, restructuring flow, changing tone): stop. Describe exactly what you're about to change and why. Wait for my confirmation before proceeding.

Before deleting any file, overwriting existing code, dropping database records, or removing dependencies: stop. List exactly what will be affected. Ask for explicit confirmation. Only proceed after I say yes in the current message. "You mentioned this earlier" is not confirmation.

The following require explicit in-session confirmation, no exceptions: deploying or pushing to any environment, running migrations or schema changes, sending any external API call, executing any command with irreversible side effects. I must say yes in the current message.

After any coding task, end with: Files changed (list every file touched) / What was modified (one line per file) / Files intentionally not touched / Follow-up needed.

For any task involving architecture decisions, debugging complex issues, or non-trivial features: work through the problem step by step before writing any code. Show your reasoning. Identify where you're uncertain. Then implement.

 # Memory

Maintain a file called MEMORY.md in this project. After any significant decision, add an entry: What was decided / Why / What was rejected and why. Read MEMORY.md at the start of every session. Never contradict a logged decision without flagging it first.

When I say "session end", "wrapping up", or "let's stop here": write a session summary to MEMORY.md. Include: Worked on / Completed / In progress / Decisions made / Next session priorities.

Maintain a file called ERRORS.md. When an approach takes more than 2 attempts to work, log it: What didn't work / What worked instead / Note for next time. Check ERRORS.md before suggesting approaches to similar tasks.

For questions involving system architecture, performance tradeoffs, database design, or long-term technical decisions: use extended thinking mode. Work through the problem step by step. Surface tradeoffs I haven't considered. Flag assumptions that might not hold at scale. Then give your recommendation.

1. Ask, don't assume. If something is unclear, ask before writing a single line. Never make silent assumptions about intent, architecture, or requirements.

2. Simplest solution first. Always implement the simplest thing that could work. Do not add abstractions or flexibility that weren't explicitly requested.

3. Don't touch unrelated code. If a file or function is not directly part of the current task, do not modify it, even if you think it could be improved.

4. Flag uncertainty explicitly. If you are not confident about an approach or technical detail, say so before proceeding. Confidence without certainty causes more damage than admitting a gap.


## Qué es

Sistema autónomo de **generación de leads** para **Arkana Tech** (agencia de
automatización con IA). Corre en un VPS y, a diario, descubre negocios locales en
Google Maps, los califica por su "madurez para automatización" y entrega los leads
a Google Sheets + Telegram. En construcción: **outreach** (borradores de propuesta
en Gmail).

- **Repo:** https://github.com/zitro677/arkana-leadgen
- **Repo local:** `E:\Projects Claude\Hermes-leads`
- **VPS:** `root@srv1764335.hstgr.cloud` (IPv4 `2.25.210.78`) — Hostinger, Ubuntu 24.04
- **Despliegue en VPS:** `/root/arkana_leadgen` (clon del repo, venv en `.venv`)

## Arquitectura

```
cron 08:00 America/Bogota
  -> lead_gen.py (orquestador)
       Apify Google Maps  -> enrich.py (Scrapling: email + chatbot)
       -> hermes_client.qualify_lead (Hermes/openai-codex, skill arkana_lead_gen)
       -> hermes_client.write_leads_to_sheet (google_api.py sheets append)
       -> notify.send_telegram (Top-5)  +  backup CSV/JSON local

outreach.py (manual, EN CONSTRUCCIÓN)
  -> sheet_reader (lee leads del Sheet) -> draft_writer (Hermes redacta)
  -> gmail_client (crea BORRADOR en Gmail vía API)  [no envía]
```

### Decisiones clave (no romper)
- **Hermes hace la calificación** vía su API local OpenAI-compatible
  (`http://127.0.0.1:8642/v1/chat/completions`, modelo `hermes-agent`), usando la
  suscripción ChatGPT Pro (openai-codex). **No** se usa la API de Anthropic.
- **Google Sheets** se escribe DIRECTO con el script de la skill google-workspace:
  `google_api.py sheets append` (determinista, sin gate de aprobación del agente).
  NO rutear la escritura por el agente de Hermes (se bloquea pidiendo aprobación).
- **Enriquecimiento web propio (Scrapling)**: email por regex; chatbot por
  firmas de proveedores conocidos **+** señales DOM genéricas (>=2) para bots
  propios/self-hosted. Un link `wa.me` NO cuenta como chatbot.
- **Dedupe** entre corridas: `seen_leads.json` (pipeline), `drafted.json` (outreach).

### Rúbrica de scoring (v2) — definida en la skill `arkana_lead_gen`
- `no_website` +40 · `no_site_chatbot` +35 · `no_booking_system` +15 · `email_found` +10
- Umbrales: ≥55 alta · 30-54 media · <30 baja.
- `MIN_SCORE=50` (umbral para incluir en Sheet y para outreach).

## Archivos

| Archivo | Responsabilidad |
|---------|-----------------|
| `lead_gen.py` | Orquestador del pipeline: scrape, dedupe, filtro, backup, CLI |
| `hermes_client.py` | `qualify_lead` (Hermes) + `write_leads_to_sheet` (google_api.py) |
| `enrich.py` | Scrapling: `enrich_lead`, `detect_chatbot`, `extract_emails` |
| `notify.py` | `send_telegram` (Bot API) |
| `clean_sheet.py` | Limpia la hoja: encabezados + quita filas de prueba |
| `inspect_site.py` | Diagnóstico: qué chatbot/scripts tiene una web |
| `check.py` | Smoke test: enriquece+califica 1 lead |
| `run_daily.sh` | Wrapper del cron |
| `hermes_skill/arkana_lead_gen/` | La skill (se copia a `~/.hermes/skills/`) |
| `tests/` | pytest (lógica pura) |
| `outreach.py`, `sheet_reader.py`, `draft_writer.py`, `gmail_client.py` | Outreach (en construcción) |
| `docs/` | specs y planes de diseño |
| `SESSION-NOTES.md` | Bitácora |

## Config (`.env` en el VPS, NO commitear)

`APIFY_KEY`, `HERMES_API_URL=http://127.0.0.1:8642/v1`, `HERMES_API_KEY`,
`HERMES_MODEL=hermes-agent`, `GOOGLE_SHEETS_ID`, `SHEET_TAB=leads`,
`MIN_SCORE=50`, `MAX_BATCH=10`, `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID`.
Opcional: `GWS_GAPI` (ruta a google_api.py).

## Dependencias externas (ya montadas en el VPS)
- Hermes con API local activa (`API_SERVER_ENABLED=true` en `/root/.hermes/.env`).
- Skill `google-workspace` autenticada (OAuth). Token: `/root/.hermes/google_token.json`.
  Script: `/root/.hermes/skills/productivity/google-workspace/scripts/google_api.py`
  (`sheets get|update|append|create`, `gmail search|get|send|reply|labels|modify`).
  Gmail **no** tiene subcomando de borradores → outreach usa la API de Gmail directa.
- Google Sheets API + Gmail scopes habilitados en el proyecto Google Cloud.

## Comandos

```bash
# En el VPS (/root/arkana_leadgen)
.venv/bin/python -m pytest tests/ -v          # tests
.venv/bin/python lead_gen.py --test           # 1 categoría
.venv/bin/python lead_gen.py --ciudad Bogotá  # corrida completa
./run_daily.sh                                # corrida del cron (manual)
tail -f cron.log                              # logs
rm seen_leads.json                            # resetear dedupe
```

## Convenciones / cómo trabajar aquí

- **Despliegue:** el código vive en GitHub. Para actualizar el VPS:
  `cd /root/arkana_leadgen && git pull`. Los `push` se hacen desde el repo local.
- **NO pegar archivos a mano en el VPS** (heredocs y líneas largas se rompen al
  pegar en esa terminal). Crear/editar archivos vía repo + `git pull`. Para
  comandos multi-token usar `\` de continuación o ponerlos en una sola línea.
- **Secretos:** `.env`, `seen_leads.json`, `drafted.json`, `leads_*.json/csv`,
  `cron.log` están en `.gitignore`. No commitear credenciales.
- **TDD:** lógica pura con tests en `tests/`; las integraciones (Apify, Hermes,
  Sheets, Gmail) se validan con comandos de verificación, no en pytest.
- **Idioma:** español (Bogotá). Tildes/ñ OK (archivos en UTF-8, LF — ver `.gitattributes`).
- **Robustez para cron desatendido:** todo paso externo con try/except + reintento;
  fallo de un lead se salta, no rompe el lote.

## Roadmap
- En curso: **outreach** (borradores Gmail) — ver `docs/2026-06-19-arkana-outreach-plan.md`.
- Después: leads solo-teléfono (WhatsApp), Apify con reviews (`poor_review_response`),
  `outdated_hours`, Nashville, reporte semanal.


## SESIÓN WORKFLOW (obligatorio)
Al iniciar SIEMPRE:
1. Lee memory.md → contexto del proyecto
2. Lee claude-progress.txt → estado actual y pendientes  
3. Lee errors.md → errores conocidos a evitar

Al terminar SIEMPRE:
1. Actualiza claude-progress.txt → nueva entrada en LOG DE SESIONES
2. Si hubo error complejo → agrégalo a errors.md
3. Haz commit con mensaje descriptivo

