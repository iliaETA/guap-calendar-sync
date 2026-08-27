"""Download the current GUAP schedule page."""

from __future__ import annotations

import requests


USER_AGENT = "guap-calendar-sync/1.0 (+https://github.com/iliaETA/guap-calendar-sync)"


def download_schedule(url: str, timeout: int = 30) -> str:
    response = requests.get(
        url,
        headers={"User-Agent": USER_AGENT, "Accept-Language": "ru-RU,ru;q=0.9"},
        timeout=timeout,
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    html = response.text
    if "Расписание занятий" not in html:
        raise ValueError("ГУАП вернул страницу без расписания")
    return html
