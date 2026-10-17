from fastapi import APIRouter, Query
from backend.app.models import GraphResponse
from backend.app.services.graph_service import graph_service

router = APIRouter(tags=["Knowledge Graph"])


@router.get("/graph", response_model=GraphResponse)
def get_graph(project_id: str = Query(default="PRJ-SENTINEL", description="Project ID to visualize")) -> GraphResponse:
    """Return nodes and directed relationships for visualization in Cytoscape.js."""
    return graph_service.get_graph(project_id=project_id)
