from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


# SQLAlchemy 启动代码保持很小，方便测试切换到 sqlite:///:memory:。
class Base(DeclarativeBase):
    pass


def create_database(db_url: str):
    engine = create_engine(db_url)
    factory = sessionmaker(engine, expire_on_commit=False)
    return engine, factory
