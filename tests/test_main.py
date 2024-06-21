from starlette.testclient import TestClient

from rsserpent_rev.main import ATOM_MIMETYPE, RSS_MIMETYPE


def test_index(client: TestClient) -> None:
    """Test if the index route works properly."""
    response = client.get("/")
    assert response.status_code == 200
    assert "RSSerpent is up & running" in response.text


def test_all_routes(client: TestClient) -> None:
    """Test if the all_routes routes works properly."""
    response = client.get("/all_routes")
    assert response.status_code == 200
    assert "Plugins Information" in response.text


def test_title_include(client: TestClient) -> None:
    response = client.get("/_/example/10?title_include=Example")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == RSS_MIMETYPE
    assert response.text.count("<item>") == 10

    response = client.get("/_/example/10?title_include=Example Title 10")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == RSS_MIMETYPE
    assert response.text.count("<item>") == 1


def test_title_exclude(client: TestClient) -> None:
    response = client.get("/_/example/10?title_exclude=Example")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == RSS_MIMETYPE
    assert response.text.count("<item>") == 0

    response = client.get("/_/example/10?title_exclude=Example Title 10")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == RSS_MIMETYPE
    assert response.text.count("<item>") == 9


def test_description_include(client: TestClient) -> None:
    response = client.get("/_/example/10?description_include=Example")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == RSS_MIMETYPE
    assert response.text.count("<item>") == 10

    response = client.get("/_/example/10?description_include=Example Description 10")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == RSS_MIMETYPE
    assert response.text.count("<item>") == 1


def test_description_exclude(client: TestClient) -> None:
    response = client.get("/_/example/10?description_exclude=Example")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == RSS_MIMETYPE
    assert response.text.count("<item>") == 0

    response = client.get("/_/example/10?description_exclude=Example Description 10")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == RSS_MIMETYPE
    assert response.text.count("<item>") == 9


def test_category_include(client: TestClient) -> None:
    response = client.get("/_/example/10?category_include=example1")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == RSS_MIMETYPE
    assert response.text.count("<item>") == 5

    response = client.get("/_/example/10?category_include=example")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == RSS_MIMETYPE
    assert response.text.count("<item>") == 10


def test_category_exclude(client: TestClient) -> None:
    response = client.get("/_/example/10?category_exclude=example1")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == RSS_MIMETYPE
    assert response.text.count("<item>") == 5

    response = client.get("/_/example/10?category_exclude=example")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == RSS_MIMETYPE
    assert response.text.count("<item>") == 0


def test_limit(client: TestClient) -> None:
    response = client.get("/_/example/10?limit=5")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == RSS_MIMETYPE
    assert response.text.count("<item>") == 5


def test_example_cache_with_limit(client: TestClient) -> None:
    response = client.get("/_/example/10")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == RSS_MIMETYPE
    assert response.text.count("<item>") == 10

    response = client.get("/_/example/10?limit=5")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == RSS_MIMETYPE
    assert response.text.count("<item>") == 5

    # make sure limit do not affect the cache, so the response should be 10
    response = client.get("/_/example/10")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == RSS_MIMETYPE
    assert response.text.count("<item>") == 10


def test_example_cache_with_limit_fg(client: TestClient) -> None:
    response = client.get("/_/example/feedgen.atom")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == ATOM_MIMETYPE
    assert response.text.count("<entry>") == 2

    response = client.get("/_/example/feedgen.atom?limit=1")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == ATOM_MIMETYPE
    assert response.text.count("<entry>") == 1

    # make sure limit do not affect the cache, so the response should always be 2
    response = client.get("/_/example/feedgen.atom")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == ATOM_MIMETYPE
    assert response.text.count("<entry>") == 2


def test_multiple_filter(client: TestClient) -> None:
    """Test if the filter works properly."""
    response = client.get("/_/example/10?title_include=Example&category_include=example1")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == RSS_MIMETYPE
    assert response.text.count("<item>") == 5


def test_multiple_filter_and_limit(client: TestClient) -> None:
    """Test if the filter and limit works properly."""
    response = client.get("/_/example/10?title_include=Example&category_include=example1&limit=3")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == RSS_MIMETYPE
    # limit should be applied after filtering
    assert response.text.count("<item>") == 3


def test_date_before(client: TestClient) -> None:
    response = client.get("/_/example/feedgen?date_before=2025-04-23T10%3A20%3A30.400%2B08%3A00")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == RSS_MIMETYPE
    assert response.text.count("<item>") == 2

    response = client.get("/_/example/feedgen?date_before=2010-02-04T10%3A20%3A30.400%2B08%3A00")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == RSS_MIMETYPE
    assert response.text.count("<item>") == 1


def test_date_after(client: TestClient) -> None:
    response = client.get("/_/example/feedgen?date_after=2010-02-04T10%3A20%3A30.400%2B08%3A00")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == RSS_MIMETYPE
    assert response.text.count("<item>") == 1

    response = client.get("/_/example/feedgen?date_after=2010-02-04T10%3A20%3A30.400%2B08%3A00")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == RSS_MIMETYPE
    assert response.text.count("<item>") == 1
