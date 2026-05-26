import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # API Keys
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    
    # App Settings
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True
    
    # Directories
    WORKSPACE_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    REFERENCE_DIR: str = os.path.join(WORKSPACE_DIR, "reference_materials")
    BOOKS_DIR: str = os.path.join(WORKSPACE_DIR, "output_books")
    TRACES_DIR: str = os.path.join(WORKSPACE_DIR, "traces")
    MEMORIES_DIR: str = os.path.join(WORKSPACE_DIR, "memories")
    
    # Defaults
    DEFAULT_MODEL_PROVIDER: str = "openai"  # "openai" or "mock"
    
    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()

# Ensure directories exist
for directory in [settings.REFERENCE_DIR, settings.BOOKS_DIR, settings.TRACES_DIR, settings.MEMORIES_DIR]:
    os.makedirs(directory, exist_ok=True)
