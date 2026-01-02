from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import init_db, set_engine
from .routers import conditions, days, goals, health, review, tags
from .settings import settings

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger("goal-tracker")


def create_app(engine_override=None) -> FastAPI:
    if engine_override is not None:
        set_engine(engine_override)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        init_db()
        logger.info("Database initialized")
        yield

    app = FastAPI(title="Goal Tracker API", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health)
    app.include_router(goals)
    app.include_router(tags)
    app.include_router(conditions)
    app.include_router(days)
    app.include_router(review)

    return app


app = create_app()
