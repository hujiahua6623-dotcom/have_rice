import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import admin, auth, rooms, ws
from app.config import settings
from app.database import init_db

os.makedirs("data", exist_ok=True)
init_db()

app = FastAPI(title=settings.app_name, version="0.1.0")

origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(rooms.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(ws.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
