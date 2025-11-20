"""Evaluator that logs metrics and prompts to MLflow instead of Langfuse."""

import json
import logging
import math
import os
from asyncio import gather
from datetime import datetime
from uuid import uuid4

import mlflow
import ragas
from datasets import Dataset
from langchain_core.runnables import RunnableConfig
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import (
    answer_correctness,
    answer_relevancy,
    answer_similarity,
    context_entity_recall,
    context_precision,
    context_recall,
    faithfulness,
)
from ragas.run_config import RunConfig
from tqdm import tqdm

from rag_core_api.api_endpoints.chat import Chat
from rag_core_api.embeddings.embedder import Embedder
from rag_core_api.evaluator.evaluator import Evaluator
from rag_core_api.impl.settings.chat_history_settings import ChatHistorySettings
from rag_core_api.impl.settings.ragas_settings import RagasSettings
from rag_core_api.models.chat_request import ChatRequest
from rag_core_lib.impl.mlflow_manager.mlflow_manager import MlflowManager
from rag_core_lib.impl.settings.mlflow_settings import MlflowSettings
from rag_core_lib.impl.utils.async_threadsafe_semaphore import AsyncThreadsafeSemaphore

logger = logging.getLogger(__name__)


class MlflowRagasEvaluator(Evaluator):
    """Evaluate questions using Ragas, log results to MLflow."""

    METRICS = [
        faithfulness,
        answer_relevancy,
        context_precision,
        context_recall,
        answer_correctness,
        context_entity_recall,
        answer_similarity,
    ]

    def __init__(
        self,
        chat_endpoint: Chat,
        mlflow_manager: MlflowManager,
        settings: RagasSettings,
        embedder: Embedder,
        semaphore: AsyncThreadsafeSemaphore,
        chat_history_config: ChatHistorySettings,
        chat_llm,
        mlflow_settings: MlflowSettings,
    ) -> None:
        self._chat_history_config = chat_history_config
        self._chat_endpoint = chat_endpoint
        self._settings = settings
        self._embedder = embedder
        self._semaphore = semaphore
        self._metrics = [faithfulness, answer_relevancy, context_precision]
        self._mlflow_settings = mlflow_settings

        mlflow.set_tracking_uri(self._mlflow_settings.tracking_uri)
        if self._mlflow_settings.experiment_name:
            mlflow.set_experiment(self._mlflow_settings.experiment_name)

        self._llm_wrapped = LangchainLLMWrapper(chat_llm, RunConfig())
        mlflow_manager.init_prompts()

    async def aevaluate(self) -> None:
        """Run evaluations for the configured dataset."""
        try:
            evaluation_dataset = self._load_dataset()
            if evaluation_dataset is None:
                return
            await self._aauto_answer_generation4evaluation_questions(evaluation_dataset)
        except Exception:
            logger.exception("Failed to evaluate questions")

    async def _aauto_answer_generation4evaluation_questions(self, dataset: Dataset) -> None:
        session_id = str(uuid4())
        generation_time = datetime.now()
        experiment_name = f'eval-{self._settings.evaluation_dataset_name}-{generation_time.strftime("%Y%m%d-%H%M%S")}'
        config = RunnableConfig(
            tags=[],
            callbacks=[],
            recursion_limit=25,
            metadata={"session_id": session_id},
        )

        active = mlflow.active_run()
        try:
            if active:
                mlflow.start_run(run_id=active.info.run_id, nested=True)
            else:
                mlflow.start_run(run_name=experiment_name, tags={"component": "rag-eval"})
            mlflow.log_params(
                {
                    "dataset": self._settings.evaluation_dataset_name,
                    "dataset_file": self._settings.dataset_filename,
                    "model": self._settings.model,
                }
            )
            evaluate_tasks = [
                self._aevaluate_question(item, experiment_name, config) for item in tqdm(dataset)
            ]
            await gather(*evaluate_tasks)
        finally:
            if not active:
                mlflow.end_run()

    async def _aevaluate_question(self, item, experiment_name: str, config: RunnableConfig):
        async with self._semaphore:
            chat_request = ChatRequest(message=item["question"])

            with mlflow.start_run(
                run_name=f"{experiment_name}-{item.get('id', uuid4())}",
                nested=True,
                tags={"question_id": str(item.get("id", ""))},
            ):
                try:
                    response = await self._chat_endpoint.achat(config["metadata"]["session_id"], chat_request)
                except Exception:
                    logger.exception("Error while answering question %s", item.get("question"))
                    response = None
                output = {
                    "answer": response.answer if response else None,
                    "documents": (
                        [x.page_content for x in response.citations] if response and response.citations else None
                    ),
                }
                mlflow.log_dict(
                    {
                        "question": item.get("question"),
                        "expected": item.get("ground_truth"),
                        "answer": output["answer"],
                        "documents": output["documents"],
                    },
                    "qa.json",
                )

                if response and response.citations:
                    eval_data = Dataset.from_dict(
                        {
                            "question": [item.get("question")],
                            "answer": [output["answer"]],
                            "contexts": [output["documents"]],
                            "ground_truth": [item.get("ground_truth")],
                        }
                    )
                    result = ragas.evaluate(
                        eval_data,
                        metrics=self.METRICS,
                        llm=self._llm_wrapped,
                        embeddings=self._embedder,
                    )
                    for metric, score in result.scores[0].items():
                        if math.isnan(score):
                            score = 0.0
                        mlflow.log_metric(metric, score)
                else:
                    for metric in self.METRICS:
                        mlflow.log_metric(metric.name, 0.0)

    def _load_dataset(self) -> Dataset | None:
        if not os.path.exists(self._settings.dataset_filename):
            logger.error("Dataset file does not exist. Filename: %s", self._settings.dataset_filename)
            return None
        with open(self._settings.dataset_filename, "r", encoding="utf-8") as file:
            data = json.load(file)
        return Dataset.from_list(data)
