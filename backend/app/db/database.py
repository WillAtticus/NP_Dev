import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATA_DIR = os.environ.get("DATA_DIR", "./data")
os.makedirs(DATA_DIR, exist_ok=True)

SQLITE_URL = f"sqlite:///{DATA_DIR}/neuropulse.db"
engine = create_engine(SQLITE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    os.makedirs(DATA_DIR, exist_ok=True)
    try:
        from . import models  # noqa: F401
    except ImportError:
        try:
            from app.db import models  # noqa: F401
        except ImportError:
            from backend.app.db import models  # noqa: F401
    try:
        from .migrations import upgrade_database
    except ImportError:
        try:
            from app.db.migrations import upgrade_database
        except ImportError:
            from backend.app.db.migrations import upgrade_database
    upgrade_database(engine)
