import os
from contextlib import contextmanager

from celery import Celery
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")

celery_app = Celery("nexus_twin", broker=REDIS_URL, backend=REDIS_URL)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
)
celery_app.autodiscover_tasks(["src.workers.tasks"])


@contextmanager
def get_sync_session():
    database_url = os.environ.get("DATABASE_URL", "")
    sync_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
    engine = create_engine(sync_url)
    session_local = sessionmaker(bind=engine)
    session = session_local()
    try:
        yield session
    finally:
        session.close()
