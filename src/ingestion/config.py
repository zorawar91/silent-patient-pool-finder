"""
Database connection config.
Reads from .env (or environment variables).
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from loguru import logger

# Load .env from project root
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB   = os.getenv("POSTGRES_DB",   "sppf")
POSTGRES_USER = os.getenv("POSTGRES_USER", "sppf")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "sppf_local")

DATABASE_URL = (
    f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
    f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
)

# Paths
PROJECT_ROOT  = Path(__file__).resolve().parents[2]
DATA_DIR      = PROJECT_ROOT / "data" / "synthetic"
SYNTHEA_CSV   = DATA_DIR / "csv"


def get_engine() -> Engine:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    # Verify connection
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    logger.info(f"Connected to PostgreSQL: {POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}")
    return engine
