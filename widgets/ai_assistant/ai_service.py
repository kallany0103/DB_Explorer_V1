# widgets/ai_assistant/ai_service.py
"""
AI Service for SQL Code Explanation and Chat.
Supports:
- OpenAI (gpt-4o, gpt-4o-mini, etc.)
- Google Gemini (gemini-1.5-flash, gemini-2.0-flash, etc. via Gemini REST API)
- Anthropic Claude (claude-3-5-sonnet, etc.)
- Ollama / Local LLM (OpenAI-compatible /v1/chat/completions)
- Custom OpenAI-compatible endpoints
- Graceful offline fallback when no API key or offline mode is selected
"""

import json
from typing import Dict, Any, List, Optional
import httpx
from widgets.ai_assistant.offline_analyzer import analyze_sql_locally


SYSTEM_PROMPT = """You are an expert Database Architect and SQL Performance Tuning Assistant (similar to Toad for Oracle's AI assistant).
Your goal is to clearly and concisely explain the provided SQL query and assist the developer.

When asked to explain a query, structure your response cleanly with markdown and include:
1. A brief summary of what the query accomplishes.
2. **Components**:
   - Explanation of key clauses, projection list (`SELECT`), functions, and tables involved.
3. **Relationships**:
   - Joins, foreign key references, subqueries, or cross-table connections (or state if it's single table).
4. **Performance Considerations**:
   - Potential bottlenecks (e.g. `SELECT *`, Cartesian products, missing indexes on WHERE/JOIN columns, full table scans, sorting overhead) and actionable suggestions.

Keep your explanations concise, professional, and visually easy to read.
"""


def explain_query_ai(
    sql: str,
    ai_settings: Dict[str, Any],
    chat_history: Optional[List[Dict[str, str]]] = None,
    user_prompt: Optional[str] = None,
    db_type: str = "GENERIC"
) -> str:
    """
    Explains the SQL query using the configured AI provider.
    If no API key is set or call fails, falls back gracefully.
    """
    provider = (ai_settings.get("ai_provider") or "OpenAI").strip()
    api_key = (ai_settings.get("ai_api_key") or "").strip()
    base_url = (ai_settings.get("ai_base_url") or "").strip()
    model = (ai_settings.get("ai_model") or "").strip()

    # If no provider API key and not a local endpoint, use local offline analyzer
    is_local_ollama = "ollama" in provider.lower() or "localhost" in base_url or "127.0.0.1" in base_url
    if not api_key and not is_local_ollama:
        if user_prompt and user_prompt.strip().lower() not in ("explain", "explain this query", "explain code using ai"):
            return (
                "⚠️ **API Key Required for Interactive Chat**\n\n"
                "Please configure an API Key (OpenAI, Gemini, Claude, or Ollama) in **Preferences → AI Assistant** "
                "to ask arbitrary follow-up questions.\n\n"
                f"**Local Analysis of your SQL:**\n\n{analyze_sql_locally(sql, db_type)}"
            )
        return analyze_sql_locally(sql, db_type)

    # Determine message prompt
    if user_prompt:
        actual_user_message = f"SQL Query (Dialect: {db_type}):\n```sql\n{sql}\n```\n\nUser Question: {user_prompt}"
    else:
        actual_user_message = f"Please explain this {db_type} SQL code:\n```sql\n{sql}\n```"

    try:
        if "gemini" in provider.lower():
            return _call_gemini(api_key, model or "gemini-1.5-flash", actual_user_message, chat_history)
        elif "claude" in provider.lower() or "anthropic" in provider.lower():
            return _call_anthropic(api_key, model or "claude-3-5-sonnet-20241022", actual_user_message, chat_history)
        else:
            # OpenAI or OpenAI-compatible (Ollama, vLLM, LMStudio, Azure OpenAI)
            endpoint = base_url if base_url else "https://api.openai.com/v1"
            if not endpoint.endswith("/v1") and not endpoint.endswith("/v1/"):
                endpoint = endpoint.rstrip("/") + "/v1"
            default_model = "llama3" if is_local_ollama else "gpt-4o-mini"
            return _call_openai_compatible(
                api_key=api_key or "ollama",
                base_url=endpoint,
                model=model or default_model,
                user_message=actual_user_message,
                chat_history=chat_history
            )
    except Exception as e:
        error_msg = str(e)
        offline_fallback = analyze_sql_locally(sql, db_type)
        return (
            f"⚠️ **AI Service Error**: `{error_msg}`\n\n"
            f"> *(Showing local offline analysis instead)*\n\n"
            f"{offline_fallback}"
        )


def _call_openai_compatible(
    api_key: str,
    base_url: str,
    model: str,
    user_message: str,
    chat_history: Optional[List[Dict[str, str]]] = None
) -> str:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if chat_history:
        for msg in chat_history:
            messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
    messages.append({"role": "user", "content": user_message})

    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
    }

    with httpx.Client(timeout=30.0) as client:
        resp = client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


def _call_gemini(
    api_key: str,
    model: str,
    user_message: str,
    chat_history: Optional[List[Dict[str, str]]] = None
) -> str:
    clean_model = model if model else "gemini-1.5-flash"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{clean_model}:generateContent?key={api_key}"

    contents = []
    if chat_history:
        for msg in chat_history:
            role = "user" if msg.get("role") == "user" else "model"
            contents.append({
                "role": role,
                "parts": [{"text": msg.get("content", "")}]
            })

    contents.append({
        "role": "user",
        "parts": [{"text": f"{SYSTEM_PROMPT}\n\n{user_message}"}]
    })

    payload = {
        "contents": contents,
        "generationConfig": {
            "temperature": 0.2
        }
    }

    with httpx.Client(timeout=30.0) as client:
        resp = client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        candidates = data.get("candidates", [])
        if candidates and "content" in candidates[0]:
            parts = candidates[0]["content"].get("parts", [])
            if parts:
                return parts[0].get("text", "")
        return "No response generated by Gemini."


def _call_anthropic(
    api_key: str,
    model: str,
    user_message: str,
    chat_history: Optional[List[Dict[str, str]]] = None
) -> str:
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }

    messages = []
    if chat_history:
        for msg in chat_history:
            messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
    messages.append({"role": "user", "content": user_message})

    payload = {
        "model": model or "claude-3-5-sonnet-20241022",
        "system": SYSTEM_PROMPT,
        "messages": messages,
        "max_tokens": 2048,
        "temperature": 0.2
    }

    with httpx.Client(timeout=30.0) as client:
        resp = client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        content = data.get("content", [])
        if content and isinstance(content, list):
            return content[0].get("text", "")
        return "No response generated by Claude."
