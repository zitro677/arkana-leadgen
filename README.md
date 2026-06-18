# Arkana Lead Gen (v1)

Pipeline diario: **Apify (Google Maps)** → **Hermes / openai-codex** (califica) → **Google Sheets** (script `google_api.py`) + **Telegram** (Top-5).

## Arquitectura
- `lead_gen.py` — orquestador: scrape (Apify), dedupe, filtrado, backup, CLI.
- `hermes_client.py` — `qualify_lead` (API local de Hermes) + `write_leads_to_sheet` (script directo google_api.py).
- `notify.py` — `send_telegram`.
- `hermes_skill/arkana_lead_gen/` — skill de Hermes (rúbrica de calificación).

## Requisitos previos (ya configurados en el VPS)
- Hermes con API local activa (`API_SERVER_ENABLED=true`).
- Skill `google-workspace` autenticada (OAuth) y Google Sheets API habilitada.

## Instalación en el VPS
```bash
git clone https://github.com/zitro677/arkana-leadgen /root/arkana_leadgen
cd /root/arkana_leadgen
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
nano .env          # rellena APIFY_KEY, HERMES_API_KEY, GOOGLE_SHEETS_ID, TELEGRAM_*

# Instalar la skill de calificación
mkdir -p /root/.hermes/skills/arkana_lead_gen
cp hermes_skill/arkana_lead_gen/* /root/.hermes/skills/arkana_lead_gen/
systemctl restart hermes-gateway
```

## Uso
```bash
.venv/bin/python lead_gen.py --test                       # 1 categoría
.venv/bin/python lead_gen.py --ciudad Bogotá --categoria restaurantes
.venv/bin/python lead_gen.py --ciudad Bogotá              # 8 categorías
.venv/bin/python -m pytest tests/ -v                      # tests
```

## Cron (diario 08:00 America/Bogota)
```bash
chmod +x run_daily.sh
( crontab -l 2>/dev/null; echo "CRON_TZ=America/Bogota"; echo "0 8 * * * /root/arkana_leadgen/run_daily.sh" ) | crontab -
```

## Operación
- Logs: `tail -f cron.log`
- Forzar corrida: `./run_daily.sh`
- Resetear dedupe: `rm seen_leads.json`

## Roadmap v2
Apify con reviews (`poor_review_response`), enriquecimiento con Scrapling, `outdated_hours`, Nashville, reporte semanal.
