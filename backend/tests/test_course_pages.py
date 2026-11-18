"""Course detail page parsing and the rolling crawl's page choice. Fake HTML, no network."""

from datetime import UTC, datetime, timedelta

from app.catalog.course_build import build_row
from app.catalog.course_pages import parse_course_page, stale_coids

# Shaped like a real catalog page: hidden spacer spans after links, <br> between blocks,
# a closing <hr> and the page footer after the course text.
PAGE = """<html><body><table><tr><td><p>
<h1 id='course_preview_title'>ZOO 2023\xa0-\xa0Imaginary Zoology</h1><hr>Prerequisites:
<a href="preview_course_nopop.php?catoid=10&coid=1">ZOO 1013</a><span style="display: none !important">&#160;</span>\xa0or
<a href="preview_course_nopop.php?catoid=10&coid=2">ZOO 1053</a><span style="display: none !important">&#160;</span>\xa0or higher.<br>
Corequisites: <a href="preview_course_nopop.php?catoid=10&coid=3">ZOO 2021</a><span style="display: none !important">&#160;</span>.<br>
Animals that do not exist. 3 hours.  Fall, spring.  <br>ACTS Course Equivalent: ZOO 1004<br></p>
<br><hr><div style="float: right"><a href="#">Back to Top</a></div>
</td></tr></table></body></html>"""


def test_parse_course_page():
    title, body = parse_course_page(PAGE)
    assert title == "ZOO 2023 - Imaginary Zoology"
    assert body.split("\n") == [
        "Prerequisites: ZOO 1013 or ZOO 1053 or higher.",
        "Corequisites: ZOO 2021.",
        "Animals that do not exist. 3 hours. Fall, spring.",
        "ACTS Course Equivalent: ZOO 1004",
    ]
    row = build_row(title, body)
    assert row["code"] == "ZOO 2023"
    assert row["prereqs"] == "ZOO 1013|ZOO 1053"
    assert row["coreqs"] == "ZOO 2021"
    assert row["description"] == "Animals that do not exist. 3 hours. Fall, spring."


def test_a_page_without_a_course_is_none():
    # A broken coid redirects to an unrelated catalog page.
    assert parse_course_page("<html><h1 id='acalog-content'>Graduate Catalog</h1></html>") is None


def test_stale_pages_never_fetched_first_then_oldest():
    now = datetime(2026, 11, 30, tzinfo=UTC)
    fetched = {
        "1": "2026-11-29T00:00:00+00:00",  # fresh: skipped
        "2": "2026-11-16T00:00:00+00:00",
        "3": "2026-11-10T00:00:00+00:00",
    }
    assert stale_coids(["1", "2", "3", "4"], fetched, now, timedelta(days=7)) == ["4", "3", "2"]
