from fastapi import FastAPI

from app.api.routes.health import router as health_router

app = FastAPI(
    title="Event-Driven Automation Engine",
    version="0.1.0",
    description="Durable at-least-once event delivery reference implementation.",
)
app.include_router(health_router)
