# widgets/ai_assistant/__init__.py
from widgets.ai_assistant.chat_panel import AIChatPanel
from widgets.ai_assistant.ai_service import explain_query_ai
from widgets.ai_assistant.offline_analyzer import analyze_sql_locally

__all__ = ["AIChatPanel", "explain_query_ai", "analyze_sql_locally"]
