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
    print(f"  Backup local: leads_{stamp}.json / .csv")


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
    print(f"\nArkana Lead Gen v1 — {datetime.now():%Y-%m-%d %H:%M}")
    for ciudad, categoria, query in targets:
        print(f"Scraping: {query}")
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
    print(f"\n{total_raw} scrapeados -> {len(qualified)} con score>={min_score}")
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
    print(f"\nCompletado — {len(leads)} leads calificados")
