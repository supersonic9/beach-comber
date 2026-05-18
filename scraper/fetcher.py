import random
import time

import requests
from requests import Session

from scraper.config import BASE_URL, REQUEST_DELAY_MIN, REQUEST_DELAY_MAX

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://casa.sapo.pt/",
}

_session: Session | None = None


def _get_session() -> Session:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update(HEADERS)
    return _session


def get_page(area: str, prop_type: str, page: int) -> str:
    """Fetch HTML for one search page. Retries 3× on 429/5xx with exponential backoff."""
    url = BASE_URL.format(prop_type=prop_type, area=area)
    params = {"pn": page}
    session = _get_session()

    for attempt in range(3):
        try:
            resp = session.get(url, params=params, timeout=30)
            if resp.status_code == 200:
                _sleep()
                return resp.text
            if resp.status_code in (429, 500, 502, 503, 504):
                wait = (2 ** attempt) * 5 + random.uniform(0, 2)
                time.sleep(wait)
                continue
            resp.raise_for_status()
        except requests.HTTPError:
            raise  # non-retryable (404, 403, etc.) — don't retry
        except requests.RequestException:
            if attempt == 2:
                raise
            time.sleep((2 ** attempt) * 5)

    raise RuntimeError(f"Failed to fetch {url}?pn={page} after 3 attempts")


def _sleep() -> None:
    time.sleep(random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX))
