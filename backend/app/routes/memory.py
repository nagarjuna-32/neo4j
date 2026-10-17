from fastapi import APIRouter, HTTPException, status
from backend.app.models import MemoryCaptureRequest, MemoryCaptureResponse
from backend.app.services.graph_service import graph_service

router = APIRouter(tags=["Project Memory"])


@router.post("/memory", response_model=MemoryCaptureResponse, status_code=status.HTTP_201_CREATED)
def capture_memory(payload: MemoryCaptureRequest) -> MemoryCaptureResponse:
    """
    Persist an engineering decision or bug into Neo4j project memory with automatic relationship linkage.
    """
    try:
        if payload.memory_type == "decision":
            entity_id, paths = graph_service.add_memory_decision(
                project_id=payload.project_id,
                title=payload.title,
                affected_component=payload.affected_component,
                description=payload.description or "",
                reason=payload.reason,
                dependency=payload.dependency,
                author=payload.author,
                source=payload.source,
            )
            return MemoryCaptureResponse(
                success=True,
                message=f"Technical decision {entity_id} successfully persisted to project memory.",
                entity_id=entity_id,
                entity_type="Decision",
                connected_paths=paths,
            )
        elif payload.memory_type == "bug":
            entity_id, paths = graph_service.add_memory_bug(
                project_id=payload.project_id,
                title=payload.title,
                affected_component=payload.affected_component,
                symptom=payload.symptom or "",
                root_cause=payload.root_cause,
                resolution=payload.resolution,
                status=payload.status or "RESOLVED",
                verification=payload.verification,
                source=payload.source,
            )
            return MemoryCaptureResponse(
                success=True,
                message=f"Incident/Bug {entity_id} successfully persisted to project memory.",
                entity_id=entity_id,
                entity_type="Bug",
                connected_paths=paths,
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported memory_type '{payload.memory_type}'. Must be 'decision' or 'bug'.",
            )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to persist memory: {str(exc)}",
        )
