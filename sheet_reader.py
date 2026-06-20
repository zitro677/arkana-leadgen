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
