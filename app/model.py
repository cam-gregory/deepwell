import json

import httpx

from app import config

def _build_messages(user_prompt: str, system_prompt: str | None) -> list[dict]:
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
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
) -> dict:
    return {
        "model": config.MODEL_NAME,
        "messages": _build_messages(user_prompt, system_prompt),
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

def generate_stream(
    user_prompt: str,
    system_prompt: str | None = None,
    *,
    num_ctx: int = config.NUM_CTX,
    num_predict: int = config.NUM_PREDICT,
    temperature: float = config.TEMPERATURE,
    keep_alive: str = config.KEEP_ALIVE,
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
