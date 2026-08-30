from fastapi import FastAPI

from .config import settings

app = FastAPI(title="Demo App")


@app.get("/")
def root() -> dict:
    return {"message": "Hello World", "version": settings.VERSION}


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/items/{item_id}")
def get_item(item_id: int) -> dict:
    """Return a placeholder item by ID."""
    return {"item_id": item_id, "name": f"Item {item_id}", "active": True}


@app.get("/items")
def list_items(skip: int = 0, limit: int = 10) -> dict:
    """Return a paginated list of placeholder items."""
    items = [{"item_id": i, "name": f"Item {i}", "active": True} for i in range(skip, skip + limit)]
    return {"items": items, "skip": skip, "limit": limit}
