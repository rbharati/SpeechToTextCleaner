import os
import requests

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


def llm_semantic_rewrite(text: str):

    prompt = f"""
Convert this fragmented spoken English into a natural,
grammatically correct sentence.

Keep the meaning unchanged.

Text:
{text}
"""

    url = (
        "https://generativelanguage.googleapis.com"
        "/v1beta/models/gemini-2.0-flash:generateContent"
        f"?key={GEMINI_API_KEY}"
    )

    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt
                    }
                ]
            }
        ]
    }

    try:

        response = requests.post(
            url,
            json=payload,
            timeout=15
        )

        response.raise_for_status()

        data = response.json()

        return (
            data["candidates"][0]
            ["content"]["parts"][0]["text"]
            .strip()
        )

    except Exception as e:

        print("LLM Rewrite Error:", e)

        return text