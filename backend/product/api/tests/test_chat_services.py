from unittest.mock import MagicMock, patch

from flask import Flask

from chat.services import get_chat_services, reset_chat_services


def test_chat_services_are_cached_per_flask_app():
    app = Flask(__name__)

    with app.app_context():
        first = get_chat_services()
        second = get_chat_services()

    assert first is second


def test_reset_chat_services_clears_app_cache():
    app = Flask(__name__)

    with app.app_context():
        first = get_chat_services()
        reset_chat_services(app)
        second = get_chat_services()

    assert first is not second


def test_get_agent_reuses_cached_agent():
    app = Flask(__name__)
    agent = MagicMock()

    with app.app_context():
        services = get_chat_services()
        with patch("chat.services.get_llm_client", return_value=MagicMock()):
            with patch("chat.services.get_embedding_client", return_value=MagicMock()):
                with patch("chat.services.create_agent", return_value=agent) as create_agent:
                    assert services.get_agent() is agent
                    assert services.get_agent() is agent

    create_agent.assert_called_once()


def test_get_rag_tools_uses_factory_clients():
    app = Flask(__name__)
    llm = MagicMock()
    embedding = MagicMock()

    with app.app_context():
        services = get_chat_services()
        with patch("chat.services.get_llm_client", return_value=llm):
            with patch("chat.services.get_embedding_client", return_value=embedding):
                tools = services.get_rag_tools()

    assert tools.llm_client is llm
    assert tools.embedding_client is embedding
