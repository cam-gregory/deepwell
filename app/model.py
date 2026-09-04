import json

import httpx

from app import config

def _build_messages(
    user_prompt: str,
    system_prompt: str | None,
    history: list[dict] | None = None,
) -> list[dict]:
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_prompt})
    return messages

def _build_payload(
    user_prompt: str,
    system_prompt: str | None,
    *,
    stream: bool,
    num_ctx: int,
    num_predict: int,
    temperature: float,
    keep_alive: str,
    history: list[dict] | None = None,
) -> dict:
    return {
        "model": config.MODEL_NAME,
        "messages": _build_messages(user_prompt, system_prompt, history),
        "stream": stream,
        "keep_alive": keep_alive,
        "options": {
            "num_ctx": num_ctx,
            "num_predict": num_predict,
            "temperature": temperature,
        },
    }

def generate(
    user_prompt: str,
    system_prompt: str | None = None,
    *,
    num_ctx: int = config.NUM_CTX,
    num_predict: int = config.NUM_PREDICT,
    temperature: float = config.TEMPERATURE,
    keep_alive: str = config.KEEP_ALIVE,
    timeout: float = config.REQUEST_TIMEOUT,
) -> str:
    """Non-streaming generation. Returns the full answer text."""
    if not user_prompt.strip():
        raise ValueError("user_prompt must not be empty")

    payload = _build_payload(
        user_prompt,
        system_prompt,
        stream=False,
        num_ctx=num_ctx,
        num_predict=num_predict,
        temperature=temperature,
        keep_alive=keep_alive,
    )

    try:
        response = httpx.post(config.OLLAMA_URL, json=payload, timeout=timeout)
        response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise RuntimeError("Ollama request timed out") from exc
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(
            f"Ollama returned {exc.response.status_code}: {exc.response.text}"
        ) from exc
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Ollama request failed: {exc}") from exc

    try:
        data = response.json()
    except ValueError as exc:
        raise RuntimeError("Ollama returned a non-JSON response") from exc

    message = data.get("message")
    if not isinstance(message, dict):
        raise RuntimeError(f"Unexpected Ollama response shape: {data!r}")

    content = (message.get("content") or "").strip()
    if not content:
        raise RuntimeError("Model returned an empty response")

    return content

def generate_cloud(
    user_prompt: str,
    system_prompt: str | None = None,
    *,
    temperature: float = config.TEMPERATURE,
    timeout: float = config.CLOUD_REQUEST_TIMEOUT,
) -> str:
    """One-shot generation via an OpenAI-compatible chat API (ingestion only).

    Routed through the system PAC proxy so it works on corporate networks,
    reusing the same resolver as the ZIM/web downloaders."""
    if not user_prompt.strip():
        raise ValueError("user_prompt must not be empty")
    if not config.CLOUD_LLM_API_KEY:
        raise RuntimeError("DEEPWELL_CLOUD_API_KEY is not set")

    from ingestion.http_client import resolve_proxy

    url = f"{config.CLOUD_LLM_BASE_URL}/chat/completions"
    payload = {
        "model": config.CLOUD_LLM_MODEL,
        "messages": _build_messages(user_prompt, system_prompt),
        "temperature": temperature,
    }
    headers = {"Authorization": f"Bearer {config.CLOUD_LLM_API_KEY}"}

    try:
        with httpx.Client(proxy=resolve_proxy(url), timeout=timeout) as client:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(
            f"Cloud LLM returned {exc.response.status_code}: {exc.response.text}"
        ) from exc
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Cloud LLM request failed: {exc}") from exc

    try:
        data = response.json()
        content = (data["choices"][0]["message"]["content"] or "").strip()
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"Unexpected cloud LLM response shape: {exc}") from exc

    if not content:
        raise RuntimeError("Cloud LLM returned an empty response")

    return content

def generate_ingest(
    user_prompt: str,
    system_prompt: str | None = None,
    *,
    temperature: float = config.TEMPERATURE,
) -> str:
    """Ingestion-time generation. Uses the cloud LLM when configured
    (DEEPWELL_INGEST_LLM=cloud) and reachable, otherwise the local Ollama
    model, and always falls back to local on failure so ingestion keeps
    working offline. The query/answer path never calls this."""
    if config.INGEST_LLM_PROVIDER == "cloud":
        try:
            return generate_cloud(user_prompt, system_prompt, temperature=temperature)
        except Exception as exc:
            print(f"  cloud ingest LLM unavailable ({exc}); using local model")
    return generate(user_prompt, system_prompt, temperature=temperature)

def generate_stream(
    user_prompt: str,
    system_prompt: str | None = None,
    *,
    num_ctx: int = config.NUM_CTX,
    num_predict: int = config.NUM_PREDICT,
    temperature: float = config.TEMPERATURE,
    keep_alive: str = config.KEEP_ALIVE,
    history: list[dict] | None = None,
):
    """Streaming generation. Yields answer-content tokens as they arrive."""
    if not user_prompt.strip():
        raise ValueError("user_prompt must not be empty")

    payload = _build_payload(
        user_prompt,
        system_prompt,
        stream=True,
        num_ctx=num_ctx,
        num_predict=num_predict,
        temperature=temperature,
        keep_alive=keep_alive,
        history=history,
    )

    # No read timeout: generation can pause between tokens.
    timeout = httpx.Timeout(connect=10.0, read=None, write=10.0, pool=10.0)

    try:
        with httpx.stream(
            "POST", config.OLLAMA_URL, json=payload, timeout=timeout
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line:
                    continue
                data = json.loads(line)
                token = (data.get("message") or {}).get("content")
                if token:
                    yield token
                if data.get("done"):
                    break
    except httpx.TimeoutException as exc:
        raise RuntimeError("Ollama request timed out") from exc
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(
            f"Ollama returned {exc.response.status_code}: {exc.response.text}"
        ) from exc
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Ollama request failed: {exc}") from exc
