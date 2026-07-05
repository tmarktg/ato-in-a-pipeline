import enum
from datetime import datetime, timezone

from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, Enum, Integer, String, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings

Base = declarative_base()


class StatusEnum(str, enum.Enum):
    green = "green"
    yellow = "yellow"
    red = "red"


class ServiceRecord(Base):
    __tablename__ = "services"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    version = Column(String, nullable=False)
    status = Column(Enum(StatusEnum), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class ServiceCreate(BaseModel):
    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    status: StatusEnum


class ServiceStatusUpdate(BaseModel):
    status: StatusEnum


class ServiceOut(BaseModel):
    id: int
    name: str
    version: str
    status: StatusEnum

    model_config = {"from_attributes": True}


_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=_connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
