from __future__ import annotations
# Database connection helper for Neon (PostgreSQL).
# Used by both the pipeline (run.py) and the Streamlit dashboard.
#
# Connection string priority:
#   1. st.secrets["NEON_DATABASE_URL"]  — Streamlit Cloud / local secrets.toml
#   2. NEON_DATABASE_URL env var        — local development
#   3. DATABASE_URL env var             — generic fallback

import os
import logging

log = logging.getLogger(__name__)


def get_engine(echo: bool = False):
    """
    Return a SQLAlchemy engine connected to Neon, or None if no URL is configured.
    Neon requires SSL — appended automatically if missing.
    """
    from sqlalchemy import create_engine

    url = _resolve_url()
    if not url:
        return None

    # Neon requires sslmode=require
    if "sslmode" not in url:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}sslmode=require"

    try:
        engine = create_engine(url, pool_pre_ping=True, echo=echo)
        log.info("Neon engine created.")
        return engine
    except Exception as e:
        log.error(f"Failed to create DB engine: {e}")
        return None


def _resolve_url() -> str | None:
    """Try streamlit secrets first, then env vars."""
    # 1. Streamlit secrets (works in Streamlit Cloud and local secrets.toml)
    try:
        import streamlit as st
        url = st.secrets.get("NEON_DATABASE_URL")
        if url:
            return url
    except Exception:
        pass

    # 2. Environment variables
    return (
        os.environ.get("NEON_DATABASE_URL")
        or os.environ.get("DATABASE_URL")
    )
