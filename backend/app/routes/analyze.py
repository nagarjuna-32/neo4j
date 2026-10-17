from fastapi import APIRouter, HTTPException, status
from backend.app.models import AnalyzeRequest, AnalyzeResponse
from backend.app.services.graph_service import graph_service
from backend.app.services.ai_service import ai_service

router = APIRouter(tags=["Contextual Debugging"])


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze_question(request: AnalyzeRequest) -> AnalyzeResponse:
    """
    Contextual debugging assistant:
    1. Retrieves connected decisions, bugs, fixes, dependencies, and tests via Cypher graph traversal.
    2. Constructs grounded evidence package with explicit citations.
    3. Invokes configured AI model (or deterministic fallback) with strict grounding.
    """
    try:
        # Step 1: Graph context retrieval
        context = graph_service.retrieve_context_for_analysis(
            project_id=request.project_id,
            question=request.question,
            target_component=request.component,
        )

        # Step 2: AI reasoning & synthesis
        response = ai_service.analyze_question(
            project_id=request.project_id,
            question=request.question,
            component_name=request.component,
            context=context,
        )

        return response
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analysis pipeline error: {str(exc)}",
        )
