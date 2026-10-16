"""The admin web app. Start it from the project root with:

    uv run uvicorn app.admin.app:app --reload --port 8000

then open http://localhost:8000  (API docs: http://localhost:8000/docs)

It is a SEPARATE program from the voice agent: both share the same
PostgreSQL database, so a change made here is seen by the assistant on
its next call.
"""

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.admin.errors import DuplicateError, InvalidStateError, NotFoundError
from app.admin.routes import router
from app.core.logging import setup_logging
from app.exceptions import DatabaseError

setup_logging()
logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="Clinic Admin")
app.include_router(router)


# ---- turn named errors into clean HTTP answers --------------------------

@app.exception_handler(NotFoundError)
async def not_found_handler(request: Request, exc: NotFoundError):
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(DuplicateError)
async def duplicate_handler(request: Request, exc: DuplicateError):
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(InvalidStateError)
async def invalid_state_handler(request: Request, exc: InvalidStateError):
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(DatabaseError)
async def database_handler(request: Request, exc: DatabaseError):
    logger.error("Database unavailable: %s", exc)
    return JSONResponse(
        status_code=503,
        content={"detail": "The database is not reachable right now."},
    )


# ---- the admin page -----------------------------------------------------

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def admin_page():
    return FileResponse(STATIC_DIR / "index.html")