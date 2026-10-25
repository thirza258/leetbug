import logging
import random
import re
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

FREE_OPENROUTER_MODELS = [
    "google/gemma-4-26b-a4b-it:free",
    "nvidia/nemotron-3.5-lightning:free",
    "cohere/north-mini-code:free",
    "recursive/flint-v1.0:free",
    "xingchen-agi/xing4.0-29b-a4b:free",
    "nvidia/nemotron-3.5-super-vl:free",
    "dots-studio/dots-3-note-preview:free",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "google/gemma-4-31b-it:free",
]


def get_shuffled_free_models() -> list[str]:
    models = list(FREE_OPENROUTER_MODELS)
    random.shuffle(models)
    return models


def is_credit_exhausted_error(exc_or_status: Any, message: str = "") -> bool:
    code = None
    if isinstance(exc_or_status, int):
        code = exc_or_status
    else:
        for attr in ("status_code", "http_status", "code"):
            val = getattr(exc_or_status, attr, None)
            if isinstance(val, int):
                code = val
                break
        if code is None and hasattr(exc_or_status, "response"):
            resp = getattr(exc_or_status, "response", None)
            code = getattr(resp, "status_code", None)

    msg_str = f"{exc_or_status} {message}".lower()
    if code == 402:
        return True

    if "rate limit" in msg_str and not any(k in msg_str for k in ("credit", "payment", "balance")):
        return False

    credit_keywords = (
        "402",
        "credit",
        "payment required",
        "run out of credits",
        "insufficient balance",
        "insufficient credits",
        "insufficient_quota",
        "exceeded your current quota",
        "out of credit",
    )
    return any(kw in msg_str for kw in credit_keywords)


class AIUnavailable(Exception):
    pass


def complete(messages, *, max_tokens=4096, timeout=None):
    if not settings.ai_enabled:
        raise AIUnavailable("AI fixes need a configured OpenRouter or Ollama model. Manual mode is available.")
    headers = {"Content-Type": "application/json"}
    if settings.ai_api_key:
        headers["Authorization"] = f"Bearer {settings.ai_api_key}"
    if settings.ai_provider == "openrouter":
        headers.update({"HTTP-Referer": settings.origins[0], "X-Title": "LeetBug"})
    try:
        with httpx.Client(timeout=timeout or settings.ai_timeout_seconds) as client:
            response = client.post(f"{settings.llm_url}/chat/completions", headers=headers,
                                   json={"model": settings.ai_model, "messages": messages,
                                         "temperature": 0.2, "max_tokens": max_tokens})
            if settings.ai_provider == "openrouter" and is_credit_exhausted_error(response.status_code, response.text):
                logger.warning("OpenRouter credits exhausted (%s), falling back to shuffled free models", response.status_code)
                for free_model in get_shuffled_free_models():
                    try:
                        logger.info("Retrying with free fallback model: %s", free_model)
                        fb_resp = client.post(
                            f"{settings.llm_url}/chat/completions",
                            headers=headers,
                            json={"model": free_model, "messages": messages,
                                  "temperature": 0.2, "max_tokens": max_tokens}
                        )
                        if fb_resp.is_success:
                            data = fb_resp.json()
                            content = data["choices"][0]["message"]["content"]
                            if isinstance(content, str) and content.strip():
                                logger.info("Fallback succeeded with free model: %s", free_model)
                                return content, data.get("usage", {}).get("total_tokens")
                    except Exception as fb_exc:
                        logger.warning("Free model %s failed: %s", free_model, fb_exc)
                        continue
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            if not isinstance(content, str) or not content.strip():
                raise ValueError("Empty model response")
            return content, data.get("usage", {}).get("total_tokens")
    except (httpx.HTTPError, KeyError, IndexError, ValueError, TypeError) as exc:
        raise AIUnavailable("The AI model did not return a usable response. Check the model configuration or try manual mode.") from exc


def patch_code(problem, language, source, prompt):
    content, tokens = complete([
        {"role": "system", "content": "You are a debugging assistant. Apply the user's directive to the supplied program. "
         "Return only the complete patched source, with no explanation. Preserve the entry point and language. "
         "The program runs without network access. Do not include tests or invent additional dependencies."},
        {"role": "user", "content": f"Language: {language}\nProblem: {problem.title}\n"
         f"Requirements:\n{chr(10).join(problem.requirements)}\nCurrent source:\n{source}\nDirective:\n{prompt}"},
    ])
    fence = re.fullmatch(r"\s*```[^\n]*\n(.*?)\n?```\s*", content, re.DOTALL)
    content = fence.group(1) if fence else content.strip()
    if len(content) > 50000:
        raise AIUnavailable("The generated source exceeded the workspace limit. Try a more focused directive.")
    return content, tokens
