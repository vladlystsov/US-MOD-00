import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "moderation-secret-key-change-in-production")
    JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

    B2B_SERVICE_URL = os.getenv("B2B_SERVICE_URL", "http://localhost:8000")
    # Legacy B2B_SERVICE_KEY remains a fallback for existing local environments.
    B2B_SERVICE_KEY = os.getenv("B2B_SERVICE_KEY", "b2b-secret-key-123")
    B2B_TO_MOD_KEY = os.getenv("B2B_TO_MOD_KEY", B2B_SERVICE_KEY)
    MOD_TO_B2B_KEY = os.getenv("MOD_TO_B2B_KEY", "moderation-secret-key-123")

    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./moderation.db")

    DEBUG = os.getenv("DEBUG", "True").lower() == "true"

settings = Settings()
