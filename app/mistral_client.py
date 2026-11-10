import httpx


class MistralError(Exception):
    pass


async def complete(
    *,
    system: str,
    user: str,
    model: str,
    base_url: str,
    api_key: str,
    temperature: float = 0.2,
    timeout: float = 90.0,
) -> str:
    url = base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json=payload, headers=headers)
    except httpx.HTTPError as exc:
        raise MistralError(f"Kan Mistral API niet bereiken: {exc}") from exc
    if resp.status_code != 200:
        raise MistralError(f"Mistral API fout {resp.status_code}: {resp.text[:300]}")
    data = resp.json()
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise MistralError("Onverwacht antwoord van Mistral API") from exc
