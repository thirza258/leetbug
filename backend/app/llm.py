import re

import httpx

from app.config import settings


class AIUnavailable(Exception):
    pass


def complete(messages, *, max_tokens=4096):
    if not settings.ai_enabled:
        raise AIUnavailable("AI fixes need a configured OpenRouter or Ollama model. Manual mode is available.")
    headers = {"Content-Type": "application/json"}
    if settings.ai_api_key:
        headers["Authorization"] = f"Bearer {settings.ai_api_key}"
    if settings.ai_provider == "openrouter":
        headers.update({"HTTP-Referer": settings.origins[0], "X-Title": "LeetBug"})
    try:
        with httpx.Client(timeout=settings.ai_timeout_seconds) as client:
            response = client.post(f"{settings.llm_url}/chat/completions", headers=headers,
                                   json={"model": settings.ai_model, "messages": messages,
                                         "temperature": 0.2, "max_tokens": max_tokens})
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

