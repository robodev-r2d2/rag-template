"""MLflow-based prompt and model manager."""

import logging
from typing import Optional

import mlflow
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.language_models.llms import LLM

from rag_core_lib.impl.settings.mlflow_settings import MlflowSettings

logger = logging.getLogger(__name__)


class MlflowManager:
    """Manage prompts and model config using MLflow for tracking/versioning."""

    def __init__(
        self,
        settings: MlflowSettings,
        managed_prompts: dict[str, ChatPromptTemplate],
        llm: LLM,
    ):
        self._settings = settings
        self._managed_prompts = managed_prompts
        self._llm = llm

        mlflow.set_tracking_uri(self._settings.tracking_uri)
        if self._settings.experiment_name:
            mlflow.set_experiment(self._settings.experiment_name)
        if self._settings.api_token:
            mlflow.set_registry_uri(self._settings.tracking_uri)

    def init_prompts(self) -> None:
        """Log current prompt definitions to MLflow for versioning."""
        if not self._managed_prompts:
            return
        active = mlflow.active_run()
        try:
            if active:
                run = mlflow.start_run(run_id=active.info.run_id, nested=True)
            else:
                run = mlflow.start_run(run_name="prompt-sync", tags={"component": "prompt-sync"})
            for name, prompt in self._managed_prompts.items():
                mlflow.log_dict(self._prompt_to_dict(prompt), f"prompts/{name}.json")
        except Exception:
            logger.exception("Failed to log prompts to MLflow")
        finally:
            if not active:
                mlflow.end_run()

    def get_base_llm(self, name: str) -> LLM:
        """Return the configured LLM (no remote override)."""
        return self._llm

    def get_base_prompt(self, name: str) -> ChatPromptTemplate:
        """Return the managed prompt by name."""
        prompt = self._managed_prompts.get(name)
        if prompt:
            prompt.metadata = {"mlflow_prompt_name": name}
            return prompt

        logger.error("Prompt '%s' not found. Using fallback identity prompt.", name)
        return ChatPromptTemplate.from_messages([])

    def _prompt_to_dict(self, prompt: ChatPromptTemplate) -> list[dict]:
        try:
            messages = []
            for msg in prompt.messages:
                template = getattr(msg, "prompt", msg)
                entry = {
                    "type": msg.__class__.__name__,
                    "template": getattr(template, "template", str(template)),
                }
                messages.append(entry)
            return messages
        except Exception:
            return [{"raw": str(prompt)}]
