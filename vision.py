"""Card extraction using the selected AI provider."""
import base64
import json
import httpx
from anthropic import Anthropic

EXTRACTION_PROMPT = (
    "You are extracting structured contact data from a business card image. "
    "Return ONLY a JSON object (no prose, no code fences) with exactly these keys: "
    '"name", "email", "company", "title", "phone". '
    "Use an empty string for any field that is not present. "
    "If the name appears in CJK characters, prefer the Latin/English version if both exist."
)

def extract_namecard(image_bytes: bytes, mime_type: str = "image/jpeg", *, provider, api_key, model) -> dict:
    b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
    if provider == "openai":
        response = httpx.post(
            "https://api.openai.com/v1/responses",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model, "store": False, "max_output_tokens": 400,
                "input": [{"role": "user", "content": [
                    {"type": "input_text", "text": EXTRACTION_PROMPT},
                    {"type": "input_image", "image_url": f"data:{mime_type};base64,{b64}"},
                ]}],
            },
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("status") != "completed":
            raise ValueError("OpenAI did not complete the card extraction. Try again.")
        text = "".join(part.get("text", "") for item in payload.get("output", [])
                       if item.get("type") == "message"
                       for part in item.get("content", []) if part.get("type") == "output_text").strip()
    elif provider == "anthropic":
        msg = Anthropic(api_key=api_key).messages.create(
            model=model,
            max_tokens=400,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": mime_type, "data": b64},
                    },
                    {"type": "text", "text": EXTRACTION_PROMPT},
                ],
            }],
        )
        text = msg.content[0].text.strip()
    else:
        raise ValueError("Choose anthropic or openai as VISION_PROVIDER.")
    # Defensive: strip code fences if model returns them
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        raise ValueError("The model did not return valid card data. Try another photo.") from None
    if not isinstance(data, dict):
        raise ValueError("The model did not return a contact object.")
    # Normalise
    return {
        "name":    (data.get("name") or "").strip(),
        "email":   (data.get("email") or "").strip(),
        "company": (data.get("company") or "").strip(),
        "title":   (data.get("title") or "").strip(),
        "phone":   (data.get("phone") or "").strip(),
    }

