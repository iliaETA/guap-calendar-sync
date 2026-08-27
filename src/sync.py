"""Telegram delivery helpers."""

from __future__ import annotations

import requests


def split_message(text: str, limit: int = 4000) -> list[str]:
    chunks: list[str] = []
    rest = text
    while len(rest) > limit:
        split_at = rest.rfind("\n\n", 0, limit)
        if split_at < limit // 2:
            split_at = limit
        chunks.append(rest[:split_at])
        rest = rest[split_at:].lstrip()
    if rest:
        chunks.append(rest)
    return chunks


def send_telegram(text: str, token: str, chat_id: str) -> None:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    for chunk in split_message(text):
        response = requests.post(url, json={"chat_id": chat_id, "text": chunk}, timeout=30)
        response.raise_for_status()
