"""Mock implementation of MlflowManager for testing."""

from unittest.mock import Mock

from langchain_core.language_models.llms import LLM
from langchain_core.prompts import ChatPromptTemplate


class MockMlflowManager:
    """Mock for the MlflowManager."""

    def __init__(self, managed_prompts: dict, llm: LLM, tracking_client: Mock | None = None, **kwargs):
        self._managed_prompts = managed_prompts
        self._llm = llm
        self._client = tracking_client

    def init_prompts(self):
        """Mock init_prompts method."""
        return None

    def get_base_llm(self, name: str) -> LLM:
        """Mock get_base_llm method."""
        return self._llm

    def get_base_prompt(self, name: str) -> ChatPromptTemplate:
        """Mock get_base_prompt method."""
        if name in self._managed_prompts:
            return self._managed_prompts[name]
        return ChatPromptTemplate.from_template("Default prompt template")
