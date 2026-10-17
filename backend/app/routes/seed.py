from fastapi import APIRouter
from typing import Dict, Any
from backend.app.services.graph_service import graph_service

router = APIRouter(tags=["Demo Seeding"])


@router.post("/seed")
def seed_demo_graph() -> Dict[str, Any]:
    """
    Seed the complete synthetic demo graph ('Sentinel Demo App') using idempotent Cypher MERGE queries.
    """
    result = graph_service.seed_data()
    return result
