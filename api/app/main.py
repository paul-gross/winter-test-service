import logging
import os
import sys
import time

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Query

from app.deps import ItemServiceDep, ReadItemRepositoryDep, build_write_item_repository
from app.schemas import HealthRead, ItemCreate, ItemRead
from app.services.item_service import ItemValidationError
from wts_persistence.domain.errors import RepositoryError
from wts_logging import configure_logging


# ---------------------------------------------------------------------------
# Logging setup: INFO+ → stdout, WARNING+ → stderr (shared with the worker)
# ---------------------------------------------------------------------------

configure_logging()
logger = logging.getLogger("api")


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

def _boot_delay() -> None:
    delay = float(os.environ.get("WTS_BOOT_DELAY_SECONDS", "0"))
    if delay > 0:
        logger.info("WTS_BOOT_DELAY_SECONDS=%s — sleeping before startup", delay)
        time.sleep(delay)


def _init_schema_with_backoff(timeout: float = 30.0) -> None:
    repo = build_write_item_repository()
    deadline = time.monotonic() + timeout
    attempt = 0
    while True:
        try:
            repo.init_schema()
            logger.info("DB schema initialised")
            return
        except RepositoryError as exc:
            attempt += 1
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                logger.warning(
                    "DB schema init failed after %d attempts, continuing without DB: %s",
                    attempt, exc,
                )
                return
            wait = min(2.0 ** (attempt - 1), 5.0)
            wait = min(wait, remaining)
            logger.info(
                "DB not ready (attempt %d): %s — retrying in %.1fs", attempt, exc, wait
            )
            time.sleep(wait)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _boot_delay()
    _init_schema_with_backoff()
    yield


app = FastAPI(lifespan=lifespan)


# ---------------------------------------------------------------------------
# Request logging middleware
# ---------------------------------------------------------------------------

@app.middleware("http")
async def _log_requests(request: Request, call_next):
    response = await call_next(request)
    logger.info("%s %s → %d", request.method, request.url.path, response.status_code)
    return response


# ---------------------------------------------------------------------------
# Routes — reads go direct through the read seam; the mutation through the service
# ---------------------------------------------------------------------------

@app.get("/api/health", response_model=HealthRead)
def health(items: ReadItemRepositoryDep):
    return HealthRead(status="ok", db="ok" if items.ping() else "down")


@app.get("/api/items", response_model=list[ItemRead])
def get_items(items: ReadItemRepositoryDep):
    return items.list_items()


@app.post("/api/items", status_code=201, response_model=ItemRead)
def create_item(body: ItemCreate, service: ItemServiceDep):
    try:
        return service.add_item(body.label)
    except ItemValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/chaos/crash")
def chaos_crash():
    logger.info("CHAOS: /api/chaos/crash triggered — calling os._exit(1)")
    sys.stdout.flush()
    sys.stderr.write("CHAOS: hard crash via os._exit(1)\n")
    sys.stderr.flush()
    os._exit(1)


@app.post("/api/chaos/error-log")
def chaos_error_log(n: int = Query(default=5, ge=1)):
    # Intentionally raw: write straight to stderr with no logger/formatting, so
    # the emitted lines deliberately do NOT match the app's normal log format —
    # unstructured error output, distinct from the formatted logger.warning below.
    for i in range(1, n + 1):
        sys.stderr.write(f"CHAOS ERROR {i}/{n}\n")
    sys.stderr.flush()
    logger.warning("chaos/error-log emitted %d error lines to stderr", n)
    return {"emitted": n}
