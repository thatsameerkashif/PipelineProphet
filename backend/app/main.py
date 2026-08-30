from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import builds, predict, webhook

app = FastAPI(title="Pipeline Prophet API", version="0.1.0")

# ---------------------------------------------------------------------------
# CORS — allow Vite dev server during development
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(predict.router, prefix="/api")
app.include_router(webhook.router, prefix="/api")
app.include_router(builds.router, prefix="/api")


# ---------------------------------------------------------------------------
# Repo list (static for demo)
# ---------------------------------------------------------------------------

@app.get("/api/repos")
async def list_repos() -> list[dict]:
    return [
        {
            "repo_id": "pipeline-prophet-demo",
            "name": "pipeline-prophet-demo",
            "description": "Demo repository for Pipeline Prophet",
            "build_count": 80,
        }
    ]


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "pipeline-prophet"}
