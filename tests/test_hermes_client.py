import hermes_client as hc


def test_extract_json_plain():
    assert hc._extract_json('{"score": 55}') == {"score": 55}


def test_extract_json_with_markdown_fences():
    txt = '```json\n{"score": 30, "prioridad": "media"}\n```'
    assert hc._extract_json(txt) == {"score": 30, "prioridad": "media"}


def test_extract_json_with_surrounding_text():
    txt = 'Aquí tienes el lead:\n{"empresa": "X"}\nGracias.'
    assert hc._extract_json(txt) == {"empresa": "X"}
