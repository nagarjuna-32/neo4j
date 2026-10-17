import logging
from fastapi import APIRouter, HTTPException, status
from backend.app.models import ChatRequest, ChatResponse
from backend.app.services.chat_service import chat_service

logger = logging.getLogger("codebrain.routes.chat")

router = APIRouter(tags=["AI Chat Assistant"])


@router.post("/chat", response_model=ChatResponse)
def handle_chat_message(request: ChatRequest) -> ChatResponse:
    """
    Context-Aware AI Chat Assistant endpoint:
    1. Classifies intent (direct_info, debugging, code_question, project_info, general).
    2. Retrieves bounded, parameterized graph evidence from Neo4j / In-Memory engine.
    3. Synthesizes an evidence-grounded answer using OpenAI (or deterministic fallback engine).
    4. Returns answer, structured evidence citations, suggested actions, and follow-up prompts.
    """
    if not request.message or not request.message.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message cannot be empty.",
        )

    try:
        response = chat_service.process_chat(request)
        return response
    except Exception as exc:
        logger.error(f"Error in chat endpoint: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat assistant processing error: {str(exc)}",
        )
