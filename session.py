"""Module containing sqlalchemy session logic related."""

import logging
from functools import lru_cache
from typing import Generator

import sqlalchemy
import streamlit as st
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy_utils import create_database, database_exists

from models import Base, GasType

logger = logging.getLogger("gas_station_app")
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


database_creation = False
db_session = create_session()
logger.info("session created")
created_engine = db_session.bind
if not database_exists(created_engine.url):
    logger.info("Database does not exist, creating it")
    create_database(created_engine.url)
    database_creation = True
Base.metadata.bind = engine
Base.metadata.create_all(bind=created_engine)


### initialize the database with mandatory data


def create_gastypes(db_session):
    """
    Create the gas types in the database.

    Args:
        db_session: sqlalchemy session

    Returns:
        None
    """
    logger.info("Creating gas types")
    gas_dict = {"Gazole": 1, "SP95": 2, "SP98": 6, "E85": 3, "GPLc": 4, "E10": 5}

    for name, xml_id in gas_dict.items():
        if not db_session.query(GasType).filter(GasType.name == name).first():
            gas_type = GasType(name=name, xml_id=xml_id)
            db_session.add(gas_type)
    try:
        db_session.commit()
    except sqlalchemy.exc.IntegrityError:
        db_session.rollback()


if database_creation:
    create_gastypes(db_session=db_session)
