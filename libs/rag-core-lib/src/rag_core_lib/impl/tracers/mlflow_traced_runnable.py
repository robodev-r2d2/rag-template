"""MLflow traced runnable wrapper."""

from langchain_core.runnables import Runnable

from rag_core_lib.impl.settings.mlflow_settings import MlflowSettings
from rag_core_lib.tracers.traced_runnable import TracedRunnable


class MlflowTracedRunnable(TracedRunnable):
    """Thin wrapper to keep DI consistent when tracing runnables with MLflow."""

    def __init__(self, inner_chain: Runnable, settings: MlflowSettings):
        super().__init__(inner_chain, settings)
