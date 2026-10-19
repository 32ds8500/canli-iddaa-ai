"""Pytest yapilandirmasi.

Testlerde GERCEK API cagrisi yapilmaz; saglayici FixtureProvider ile
degistirilir. Veritabani izole bir SQLite dosyasidir.
"""
from __future__ import annotations

import os

# app import edilmeden ONCE ortam ayarlari
os.environ["DATABASE_URL"] = "sqlite:///./data/test_canli_iddaa.db"
os.environ["ENABLE_SCHEDULER"] = "false"
os.environ["API_FOOTBALL_KEY"] = ""
os.environ["FOOTBALL_DATA_KEY"] = ""

import pytest  # noqa: E402

from app.config import get_settings  # noqa: E402

get_settings.cache_clear()

from app.db import Base, SessionLocal, engine  # noqa: E402
from app import models  # noqa: E402,F401


@pytest.fixture()
def db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
