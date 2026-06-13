"""Anthropic SDK client wrapper.

Centralizes client construction so the agent loop never reaches for the SDK or
the API key directly. Model/thinking conventions live in the loop; see
`.claude/rules/llm-usage.md`.
"""

from anthropic import AsyncAnthropic

from app.core.config import settings


def get_anthropic_client() -> AsyncAnthropic:
    """Return an async Anthropic client.

    Passing the key from settings (which reads ``ANTHROPIC_API_KEY``) keeps it
    server-side; an empty value lets the SDK fall back to the environment.
    """
    return AsyncAnthropic(api_key=settings.anthropic_api_key or None)
