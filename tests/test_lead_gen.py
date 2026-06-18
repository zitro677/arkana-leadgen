import lead_gen as lg


def test_filter_qualified_keeps_high_scores():
    leads = [{"score": 55}, {"score": 40}, {"score": 70}]
    out = lg.filter_qualified(leads, min_score=55)
    assert [l["score"] for l in out] == [55, 70]


def test_lead_key_prefers_url():
    assert lg.lead_key({"url": "u1", "phone": "p1"}) == "u1"


def test_lead_key_falls_back_to_phone():
    assert lg.lead_key({"phone": "p1"}) == "p1"


def test_mock_data_shape():
    rows = lg._mock_data("restaurantes Bogotá")
    assert len(rows) >= 1
    assert "title" in rows[0] and "url" in rows[0]
