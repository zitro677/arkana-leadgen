import base64
from email import message_from_bytes

import gmail_client as gc


def test_build_mime_roundtrips_to_subject_and_utf8_body():
    payload = gc.build_mime("dest@x.com", "Asunto Demo", "Hola cuerpo áéíóú ñ")
    raw = base64.urlsafe_b64decode(payload["message"]["raw"].encode())
    msg = message_from_bytes(raw)
    assert msg["To"] == "dest@x.com"
    assert msg["Subject"] == "Asunto Demo"
    body = msg.get_payload(decode=True).decode("utf-8")
    assert "Hola cuerpo áéíóú ñ" in body
