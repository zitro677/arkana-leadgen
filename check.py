"""Diagnóstico v2: enriquece + califica leads de prueba e imprime el JSON.

Uso:
  python check.py                 -> lead mock sin web (no_website)
  python check.py https://sitio   -> enriquece un sitio real (email + chatbot)
"""
import sys
import json
from dotenv import load_dotenv

load_dotenv()
from enrich import enrich_lead
from hermes_client import qualify_lead

if len(sys.argv) > 1:
    url = sys.argv[1]
    lead = {
        "title": "Negocio de prueba",
        "phone": "+57 300 111 2233",
        "website": url,
        "totalScore": 4.3,
        "reviewsCount": 120,
        "url": "https://maps.google.com/?cid=test",
        "description": "",
    }
else:
    lead = {
        "title": "Pizzería Demo Centro",
        "phone": "+57 300 111 2233",
        "website": None,
        "totalScore": 4.1,
        "reviewsCount": 87,
        "url": "https://maps.google.com/?cid=demo1",
        "description": "Pizza artesanal al horno de leña",
    }

print("Enriqueciendo (visita web si tiene)...")
lead = enrich_lead(lead)
print(f"  email={lead.get('email')!r}  has_site_chatbot={lead.get('has_site_chatbot')}")
print("Calificando vía Hermes... (unos segundos)")
result = qualify_lead(lead, "Bogotá Colombia", "restaurantes")
print(json.dumps(result, ensure_ascii=False, indent=2))
