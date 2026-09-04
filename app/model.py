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

def _apply_cloud_options(payload: dict) -> None:
    """Attach optional cloud tuning (thinking effort, output cap) when configured."""
    if config.CLOUD_REASONING_EFFORT:
        payload["reasoning_effort"] = config.CLOUD_REASONING_EFFORT
    if config.CLOUD_MAX_OUTPUT_TOKENS:
        payload["max_tokens"] = config.CLOUD_MAX_OUTPUT_TOKENS

def _content_from_response(data: dict) -> str:
    """Pull message content from an OpenAI-compatible response, with a
    diagnostic error when it's missing (e.g. thinking models that return no
    content, or a safety block)."""
    choices = data.get("choices")
    if not choices:
        raise RuntimeError(f"No choices in cloud response: {json.dumps(data)[:600]}")
    choice = choices[0]
    message = choice.get("message") or {}
    content = message.get("content")
    if content is None:
        finish = choice.get("finish_reason")
        raise RuntimeError(
            f"No message content (finish_reason={finish}). "
            f"If using a thinking model, set DEEPWELL_CLOUD_REASONING=none or use "
            f"gemini-2.5-flash-lite. Raw choice: {json.dumps(choice)[:600]}"
        )
    return content.strip()

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
    _apply_cloud_options(payload)
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
    except ValueError as exc:
        raise RuntimeError("Cloud LLM returned a non-JSON response") from exc

    content = _content_from_response(data)
    if not content:
        raise RuntimeError("Cloud LLM returned an empty response")

    return content

def generate_cloud_vision(
    user_prompt: str,
    images_b64: list[str],
    system_prompt: str | None = None,
    *,
    mime: str = "image/png",
    temperature: float = 0.0,
    timeout: float = 180.0,
) -> str:
    """Multimodal one-shot generation via an OpenAI-compatible chat API.

    Sends one or more base64 images alongside the prompt (used for math-PDF
    OCR). Ingestion-only; same PAC-proxy routing as generate_cloud."""
    if not config.CLOUD_LLM_API_KEY:
        raise RuntimeError("DEEPWELL_CLOUD_API_KEY is not set")
    if not images_b64:
        raise ValueError("images_b64 must not be empty")

    from ingestion.http_client import resolve_proxy

    content: list[dict] = [{"type": "text", "text": user_prompt}]
    for b64 in images_b64:
        content.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}})

    messages: list[dict] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": content})

    url = f"{config.CLOUD_LLM_BASE_URL}/chat/completions"
    payload = {"model": config.CLOUD_LLM_MODEL, "messages": messages, "temperature": temperature}
    _apply_cloud_options(payload)
    headers = {"Authorization": f"Bearer {config.CLOUD_LLM_API_KEY}"}

    try:
        with httpx.Client(proxy=resolve_proxy(url), timeout=timeout) as client:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(
            f"Cloud vision LLM returned {exc.response.status_code}: {exc.response.text}"
        ) from exc
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Cloud vision LLM request failed: {exc}") from exc

    try:
        data = response.json()
    except ValueError as exc:
        raise RuntimeError("Cloud vision LLM returned a non-JSON response") from exc

    return _content_from_response(data)

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
