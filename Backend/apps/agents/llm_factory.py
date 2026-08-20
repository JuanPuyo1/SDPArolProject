"""LLM Factory — unified instantiation for Claude, Ollama, and local/OpenAI-compatible models.

Provides model instantiation for all agents and orchestrators based on the
`LLM_PROVIDER` environment variable/Django setting.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.conf import settings
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from pydantic import BaseModel

if TYPE_CHECKING:
    pass


def get_active_provider() -> str:
    """Return the active LLM provider in lowercase: 'anthropic', 'ollama', 'local', or 'openai_compatible'."""
    return getattr(settings, 'LLM_PROVIDER', 'anthropic').strip().lower()


def get_active_model_name() -> str:
    """Return the configured model identifier for the active provider."""
    provider = get_active_provider()
    if provider == 'anthropic':
        return getattr(settings, 'ANTHROPIC_MODEL', 'claude-haiku-4-5-20251001')
    return getattr(settings, 'LOCAL_LLM_MODEL', 'qwen2.5:3b')


def get_base_chat_model(
    *,
    temperature: float | None = None,
    model: str | None = None,
    **kwargs: Any,
) -> BaseChatModel:
    """Instantiate and return a LangChain ChatModel based on LLM_PROVIDER.

    Supported providers:
      - 'anthropic' (default): ChatAnthropic using ANTHROPIC_API_KEY / ANTHROPIC_MODEL
      - 'ollama' / 'local': ChatOllama using LOCAL_LLM_MODEL / LOCAL_LLM_BASE_URL
      - 'openai_compatible': ChatOpenAI pointing to LOCAL_LLM_BASE_URL / LOCAL_LLM_MODEL
    """
    provider = get_active_provider()

    if provider == 'anthropic':
        from langchain_anthropic import ChatAnthropic

        model_name = model or getattr(settings, 'ANTHROPIC_MODEL', 'claude-haiku-4-5-20251001')
        api_key = getattr(settings, 'ANTHROPIC_API_KEY', '') or None
        temp = temperature if temperature is not None else 0.0

        model_kwargs = {'model': model_name, 'temperature': temp, **kwargs}
        if api_key:
            model_kwargs['api_key'] = api_key
        return ChatAnthropic(**model_kwargs)

    if provider in ('ollama', 'local'):
        from langchain_ollama import ChatOllama

        model_name = model or getattr(settings, 'LOCAL_LLM_MODEL', 'qwen2.5:3b')
        base_url = getattr(settings, 'LOCAL_LLM_BASE_URL', 'http://localhost:11434')
        temp = temperature if temperature is not None else getattr(settings, 'LOCAL_LLM_TEMPERATURE', 0.0)
        timeout = getattr(settings, 'LOCAL_LLM_TIMEOUT', 60.0)

        return ChatOllama(
            model=model_name,
            base_url=base_url,
            temperature=temp,
            timeout=timeout,
            **kwargs,
        )

    if provider == 'openai_compatible':
        from langchain_openai import ChatOpenAI

        model_name = model or getattr(settings, 'LOCAL_LLM_MODEL', 'qwen2.5:3b')
        base_url = getattr(settings, 'LOCAL_LLM_BASE_URL', 'http://localhost:11434/v1')
        temp = temperature if temperature is not None else getattr(settings, 'LOCAL_LLM_TEMPERATURE', 0.0)
        timeout = getattr(settings, 'LOCAL_LLM_TIMEOUT', 60.0)

        return ChatOpenAI(
            model=model_name,
            base_url=base_url,
            api_key='local',
            temperature=temp,
            timeout=timeout,
            **kwargs,
        )

    raise ValueError(
        f"Unsupported LLM_PROVIDER: {provider!r}. "
        "Supported values are: 'anthropic', 'ollama', 'local', 'openai_compatible'."
    )


def get_tool_calling_llm(
    tools: list[BaseTool],
    *,
    model: str | None = None,
    temperature: float | None = None,
) -> Runnable:
    """Return a chat model bound to tools for agent tool-calling loops."""
    base_llm = get_base_chat_model(temperature=temperature, model=model)
    return base_llm.bind_tools(tools)


def get_router_llm(
    schema: type[BaseModel],
    *,
    model: str | None = None,
    temperature: float | None = None,
) -> Runnable:
    """Return a chat model configured for structured output according to schema."""
    base_llm = get_base_chat_model(temperature=temperature, model=model)
    return base_llm.with_structured_output(schema)
