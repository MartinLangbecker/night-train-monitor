"""Shared Snälltåget API functions for availability and trondheim scrapers."""

import json
import http.client
import ssl
from urllib.request import Request, urlopen

TOKEN_URL = "https://www.snalltaget.se/token/v2"
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36")

_conn = None


def _get_conn():
    """Get or create persistent HTTPS connection to Snälltåget API."""
    global _conn
    if _conn is None:
        ctx = ssl.create_default_context()
        _conn = http.client.HTTPSConnection("apiv2.snalltaget.se", timeout=30, context=ctx)
    return _conn


def get_token():
    """Fetch anonymous Bearer token (900s TTL). Uses urllib (one-off, no keep-alive needed)."""
    req = Request(TOKEN_URL, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())["access_token"]


def api_post(token, path, body):
    """POST to Snälltåget API with Bearer auth and keep-alive."""
    global _conn
    headers = {
        "User-Agent": USER_AGENT,
        "Origin": "https://www.snalltaget.se",
        "Referer": "https://www.snalltaget.se/",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
        "Connection": "keep-alive",
    }
    data = json.dumps(body).encode()
    for attempt in range(2):
        try:
            conn = _get_conn()
            conn.request("POST", path, body=data, headers=headers)
            resp = conn.getresponse()
            return json.loads(resp.read().decode("utf-8"))
        except (http.client.RemoteDisconnected, ConnectionResetError, BrokenPipeError, OSError):
            _conn = None
            if attempt == 0:
                continue
            raise


def fetch_calendar(token, origin, destination, direction, begin, end):
    """Fetch price calendar for a date range."""
    body = {"direction": direction, "origin": origin, "destination": destination,
            "begin": begin, "end": end, "passengers": ["AD"]}
    return api_post(token, "/orientation/calendar", body)


def fetch_searchjourney(token, origin, destination, date, oppositedate=None):
    """Fetch journey details for a specific date."""
    body = {
        "origin": origin,
        "destination": destination,
        "departure": date,
        "oppositedate": oppositedate,
        "passengers": [{"type": "AD"}],
        "travelWithpet": False,
    }
    return api_post(token, "/orientation/searchjourney", body)
