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
    p.add_argument("--to-self", action="store_true",
                   help="dirigir borradores a tu propio correo (prueba)")
    p.add_argument("--dry-run", action="store_true", help="imprime sin crear borradores")
    args = p.parse_args()
    main(args.limit, args.to_self, args.dry_run)
