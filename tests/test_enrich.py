import enrich


def test_detect_chatbot_tawk():
    html = '<script src="https://embed.tawk.to/abc123/default"></script>'
    assert enrich.detect_chatbot(html) is True


def test_detect_chatbot_intercom():
    assert enrich.detect_chatbot('<script src="https://widget.intercom.io/x.js">') is True


def test_detect_chatbot_whatsapp_link_is_not_bot():
    # Un simple link a WhatsApp NO cuenta como chatbot.
    assert enrich.detect_chatbot('<a href="https://wa.me/573001112233">Escríbenos</a>') is False


def test_detect_chatbot_custom_widget():
    # Chatbot propio/self-hosted (como arkanatech): varias señales DOM de chat.
    html = ('<div class="ark-chat-window"><div class="chat-messages"></div>'
            '<input class="chat-input"></div>')
    assert enrich.detect_chatbot(html) is True


def test_detect_chatbot_single_mention_not_bot():
    # Una sola mención suelta de "chatbot" NO debe contar (evita falso positivo).
    assert enrich.detect_chatbot('<p>Ofrecemos un chatbot para tu negocio</p>') is False


def test_detect_chatbot_none():
    assert enrich.detect_chatbot('<html><body>Bienvenido</body></html>') is False


def test_extract_emails_basic():
    assert enrich.extract_emails("Contacto: info@negocio.com") == ["info@negocio.com"]


def test_extract_emails_dedupe_and_lower():
    out = enrich.extract_emails("A@Negocio.com y a@negocio.com")
    assert out == ["a@negocio.com"]


def test_extract_emails_filters_junk():
    assert enrich.extract_emails("logo@2x.png y x@sentry.io") == []


def test_enrich_lead_without_website():
    out = enrich.enrich_lead({"title": "X", "website": None})
    assert out["email"] == "" and out["has_site_chatbot"] is False
