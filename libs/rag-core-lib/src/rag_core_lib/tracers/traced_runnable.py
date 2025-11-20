"""Module for traced runnables using MLflow."""

import json
import logging
import uuid
from typing import Any, Optional

import mlflow
from langchain_core.runnables import Runnable, RunnableConfig, ensure_config

from rag_core_lib.impl.settings.mlflow_settings import MlflowSettings
from rag_core_lib.runnables.async_runnable import AsyncRunnable

RunnableInput = Any
RunnableOutput = Any


class TracedRunnable(AsyncRunnable[RunnableInput, RunnableOutput]):
    """Wrap a Runnable with MLflow tracing (inputs/outputs + session metadata)."""

    SESSION_ID_KEY = "session_id"
    METADATA_KEY = "metadata"

    def __init__(self, inner_chain: Runnable, settings: MlflowSettings):
        self._inner_chain = inner_chain
        self._settings = settings
        mlflow.set_tracking_uri(self._settings.tracking_uri)
        if self._settings.experiment_name:
            mlflow.set_experiment(self._settings.experiment_name)
        if self._settings.api_token:
            mlflow.set_registry_uri(self._settings.tracking_uri)

    async def ainvoke(
        self, chain_input: RunnableInput, config: Optional[RunnableConfig] = None, **kwargs: Any
    ) -> RunnableOutput:
        config = ensure_config(config)
        session_id = self._get_session_id(config)
        tags = {"session_id": session_id, "component": self._inner_chain.__class__.__name__}

        active = mlflow.active_run()
        try:
            if active:
                mlflow.start_run(run_id=active.info.run_id, nested=True, tags=tags)
            else:
                mlflow.start_run(run_name=self._inner_chain.__class__.__name__, tags=tags)

            try:
                mlflow.log_dict(
                    self._safe_pack({"input": self._serialize(chain_input), "config": config}),
                    "io.json",
                )
            except Exception:
                logging.getLogger(__name__).warning("Failed to log input to MLflow", exc_info=True)
            output = await self._inner_chain.ainvoke(chain_input, config=config)
            try:
                mlflow.log_dict(
                    self._safe_pack({"output": self._serialize(output)}),
                    "io.json",
                    artifact_path="outputs",
                )
            except Exception:
                logging.getLogger(__name__).warning("Failed to log output to MLflow", exc_info=True)
            return output
        finally:
            if not active:
                mlflow.end_run()

    def _get_session_id(self, config: Optional[RunnableConfig]) -> str:
        return config.get(self.METADATA_KEY, {}).get(self.SESSION_ID_KEY, str(uuid.uuid4()))

    def _serialize(self, obj: Any) -> Any:
        try:
            json.dumps(obj)
            return obj
        except Exception:
            return str(obj)

    def _safe_pack(self, payload: dict) -> dict:
        try:
            json.dumps(payload)
            return payload
        except Exception:
            return {"raw": str(payload)}
