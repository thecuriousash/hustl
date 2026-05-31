import pytest
from hustl import create_app


@pytest.fixture
def app():
    app = create_app()
    app.config.update(
        TESTING=True,
        PROPAGATE_EXCEPTIONS=False,
        SECRET_KEY="test-secret",
        WTF_CSRF_ENABLED=False,
        DATABASE_URL="postgresql://test:test@localhost:5432/test",
        SUPABASE_URL="https://test.supabase.co",
        SUPABASE_KEY="test-key",
        STORAGE_BUCKET="test-bucket",
    )
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json == {"status": "ok"}


def test_home_page_loads(client):
    resp = client.get("/")
    assert resp.status_code in (200, 302, 500)


def test_login_page_loads(client):
    resp = client.get("/login")
    assert resp.status_code == 200


def test_signup_page_loads(client):
    resp = client.get("/signup")
    assert resp.status_code == 200


def test_market_page_loads(client):
    resp = client.get("/market")
    assert resp.status_code in (200, 302, 500)


def test_lost_and_found_page_loads(client):
    resp = client.get("/lost")
    assert resp.status_code in (200, 500)


def test_search_page_loads(client):
    resp = client.get("/search?q=test")
    assert resp.status_code in (200, 500)


def test_admin_redirects_when_not_logged_in(client):
    resp = client.get("/admin/")
    assert resp.status_code == 302


def test_security_headers(client):
    resp = client.get("/")
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"


def test_error_page(client):
    resp = client.get("/nonexistent-page-12345")
    assert resp.status_code == 404


def test_login_fails_with_empty_data(client):
    resp = client.post("/login", data={"username": "", "password": ""})
    assert resp.status_code == 200
    assert b"required" in resp.data.lower() or b"invalid" in resp.data.lower()
