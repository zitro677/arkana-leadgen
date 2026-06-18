---
name: arkana_lead_gen
description: Califica negocios locales por su madurez para automatización con IA (señales + scoring) y devuelve JSON estructurado para Arkana Tech.
version: 1.0.0
platforms: [linux]
metadata:
  hermes:
    category: sales
    tags: [leads, sales, qualification, arkana]
---

# SKILL: arkana_lead_gen

## Purpose
Califica negocios locales (previamente scrapeados de Google Maps) por su
disposición a automatización con IA, y devuelve JSON estructurado.

## CATEGORIES
- restaurantes
- inmobiliarias
- administracion_conjuntos
- talleres_mecanicos
- clinicas_dentales
- firmas_juridicas
- car_detailing
- landscaping_irrigation

## Qualification Signals (v1 — solo estas 3 son evaluables sin reviews)
1. no_website: campo website vacío o null
2. no_whatsapp_bot: la descripción GMB no menciona chatbot/WhatsApp/bot
3. no_booking_system: no hay URL de reserva/booking visible

(Las señales poor_review_response y outdated_hours son v2; NO sumarlas en v1.)

## Output Schema (devolver SOLO este JSON, sin markdown)
{
  "empresa": string,
  "categoria": string,
  "ciudad": string,
  "telefono": string,
  "website": string | null,
  "google_maps_url": string,
  "rating": float,
  "total_reviews": int,
  "señales": [string],
  "score": int,
  "pitch_angle": string,
  "prioridad": "alta" | "media" | "baja"
}

## Scoring Logic (v1)
- no_website: +30
- no_whatsapp_bot: +25
- no_booking_system: +15
Score >= 55 -> alta | 30-54 -> media | <30 -> baja

## pitch_angle
Frase corta y específica del dolor detectado + servicio Arkana sugerido
(ej. "Sin web con 80 reseñas — bot de reservas por WhatsApp 24/7").
