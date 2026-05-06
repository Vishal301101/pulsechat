from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.db.session import engine,Base

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Runs on startup and shutdown.
    Startup: create DB tables, warm up connections.
    Shutdown: close connections cleanly.
    """
    print(f"starting {settings.APP_NAME} v{settings.VERSION}")
    print(f"Environment: {settings.ENVIRONMENT}")

    # Create all tables if they don't exist yet
    # (Later we'll replace this with Alembic migrations)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    print("Database tables ready")

    yield

    print("shutting down")
    await engine.dispose()
    print("Database connection closed")

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="Realtime team chat api",
    docs_url="/docs" if settings.ENVIRONMENT == "development" else None,
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins = ["http://localhost:3000"],
    allow_credentials=True,
    allow_methods = ["*"],
    allow_headers = ["*"]
)

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
    }

@app.get("/")
async def root():
    return {"message": f"Welcome to {settings.APP_NAME}"}