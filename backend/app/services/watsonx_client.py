"""
IBM watsonx.ai wrapper using the ibm-watsonx-ai SDK.
Exposes a single `generate` function for text generation.

Uses the chat API (non-deprecated) when available, falls back to generate_text.
Falls back gracefully when ibm-watsonx-ai is not installed (demo / dev mode).
"""
import warnings

try:
    from ibm_watsonx_ai.foundation_models import ModelInference
    from ibm_watsonx_ai.metanames import GenTextParamsMetaNames as ParamNames
    _WATSONX_AVAILABLE = True
except ImportError:
    ModelInference = None  # type: ignore[assignment,misc]
    ParamNames = None      # type: ignore[assignment,misc]
    _WATSONX_AVAILABLE = False

from app.config import WATSONX_API_KEY, WATSONX_PROJECT_ID, WATSONX_URL, WATSONX_MODEL_ID


def _get_model(max_tokens: int):
    """Build and return a configured ModelInference instance."""
    credentials = {
        "apikey": WATSONX_API_KEY,
        "url": WATSONX_URL,
    }
    params = {
        ParamNames.MAX_NEW_TOKENS: max_tokens,
        ParamNames.TEMPERATURE: 0.1,  # low temperature for structured JSON output
    }
    return ModelInference(
        model_id=WATSONX_MODEL_ID,
        credentials=credentials,
        project_id=WATSONX_PROJECT_ID,
        params=params,
    )


def generate(prompt: str, max_tokens: int = 1024) -> str:
    """
    Send *prompt* to the configured watsonx.ai model and return the generated text.

    Tries the modern chat() API first (non-deprecated), falls back to generate_text().
    Suppresses IBM SDK deprecation warnings — they are informational only.

    This is a synchronous call. When called from FastAPI endpoints wrap it with
    ``asyncio.to_thread(generate, prompt)`` to avoid blocking the event loop.
    """
    if not _WATSONX_AVAILABLE:
        raise RuntimeError("ibm-watsonx-ai package is not installed")
    if not WATSONX_API_KEY or not WATSONX_PROJECT_ID:
        raise RuntimeError("watsonx.ai credentials not configured")

    model = _get_model(max_tokens)

    # Suppress IBM SDK deprecation / license warnings — cosmetic only
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        # Try the chat API first (current, non-deprecated)
        try:
            messages = [{"role": "user", "content": prompt}]
            response = model.chat(messages=messages)
            # Extract text from chat response structure
            return response["choices"][0]["message"]["content"]
        except Exception:
            # Fall back to generate_text (still works, just deprecated)
            try:
                return model.generate_text(prompt=prompt)
            except Exception as exc:
                raise RuntimeError(f"watsonx.ai generation failed: {exc}") from exc
