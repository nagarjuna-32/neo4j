from fastapi import APIRouter
from backend.app.config import settings
from backend.app.database import db_manager
from backend.app.models import HealthResponse

router = APIRouter(tags=["Health & Diagnostics"])


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    neo4j_connected = db_manager.is_connected
    neo4j_status = (
        "Connected to Neo4j instance"
        if neo4j_connected
        else f"Neo4j offline ({db_manager.connection_error or 'Credentials not provided in .env'})"
    )

    ai_configured = settings.is_openai_configured
    ai_status = (
        f"Configured with OpenAI ({settings.OPENAI_MODEL})"
        if ai_configured
        else "Deterministic Evidence-Grounded Engine active (OPENAI_API_KEY not configured)"
    )

    storage_backend = "Neo4j AuraDB / Live Cypher Engine" if neo4j_connected else "Local Graph Engine (In-Memory Traversal)"

    diagnostics = []
    if neo4j_connected:
        diagnostics.append(f"Active Neo4j URI: {settings.NEO4J_URI}")
        diagnostics.append(f"Target Database: {settings.NEO4J_DATABASE}")
    else:
        diagnostics.append("Tip: To connect to live Neo4j AuraDB, set NEO4J_URI, NEO4J_USERNAME, and NEO4J_PASSWORD in your .env file.")
        diagnostics.append("Running in self-contained Graph Memory mode for instant local testing and evaluation.")

    if ai_configured:
        diagnostics.append(f"OpenAI Model: {settings.OPENAI_MODEL} with temperature {settings.OPENAI_TEMPERATURE}")
    else:
        diagnostics.append("Tip: To enable OpenAI synthesis, set OPENAI_API_KEY in your .env file.")

    return HealthResponse(
        api_status="healthy",
        neo4j_status=neo4j_status,
        neo4j_connected=neo4j_connected,
        ai_status=ai_status,
        ai_configured=ai_configured,
        ai_model=settings.OPENAI_MODEL if ai_configured else "deterministic_graph_engine",
        storage_backend=storage_backend,
        version=settings.VERSION,
        diagnostics=diagnostics,
    )
