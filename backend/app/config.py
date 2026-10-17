import os
from pathlib import Path
from dotenv import load_dotenv

# Search for .env in potential project roots
possible_env_paths = [
    Path.cwd() / ".env",
    Path(__file__).resolve().parent.parent.parent / ".env",
    Path(__file__).resolve().parent.parent / ".env",
]

for p in possible_env_paths:
    if p.exists():
        load_dotenv(dotenv_path=p, override=False)
        break
else:
    load_dotenv()  # Fallback to standard dotenv discovery


def _clean_str(val: str, default: str = "") -> str:
    if not val:
        return default
    s = val.strip()
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        s = s[1:-1].strip()
    return s


class Settings:
    PROJECT_NAME: str = "DevGraph Sentinel"
    TAGLINE: str = "Understand the past. Predict the impact. Prevent the next bug."
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = _clean_str(os.getenv("ENVIRONMENT", "development"))
    LOG_LEVEL: str = _clean_str(os.getenv("LOG_LEVEL", "info"))

    # Neo4j Settings
    NEO4J_URI: str = _clean_str(os.getenv("NEO4J_URI", ""))
    NEO4J_USERNAME: str = _clean_str(os.getenv("NEO4J_USERNAME", "neo4j"))
    NEO4J_PASSWORD: str = _clean_str(os.getenv("NEO4J_PASSWORD", ""))
    NEO4J_DATABASE: str = _clean_str(os.getenv("NEO4J_DATABASE", "neo4j"))

    # OpenAI Settings
    OPENAI_API_KEY: str = _clean_str(os.getenv("OPENAI_API_KEY", ""))
    OPENAI_MODEL: str = _clean_str(os.getenv("OPENAI_MODEL", "gpt-4.1-mini"))
    OPENAI_TEMPERATURE: float = float(os.getenv("OPENAI_TEMPERATURE", "0.2"))
    OPENAI_MAX_TOKENS: int = int(os.getenv("OPENAI_MAX_TOKENS", "1200"))

    @property
    def is_neo4j_configured(self) -> bool:
        # Must have both valid URI and password (not placeholder)
        if not self.NEO4J_URI or not self.NEO4J_PASSWORD:
            return False
        if "your_secure_neo4j_password_here" in self.NEO4J_PASSWORD or "<password>" in self.NEO4J_PASSWORD:
            return False
        return True

    @property
    def is_openai_configured(self) -> bool:
        if not self.OPENAI_API_KEY:
            return False
        if "your_openai_api_key_here" in self.OPENAI_API_KEY or "sk-..." in self.OPENAI_API_KEY:
            return False
        return True


settings = Settings()
