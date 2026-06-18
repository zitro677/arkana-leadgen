"""Enriquecimiento web de leads (v2): email + detección de chatbot en la web.

Visita la web del negocio (Scrapling con fallback a requests) y deriva:
  - email: primer email "limpio" encontrado (home y páginas de contacto).
  - has_site_chatbot: True si detecta la firma de un widget de chat/bot real.
Un simple link a WhatsApp NO cuenta como chatbot.
"""
import re
from urllib.parse import urljoin

# Firmas específicas de widgets de chat/bot (bajo riesgo de falso positivo).
CHATBOT_SIGNATURES = (
    "tawk.to",
    "widget.intercom.io",
    "client.crisp.chat",
    "tidio.co", "tidiochat",
    "js.driftt.com",
    "cdn.livechatinc.com",
    "static.zdassets.com", "zopim",
    "chatwoot",
    "landbot.io",
    "fb-customerchat",
    "wati.io",
    "manychat.com",
    "smartsupp.com",
    "wchat.freshchat.com", "freshchat",
    "userlike.com",
    "js.usemessages.com",
    "kommunicate.io",
    "config.gorgias.chat",
    "olark.com",
    "jivosite", "jivochat",
)

# Señales DOM genéricas de un widget de chat embebido (custom / self-hosted).
# Se exige >=2 distintas para evitar falsos positivos por una mención suelta.
_GENERIC_CHAT_SIGNALS = (
    "chat-window", "chatwindow", "chat-widget", "chatwidget",
    "chat-container", "chat-messages", "chat-message", "chat-input",
    "chatinput", "chat-launcher", "chat-bubble", "chat-popup",
    "chat-toggle", "chat-box", "chatbox", "chat-panel", "chat-header",
    "chatbot", "live-chat", "livechat",
)

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

# Subcadenas que indican que el "email" es basura (assets, placeholders, libs).
_JUNK = (
    "@2x", "@3x", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp",
    "example.com", "sentry.io", "@sentry", "wixpress.com", "godaddy",
    "yourdomain", "domain.com", "email.com", "@email", "test.com",
)

_CONTACT_PATHS = ("/contacto", "/contact", "/contactenos", "/contact-us", "/contacto.html")

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def detect_chatbot(html):
    """True si hay un widget de chat: proveedor conocido (1 firma) o
    widget propio/embebido (>=2 señales DOM genéricas de chat)."""
    low = (html or "").lower()
    if any(sig in low for sig in CHATBOT_SIGNATURES):
        return True
    hits = sum(1 for s in _GENERIC_CHAT_SIGNALS if s in low)
    return hits >= 2


def extract_emails(html):
    """Lista de emails 'limpios' (sin basura), en orden de aparición, sin duplicados."""
    found = []
    for raw in EMAIL_RE.findall(html or ""):
        e = raw.strip().lower()
        if any(j in e for j in _JUNK):
            continue
        if e not in found:
            found.append(e)
    return found


def _fetch_html(url, timeout=12):
    """Descarga el HTML. Intenta Scrapling (stealth); si falla, usa requests."""
    try:
        from scrapling.fetchers import Fetcher
        page = Fetcher.get(url, timeout=timeout)
        html = getattr(page, "html_content", None)
        if not html:
            html = str(page)
        return html or ""
    except Exception:
        pass
    try:
        import requests
        r = requests.get(url, timeout=timeout, headers={"User-Agent": _UA})
        return r.text or ""
    except Exception:
        return ""


def enrich_lead(lead, timeout=12):
    """Devuelve una copia del lead con 'email' y 'has_site_chatbot' añadidos.

    Escanea el chatbot sobre la UNIÓN de las páginas visitadas (home + contacto),
    porque el widget suele estar solo en la página de contacto.
    """
    out = dict(lead)
    out["email"] = ""
    out["has_site_chatbot"] = False
    website = lead.get("website")
    if not website:
        return out

    home = _fetch_html(website, timeout)
    has_bot = detect_chatbot(home)
    emails = extract_emails(home)

    # Visita páginas de contacto hasta tener email Y chatbot (o agotarlas).
    for path in _CONTACT_PATHS:
        if emails and has_bot:
            break
        h = _fetch_html(urljoin(website, path), timeout)
        if not h:
            continue
        if not has_bot:
            has_bot = detect_chatbot(h)
        if not emails:
            emails = extract_emails(h)

    out["has_site_chatbot"] = has_bot
    out["email"] = emails[0] if emails else ""
    return out
