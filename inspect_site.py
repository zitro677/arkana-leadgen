"""Diagnóstico: baja una web con el mismo Scrapling de enrich y muestra
pistas de chatbot (tokens 'chat', src de scripts, globals de widgets conocidos).

Uso: python inspect_site.py https://sitio.com/contacto/
"""
import re
import sys
from urllib.parse import urljoin

from enrich import _fetch_html, detect_chatbot, extract_emails, _CONTACT_PATHS

base = sys.argv[1] if len(sys.argv) > 1 else "https://arkanatech.tech/"
urls = [base] + [urljoin(base, p) for p in _CONTACT_PATHS]

GLOBALS = ["tawk_api", "tawk.to", "intercom", "$crisp", "crisp.chat", "tidio",
           "drift", "wati", "chatwoot", "botpress", "voiceflow", "dialogflow",
           "landbot", "manychat", "smartsupp", "freshchat", "userlike",
           "usemessages", "kommunicate", "gorgias", "olark", "jivo",
           "chatlio", "chaport", "messenger", "whatsapp", "wa.me", "n8n", "webhook"]

seen = set()
for u in urls:
    html = _fetch_html(u)
    if not html or u in seen:
        continue
    seen.add(u)
    low = html.lower()
    print(f"\n=== {u}  (len={len(html)}) ===")
    print("  emails:", extract_emails(html)[:5])
    print("  detect_chatbot:", detect_chatbot(html))
    chat_tokens = sorted(set(re.findall(r"[a-z0-9.\-]*chat[a-z0-9.\-]*", low)))
    print("  chat-tokens:", chat_tokens[:15])
    srcs = sorted(set(re.findall(r'src=["\']([^"\']+)["\']', html)))
    print("  script/iframe srcs:", [s for s in srcs if "http" in s][:15])
    hits = [g for g in GLOBALS if g in low]
    print("  keyword hits:", hits)
