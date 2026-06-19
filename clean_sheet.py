"""Limpia la pestaña 'leads': pone fila de encabezados arriba y quita filas de prueba.

Lee el contenido actual, descarta filas de prueba (PRUEBA_ARKANA, DIRECTO, etc.)
y filas vacías/encabezados viejos, y reescribe: [encabezados] + [filas reales].
Rellena con filas vacías para borrar las que sobraban abajo.
"""
import os
import json
import subprocess
from dotenv import load_dotenv

load_dotenv()

GAPI = os.getenv("GWS_GAPI",
                 "/root/.hermes/skills/productivity/google-workspace/scripts/google_api.py")
SHEET = os.getenv("GOOGLE_SHEETS_ID")
TAB = os.getenv("SHEET_TAB", "leads")

HEADER = ["Empresa", "Ciudad", "Categoria", "Telefono", "Email", "Website",
          "Rating", "Reseñas", "Score", "Prioridad", "Señales", "Pitch", "MapsURL"]
TEST_MARKERS = ("PRUEBA_ARKANA", "DIRECTO", "Test A", "Test B")


def gapi(*args, values=None):
    cmd = ["python3", GAPI, *args]
    if values is not None:
        cmd += ["--values", json.dumps(values, ensure_ascii=False)]
    return subprocess.run(cmd, capture_output=True, text=True)


def is_test_or_empty(row):
    if not row or not any(str(c).strip() for c in row):
        return True
    joined = " ".join(str(c) for c in row)
    if any(m in joined for m in TEST_MARKERS):
        return True
    if str(row[0]).strip().lower() in ("empresa", ""):  # encabezado viejo
        return True
    return False


def main():
    r = gapi("sheets", "get", SHEET, f"{TAB}!A1:M2000")
    if r.returncode != 0:
        print("ERROR get:", (r.stderr or r.stdout)[:300])
        return
    try:
        data = json.loads(r.stdout or "[]")
    except json.JSONDecodeError:
        print("No pude parsear la respuesta del get:", r.stdout[:300])
        return
    rows = data.get("values", data) if isinstance(data, dict) else data
    if not isinstance(rows, list):
        print("Formato inesperado del get:", str(data)[:300])
        return
    print(f"Filas leídas: {len(rows)}")

    clean = [row for row in rows if not is_test_or_empty(row)]
    print(f"Filas reales conservadas: {len(clean)}")

    new_rows = [HEADER] + clean
    # Rellenar con filas vacías para limpiar las que sobraban abajo.
    while len(new_rows) < len(rows) + 1:
        new_rows.append([""] * len(HEADER))

    r2 = gapi("sheets", "update", SHEET, f"{TAB}!A1", values=new_rows)
    if r2.returncode != 0:
        print("ERROR update:", (r2.stderr or r2.stdout)[:300])
        return
    print("OK update:", (r2.stdout or "").strip()[:120])
    print(f"Hoja '{TAB}' limpia: 1 fila de encabezados + {len(clean)} leads reales.")


if __name__ == "__main__":
    main()
