from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import init_db, set_engine
from .routers import admin, conditions, days, goals, health, notifications, review, tags
from .services.reminder_service import reminder_loop
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
        reminder_stop = asyncio.Event()
        reminder_task = None
        if settings.reminders_enabled:
            reminder_task = asyncio.create_task(reminder_loop(reminder_stop))
            logger.info(
                "Reminder loop started with cadence %s minutes",
                settings.reminders_cadence_minutes,
            )
        yield
        if reminder_task is not None:
            reminder_stop.set()
            reminder_task.cancel()
            with suppress(asyncio.CancelledError):
                await reminder_task

    app = FastAPI(title="Goal Tracker API", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health)
    app.include_router(admin)
    app.include_router(goals)
    app.include_router(tags)
    app.include_router(conditions)
    app.include_router(days)
    app.include_router(notifications)
    app.include_router(review)

    return app


app = create_app()
