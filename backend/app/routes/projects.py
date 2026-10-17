from fastapi import APIRouter
from typing import List, Dict, Any
from backend.app.services.graph_service import graph_service

router = APIRouter(tags=["Projects"])


@router.get("/projects", response_model=List[Dict[str, Any]])
def get_projects() -> List[Dict[str, Any]]:
    """Return available projects."""
    return graph_service.get_projects()
