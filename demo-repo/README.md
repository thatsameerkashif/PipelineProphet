# pipeline-prophet-demo

A small FastAPI application used as the **demo repository** for [Pipeline Prophet](../README.md).

Pipeline Prophet connects to this repo via GitHub webhook and — before any CI pipeline runs —
predicts per-stage failure probabilities using IBM watsonx.ai Granite grounded in this
repository's own accumulated build history (stored in IBM Cloudant).

## Project structure

```
demo-repo/
├── src/
│   ├── main.py       # FastAPI application
│   └── config.py     # Pydantic settings
├── tests/
│   └── test_main.py  # Pytest test suite
├── requirements.txt  # Python dependencies
├── Dockerfile        # Container image definition
├── pipeline.yml      # Pipeline stage definitions (used by Pipeline Prophet)
└── README.md         # This file
```

## Running locally

```bash
pip install -r requirements.txt
uvicorn src.main:app --reload --port 8080
```

Visit `http://localhost:8080/health` — should return `{"status": "ok"}`.

## Running tests

```bash
pytest tests/ -v
```

## Pipeline stages

| Stage   | Command                              |
|---------|--------------------------------------|
| install | `pip install -r requirements.txt`    |
| test    | `pytest tests/ -v`                   |
| lint    | `flake8 src/ --max-line-length=88`   |
| build   | `docker build -t demo-app:latest .`  |
