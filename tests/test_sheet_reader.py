import sheet_reader as sr


def test_rows_to_leads_skips_header_and_maps():
    rows = [
        ["Empresa", "Ciudad", "Categoria", "Telefono", "Email", "Website",
         "Rating", "Reseñas", "Score", "Prioridad", "Señales", "Pitch", "MapsURL"],
        ["Pizza X", "Bogotá", "restaurantes", "+57 1", "a@x.com", "", "4.2",
         "80", "55", "alta", "no_website", "pitch", "http://m/x"],
    ]
    leads = sr.rows_to_leads(rows)
    assert len(leads) == 1
    assert leads[0]["email"] == "a@x.com"
    assert leads[0]["score"] == "55"
    assert leads[0]["empresa"] == "Pizza X"


def test_rows_to_leads_handles_short_rows():
    rows = [["Empresa"], ["Solo Nombre"]]
    leads = sr.rows_to_leads(rows)
    assert leads[0]["empresa"] == "Solo Nombre"
    assert leads[0]["email"] == ""
