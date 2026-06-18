---
name: arkana_lead_gen
description: Califica negocios locales por su madurez para automatización con IA (señales + scoring) y devuelve JSON estructurado para Arkana Tech.
version: 2.0.0
platforms: [linux]
metadata:
  hermes:
    category: sales
    tags: [leads, sales, qualification, arkana]
---

# SKILL: arkana_lead_gen

## Purpose
Califica negocios locales (scrapeados de Google Maps y enriquecidos con datos
de su web) por su disposición a automatización con IA, y devuelve JSON.

## CATEGORIES
- restaurantes
- inmobiliarias
- administracion_conjuntos
- talleres_mecanicos
- clinicas_dentales
- firmas_juridicas
- car_detailing
- landscaping_irrigation

## Qualification Signals (v2)
1. no_website: NO tiene website
2. no_site_chatbot: tiene website pero SIN chatbot detectado en ella
   (un simple link a WhatsApp NO cuenta como chatbot)
3. no_booking_system: sin URL de reserva/booking visible
4. email_found: se encontró un email de contacto
(no_website y no_site_chatbot son excluyentes)

## Output Schema (devolver SOLO este JSON, sin markdown)
{
  "empresa": string,
  "categoria": string,
  "ciudad": string,
  "telefono": string,
  "email": string,
  "website": string | null,
  "google_maps_url": string,
  "rating": float,
  "total_reviews": int,
  "señales": [string],
  "score": int,
  "pitch_angle": string,
  "prioridad": "alta" | "media" | "baja"
}

## Scoring Logic (v2)
- no_website: +40
- no_site_chatbot: +35
- no_booking_system: +15
- email_found: +10
Score >= 55 -> alta | 30-54 -> media | <30 -> baja

## pitch_angle
Frase corta y específica del dolor detectado + servicio Arkana sugerido
(ej. "Web con 87 reseñas pero sin chatbot — bot de reservas por WhatsApp 24/7").
