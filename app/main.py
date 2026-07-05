import json
import logging
import sys
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.models import (
    ServiceCreate,
    ServiceOut,
    ServiceRecord,
    ServiceStatusUpdate,
    get_db,
    init_db,
)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        return json.dumps(payload)


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(settings.log_level.upper())


configure_logging()
logger = logging.getLogger("readiness_board")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("startup complete")
    yield


app = FastAPI(title="Readiness Board", lifespan=lifespan)
Instrumentator().instrument(app).expose(app, endpoint="/metrics")


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/readyz")
def readyz(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        logger.error("readiness check failed: %s", exc)
        raise HTTPException(status_code=503, detail="database unavailable") from exc
    return {"status": "ready"}


@app.get("/services", response_model=list[ServiceOut])
def list_services(db: Session = Depends(get_db)):
    return db.query(ServiceRecord).order_by(ServiceRecord.id).all()


@app.post("/services", response_model=ServiceOut, status_code=201)
def create_service(service: ServiceCreate, db: Session = Depends(get_db)):
    record = ServiceRecord(name=service.name, version=service.version, status=service.status)
    db.add(record)
    db.commit()
    db.refresh(record)
    logger.info("service created: %s", record.name)
    return record


@app.put("/services/{service_id}/status", response_model=ServiceOut)
def update_service_status(
    service_id: int, update: ServiceStatusUpdate, db: Session = Depends(get_db)
):
    record = db.get(ServiceRecord, service_id)
    if record is None:
        raise HTTPException(status_code=404, detail="service not found")
    record.status = update.status
    db.commit()
    db.refresh(record)
    logger.info("service %s status updated to %s", service_id, update.status)
    return record
