from starlette.testclient import TestClient


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
