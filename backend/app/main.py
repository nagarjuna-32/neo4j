import logging
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from backend.app.config import settings
from backend.app.database import db_manager
from backend.app.services.graph_service import graph_service
from backend.app.routes import health, seed, projects, graph, memory, analyze, impact, activity

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("codebrain.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: attempt Neo4j connection
    logger.info("Initializing CodeBrain AI...")
    connected = db_manager.initialize()
    if connected:
        logger.info("Neo4j database connected. Schema verified.")
        if settings.AUTO_SEED:
            logger.info("AUTO_SEED is enabled. Seeding demo baseline...")
            graph_service.seed_data()
        else:
            logger.info("Automatic startup seeding disabled. Demo data can be seeded on-demand via POST /api/seed or UI button.")
    else:
        logger.info("Neo4j offline. Running in Local Graph Memory mode for instant evaluation.")

    yield

    # Shutdown
    logger.info("Shutting down CodeBrain AI...")
    db_manager.close()


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="CodeBrain AI — Every Bug Has a History (Graph Memory & Impact Intelligence API)",
    version=settings.VERSION,
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(health.router, prefix="/api")
app.include_router(seed.router, prefix="/api")
app.include_router(projects.router, prefix="/api")
app.include_router(graph.router, prefix="/api")
app.include_router(memory.router, prefix="/api")
app.include_router(analyze.router, prefix="/api")
app.include_router(impact.router, prefix="/api")
app.include_router(activity.router, prefix="/api")

# Direct deployment health check endpoints
@app.get("/health", tags=["Deployment Probes"])
@app.get("/healthz", tags=["Deployment Probes"])
def deployment_health():
    return health.get_health()

# Mount frontend static directory if exists
frontend_dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
frontend_src = Path(__file__).resolve().parent.parent.parent / "frontend"

if frontend_dist.exists() and (frontend_dist / "index.html").exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend-dist")
elif frontend_src.exists() and (frontend_src / "index.html").exists():
    app.mount("/", StaticFiles(directory=str(frontend_src), html=True), name="frontend-static")
else:
    @app.get("/")
    def root():
        return {
            "title": settings.PROJECT_NAME,
            "tagline": settings.TAGLINE,
            "version": settings.VERSION,
            "docs_url": "/docs",
            "health_url": "/api/health",
            "message": "CodeBrain AI API is running. Access /docs for interactive OpenAPI explorer.",
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=False,
    )
