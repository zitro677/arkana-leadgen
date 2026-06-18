"""Diagnóstico: califica 1 lead de prueba vía Hermes e imprime el JSON."""
import json
from dotenv import load_dotenv

load_dotenv()
from hermes_client import qualify_lead

lead = {
    "title": "Pizzería Demo Centro",
    "phone": "+57 300 111 2233",
    "website": None,
    "totalScore": 4.1,
    "reviewsCount": 87,
    "url": "https://maps.google.com/?cid=demo1",
    "description": "Pizza artesanal al horno de leña",
}

print("Calificando 1 lead de prueba vía Hermes... (puede tardar unos segundos)")
result = qualify_lead(lead, "Bogotá Colombia", "restaurantes")
print(json.dumps(result, ensure_ascii=False, indent=2))
