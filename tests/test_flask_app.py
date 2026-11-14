from app.app import app


def test_home_serves_spa_and_static_assets():
    client = app.test_client()
    response = client.get("/")
    assert response.status_code == 200
    assert b"Accessibility Testing Research Lab" in response.data
    script = client.get("/static/js/app.js")
    assert script.status_code == 200
    assert b"TC14" in script.data


def test_health_of_missing_path_remains_explicit():
    client = app.test_client()
    response = client.get("/not-a-page")
    assert response.status_code == 404
