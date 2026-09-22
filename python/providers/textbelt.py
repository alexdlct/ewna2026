"""Textbelt SMS transport."""

from __future__ import annotations

from typing import Any, Callable, Optional


TEXTBELT_ENDPOINT = "https://textbelt.com/text"


class TextbeltProvider:
    """Send SMS messages through Textbelt's HTTP API."""

    def __init__(
        self,
        api_key: str,
        *,
        timeout: float = 15,
        request_post: Optional[Callable[..., Any]] = None,
    ) -> None:
        if not api_key:
            raise ValueError("Textbelt API key is required")
        self.api_key = api_key
        self.timeout = timeout
        self._request_post = request_post

    def send_message(self, phone: str, message: str) -> str:
        request_post = self._request_post
        if request_post is None:
            import requests

            request_post = requests.post

        response = request_post(
            TEXTBELT_ENDPOINT,
            data={
                "phone": phone,
                "message": message,
                "key": self.api_key,
            },
            timeout=self.timeout,
        )
        response.raise_for_status()

        try:
            result = response.json()
        except ValueError as exc:
            raise RuntimeError("Textbelt returned an invalid JSON response") from exc

        if not isinstance(result, dict) or not result.get("success"):
            error = result.get("error") if isinstance(result, dict) else None
            raise RuntimeError(error or "Textbelt SMS failed")

        text_id = result.get("textId")
        if text_id is None:
            raise RuntimeError("Textbelt response did not include a textId")
        return str(text_id)
