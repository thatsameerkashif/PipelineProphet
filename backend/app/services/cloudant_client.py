"""
IBM Cloudant wrapper using the ibm-cloudant SDK.
All public functions are async-friendly (run sync SDK calls in a thread pool
via asyncio.to_thread so they don't block the FastAPI event loop).

Falls back gracefully when ibm-cloudant is not installed (demo / dev mode).
"""

import asyncio
from typing import Any

try:
    from ibmcloudant.cloudant_v1 import CloudantV1, Document
    from ibm_cloud_sdk_core.authenticators import IAMAuthenticator
    _IBM_CLOUDANT_AVAILABLE = True
except ImportError:
    CloudantV1 = None  # type: ignore[assignment,misc]
    Document = None    # type: ignore[assignment,misc]
    IAMAuthenticator = None  # type: ignore[assignment,misc]
    _IBM_CLOUDANT_AVAILABLE = False

from app.config import CLOUDANT_URL, CLOUDANT_APIKEY


def _get_client():
    """Build and return an authenticated CloudantV1 client."""
    if not _IBM_CLOUDANT_AVAILABLE:
        raise RuntimeError("ibm-cloudant package is not installed")
    authenticator = IAMAuthenticator(CLOUDANT_APIKEY)
    _c = CloudantV1(authenticator=authenticator)
    _c.set_service_url(CLOUDANT_URL)
    return _c


# ---------------------------------------------------------------------------
# Module-level singleton — used by build_dna.py and the setup scripts.
# Only initialised when credentials are present; callers must check themselves.
# ---------------------------------------------------------------------------

def _build_singleton():
    if not _IBM_CLOUDANT_AVAILABLE or not CLOUDANT_URL or not CLOUDANT_APIKEY:
        return None
    return _get_client()


client: CloudantV1 | None = _build_singleton()


# ---------------------------------------------------------------------------
# Async wrappers
# ---------------------------------------------------------------------------

async def create_doc(db: str, doc: dict) -> dict:
    """Insert *doc* into *db* and return the Cloudant response (id, rev, ok)."""
    def _sync():
        client = _get_client()
        document = Document.from_dict(doc)
        response = client.post_document(db=db, document=document).get_result()
        return response

    return await asyncio.to_thread(_sync)


async def get_doc(db: str, doc_id: str) -> dict:
    """Retrieve a single document by *doc_id* from *db*."""
    def _sync():
        client = _get_client()
        return client.get_document(db=db, doc_id=doc_id).get_result()

    return await asyncio.to_thread(_sync)


async def query_docs(
    db: str,
    selector: dict,
    fields: list[str] | None = None,
    limit: int = 50,
) -> list[dict]:
    """Run a Mango query against *db* and return matching documents."""
    def _sync():
        client = _get_client()
        kwargs: dict[str, Any] = {"db": db, "selector": selector, "limit": limit}
        if fields:
            kwargs["fields"] = fields
        result = client.post_find(**kwargs).get_result()
        return result.get("docs", [])

    return await asyncio.to_thread(_sync)


def list_databases() -> list[str]:
    """Synchronous helper — returns list of all database names (used in tests)."""
    client = _get_client()
    return client.get_all_dbs().get_result()
