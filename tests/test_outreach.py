import outreach as o


def test_to_int():
    assert o.to_int("55") == 55
    assert o.to_int("55.0") == 55
    assert o.to_int("") == 0
    assert o.to_int("abc") == 0


def test_candidates_filters_email_score_and_drafted():
    leads = [
        {"email": "a@x.com", "score": "60"},   # ok
        {"email": "",        "score": "90"},   # sin email -> fuera
        {"email": "b@x.com", "score": "40"},   # score bajo -> fuera
        {"email": "c@x.com", "score": "55"},   # ya drafteado -> fuera
    ]
    out = o.candidates(leads, drafted={"c@x.com"}, min_score=50)
    assert [l["email"] for l in out] == ["a@x.com"]
