"""Module containing sqlalchemy session logic related."""
from functools import lru_cache
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy_utils import create_database, database_exists

from models import Base

engine = create_engine("sqlite:///db.sqlite3", pool_pre_ping=True)


@lru_cache
def create_session() -> scoped_session:
    """Create a session given the url in settings."""
    Session = scoped_session(
        sessionmaker(autocommit=False, autoflush=False, bind=engine)
    )
    return Session


def get_session() -> Generator[scoped_session, None, None]:
    """Retrieve a session."""
    Session = create_session()
    try:
        yield Session
    finally:
        Session.remove()

db_session = create_session()
created_engine = db_session.bind
if not database_exists(created_engine.url):
    create_database(created_engine.url)
Base.metadata.bind = engine
Base.metadata.create_all(bind=created_engine)

