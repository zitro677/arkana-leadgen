"""Crea borradores en Gmail con la API (drafts.create) reutilizando el token OAuth."""
import os
import json
import base64
from email.mime.text import MIMEText

GOOGLE_TOKEN = os.getenv("GOOGLE_TOKEN", "/root/.hermes/google_token.json")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET",
                                 "/root/.hermes/google_client_secret.json")
_SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


def build_mime(to, subject, body, sender=None):
    """Arma el MIME y lo codifica en base64url para la API de Gmail."""
    msg = MIMEText(body, "plain", "utf-8")
    msg["to"] = to
    msg["subject"] = subject
    if sender:
        msg["from"] = sender
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    return {"message": {"raw": raw}}


def _load_creds():
    from google.oauth2.credentials import Credentials
    with open(GOOGLE_TOKEN, encoding="utf-8") as f:
        tok = json.load(f)
    if not tok.get("client_id") or not tok.get("client_secret"):
        with open(GOOGLE_CLIENT_SECRET, encoding="utf-8") as f:
            cs = json.load(f)
        inst = cs.get("installed") or cs.get("web") or {}
        tok.setdefault("client_id", inst.get("client_id"))
        tok.setdefault("client_secret", inst.get("client_secret"))
        tok.setdefault("token_uri", inst.get("token_uri", "https://oauth2.googleapis.com/token"))
    tok.setdefault("scopes", _SCOPES)
    return Credentials.from_authorized_user_info(tok)


def _service():
    from googleapiclient.discovery import build
    return build("gmail", "v1", credentials=_load_creds(), cache_discovery=False)


def get_self_email():
    """Email de la cuenta autenticada (para --to-self)."""
    try:
        prof = _service().users().getProfile(userId="me").execute()
        return prof.get("emailAddress", "")
    except Exception as e:
        print(f"  X  getProfile falló: {e}")
        return ""


def create_draft(to, subject, body):
    """Crea un borrador en Gmail. Devuelve True si se creó."""
    try:
        svc = _service()
        svc.users().drafts().create(
            userId="me", body=build_mime(to, subject, body)
        ).execute()
        return True
    except Exception as e:
        print(f"  X  draft error ({to}): {e}")
        return False
