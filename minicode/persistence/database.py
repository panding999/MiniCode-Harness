from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


def create_database(db_url: str):
    engine = create_engine(db_url)
    factory = sessionmaker(engine, expire_on_commit=False)
    return engine, factory
