"""LLM client abstraction — switchable between Claude, OpenAI, and Mock.

Provides a unified async interface so agent nodes don't hardcode a provider.
The MockLLMClient returns deterministic canned responses for testing the
state machine's control flow without real API calls.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from app.core.config import settings

logger = logging.getLogger(__name__)


class BaseLLMClient(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Send a prompt to the LLM and return the response text."""


class ClaudeLLMClient(BaseLLMClient):
    """Anthropic Claude via langchain-anthropic."""

    def __init__(self, model: str = "claude-sonnet-4-20250514") -> None:
        from langchain_anthropic import ChatAnthropic

        self._llm = ChatAnthropic(
            model=model,
            api_key=settings.ANTHROPIC_API_KEY,
            max_tokens=4096,
        )

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        from langchain_core.messages import HumanMessage, SystemMessage

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]
        response = await self._llm.ainvoke(messages)
        return str(response.content)


class OpenAILLMClient(BaseLLMClient):
    """OpenAI GPT via langchain-openai."""

    def __init__(self, model: str = "gpt-4o") -> None:
        from langchain_openai import ChatOpenAI

        self._llm = ChatOpenAI(
            model=model,
            api_key=settings.OPENAI_API_KEY,
            max_tokens=4096,
        )

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        from langchain_core.messages import HumanMessage, SystemMessage

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]
        response = await self._llm.ainvoke(messages)
        return str(response.content)


class MockLLMClient(BaseLLMClient):
    """Returns deterministic canned responses for testing.

    Configure via constructor:
    - fix_content: the proposed fix the mock returns (can be a "good" or "bad" fix)
    - diagnosis_text: the mock diagnosis text
    """

    def __init__(
        self,
        fix_content: str = "",
        diagnosis_text: str = "Mock diagnosis: logic error detected in the function.",
    ) -> None:
        self.fix_content = fix_content
        self.diagnosis_text = diagnosis_text
        self.call_log: list[dict[str, str]] = []

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        self.call_log.append({
            "system_prompt": system_prompt[:100],
            "user_prompt": user_prompt[:100],
        })

        # Detect whether this is an Analyze or Propose call
        sp_lower = system_prompt.lower()
        if "diagnose" in sp_lower or "analyze" in sp_lower or "root cause" in sp_lower:
            return self.diagnosis_text
        else:
            # Propose call — return the configured fix
            return self.fix_content


def get_llm_client(provider: str = "mock") -> BaseLLMClient:
    """Factory: returns the configured LLM client.

    Args:
        provider: "claude" | "openai" | "mock"

    Returns:
        An instance of the requested LLM client.

    Raises:
        ValueError: If the provider is not recognized.
    """
    if provider == "claude":
        return ClaudeLLMClient()
    elif provider == "openai":
        return OpenAILLMClient()
    elif provider == "mock":
        return MockLLMClient()
    else:
        raise ValueError(f"Unknown LLM provider: {provider!r}")
