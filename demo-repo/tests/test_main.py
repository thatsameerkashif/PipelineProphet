import pytest
from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def test_root():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert data["message"] == "Hello World"
    assert "version" in data


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_get_item():
    response = client.get("/items/42")
    assert response.status_code == 200
    data = response.json()
    assert data["item_id"] == 42
    assert data["active"] is True


def test_list_items_default():
    response = client.get("/items")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert len(data["items"]) == 10


def test_list_items_pagination():
    response = client.get("/items?skip=5&limit=3")
    assert response.status_code == 200
    data = response.json()
    assert data["skip"] == 5
    assert data["limit"] == 3
    assert len(data["items"]) == 3
