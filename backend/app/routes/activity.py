from fastapi import APIRouter, Query
from typing import List
from backend.app.models import ActivityEvent
from backend.app.services.graph_service import graph_service

router = APIRouter(tags=["Activity Feed"])


@router.get("/activity", response_model=List[ActivityEvent])
def get_activity_feed(
    project_id: str = Query(default="PRJ-SENTINEL", description="Project ID"),
    limit: int = Query(default=15, ge=1, le=50, description="Max activities to return"),
) -> List[ActivityEvent]:
    """Return recent project-memory events and recorded modifications."""
    return graph_service.get_recent_activity(project_id=project_id, limit=limit)
