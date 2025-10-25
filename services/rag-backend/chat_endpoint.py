import logging
from langchain_core.runnables import RunnableConfig

from rag_core_api.api_endpoints.chat import Chat
from rag_core_api.models.chat_request import ChatRequest
from rag_core_api.models.chat_response import ChatResponse
from rag_core_api.security.models import UserContext
from rag_core_lib.impl.settings.access_control_settings import AccessControlSettings
from rag_core_lib.tracers.traced_runnable import TracedRunnable

logger = logging.getLogger(__name__)


class UseCaseChat(Chat):
    def __init__(self, chat_graph: TracedRunnable):
        self._chat_graph = chat_graph

    async def achat(
        self,
        session_id: str,
        chat_request: ChatRequest,
        user_context: UserContext,
    ) -> ChatResponse:
        access_settings = AccessControlSettings()
        filter_kwargs = {access_settings.metadata_key: sorted(user_context.allowed_groups(access_settings))}

        config = RunnableConfig(
            tags=[],
            callbacks=None,
            recursion_limit=25,
            metadata={"session_id": session_id, "filter_kwargs": filter_kwargs},
        )

        logger.info("Hold onto your hats, folks! The chat endpoint is now powered by UseCaseChat!")

        return await self._chat_graph.ainvoke(chat_request, config)
