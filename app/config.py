import os
from pathlib import Path


class Settings:
    def __init__(self) -> None:
        self.app_api_key = os.environ.get("APP_API_KEY", "")
        self.mistral_api_key = os.environ.get("MISTRAL_API_KEY", "")
        self.mistral_model = os.environ.get("MISTRAL_MODEL", "mistral-large-latest")
        self.mistral_base_url = os.environ.get("MISTRAL_BASE_URL", "https://api.mistral.ai/v1")
        default_skills_dir = Path(__file__).resolve().parent.parent / "skills"
        self.skills_dir = Path(os.environ.get("SKILLS_DIR", str(default_skills_dir)))


settings = Settings()
