"""The polite catalog client: robots.txt, delay, bot protection. No real network."""

import httpx
import pytest

from app.catalog import http as catalog_http
from app.catalog.http import CatalogBlocked, PoliteClient, decode

ROBOTS = "User-agent: *\nDisallow: /ajax/\ncrawl-delay: 120\n"


def make_client(handler, sleeps):
    catalog_http._last_request_at = 0.0
    return PoliteClient(transport=httpx.MockTransport(handler), sleep=sleeps.append, min_delay=5)


def handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/robots.txt":
        return httpx.Response(200, text=ROBOTS)
    if request.url.path == "/content.php":
        return httpx.Response(202, headers={"x-amzn-waf-action": "challenge"})
    if request.url.path == "/forbidden.php":
        return httpx.Response(403)
    assert "FlowsaicCatalogBot" in request.headers["user-agent"]
    return httpx.Response(200, content="<h1>ok</h1>".encode())


def test_waits_the_robots_crawl_delay_between_requests():
    sleeps = []
    client = make_client(handler, sleeps)
    assert client.get("/preview_course_nopop.php?catoid=10&coid=1") == "<h1>ok</h1>"
    client.get("/preview_course_nopop.php?catoid=10&coid=2")
    assert client.delay == 120  # robots.txt beats the smaller minimum
    # One wait before the first page (after robots.txt) and one before the second.
    assert len(sleeps) == 2 and all(110 < wait <= 120 for wait in sleeps)


def test_never_fetches_paths_robots_disallows():
    client = make_client(handler, [])
    with pytest.raises(CatalogBlocked, match="robots.txt"):
        client.get("/ajax/preview_course.php?catoid=10&coid=1")


@pytest.mark.parametrize("path", ["/content.php?catoid=10&navoid=370", "/forbidden.php"])
def test_bot_protection_stops_the_run(path):
    client = make_client(handler, [])
    with pytest.raises(CatalogBlocked, match="bot protection"):
        client.get(path)


def test_decode_falls_back_to_cp1252():
    assert decode("PHSC 2023 – x".encode()) == "PHSC 2023 – x"
    assert decode(b"PHSC 2023\xa0-\xa0Physical") == "PHSC 2023\xa0-\xa0Physical"
