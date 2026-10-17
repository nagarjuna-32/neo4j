import os
from pathlib import Path
from dotenv import load_dotenv

# Load local .env if present
env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)


class Settings:
    PROJECT_NAME: str = "DevGraph Sentinel"
    TAGLINE: str = "Understand the past. Predict the impact. Prevent the next bug."
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "info")

    # Neo4j Settings
    NEO4J_URI: str = os.getenv("NEO4J_URI", "")
    NEO4J_USERNAME: str = os.getenv("NEO4J_USERNAME", "neo4j")
    NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "")
    NEO4J_DATABASE: str = os.getenv("NEO4J_DATABASE", "neo4j")

    # OpenAI Settings
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    OPENAI_TEMPERATURE: float = float(os.getenv("OPENAI_TEMPERATURE", "0.2"))
    OPENAI_MAX_TOKENS: int = int(os.getenv("OPENAI_MAX_TOKENS", "1200"))

    @property
    def is_neo4j_configured(self) -> bool:
        return bool(self.NEO4J_URI and self.NEO4J_PASSWORD)

    @property
    def is_openai_configured(self) -> bool:
        return bool(self.OPENAI_API_KEY and self.OPENAI_API_KEY.strip() != "")


settings = Settings()
