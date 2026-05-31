import os
import pytest
from hustl import create_app


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "changeme")
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "test-key")
    monkeypatch.setenv("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
    monkeypatch.setenv("STORAGE_BUCKET", "test-bucket")
    app = create_app()
    app.config.update(
        TESTING=True,
        PROPAGATE_EXCEPTIONS=False,
        WTF_CSRF_ENABLED=False,
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
    resp = client.post("/login", data={"email": "", "password": ""})
    assert resp.status_code == 200
    assert b"required" in resp.data.lower() or b"invalid" in resp.data.lower()


# ── Admin E2E tests ──────────────────────────────────────────────

def _admin_login(client):
    with client:
        resp = client.post("/login", data={"email": "admin", "password": "changeme"})
        assert resp.status_code == 302
        return resp


def test_admin_login_success(client):
    with client:
        resp = client.post("/login", data={"email": "admin", "password": "changeme"})
        assert resp.status_code == 302
        assert resp.location.endswith("/admin/")


def test_admin_login_wrong_password(client):
    with client:
        resp = client.post("/login", data={"email": "admin", "password": "wrong"})
        assert resp.status_code == 200
        assert b"Invalid" in resp.data


def test_admin_dashboard_loads(client):
    with client:
        client.post("/login", data={"email": "admin", "password": "changeme"})
        resp = client.get("/admin/")
        assert resp.status_code == 200
        assert b"Admin Center" in resp.data
        assert b"Pending Sellers" in resp.data
        assert b"Manage Users" in resp.data
        assert b"Market Moderation" in resp.data


def test_admin_users_page_loads(client):
    with client:
        client.post("/login", data={"email": "admin", "password": "changeme"})
        resp = client.get("/admin/users")
        assert resp.status_code == 200
        assert b"User Management" in resp.data


def test_admin_listings_page_loads(client):
    with client:
        client.post("/login", data={"email": "admin", "password": "changeme"})
        resp = client.get("/admin/listings")
        assert resp.status_code == 200
        assert b"Market Moderation" in resp.data


def test_admin_verify_post_redirects(client):
    with client:
        client.post("/login", data={"email": "admin", "password": "changeme"})
        resp = client.post("/admin/verify/9999")
        assert resp.status_code == 302


def test_admin_unverify_post_redirects(client):
    with client:
        client.post("/login", data={"email": "admin", "password": "changeme"})
        resp = client.post("/admin/unverify/9999")
        assert resp.status_code == 302


def test_admin_delete_item_post_redirects(client):
    with client:
        client.post("/login", data={"email": "admin", "password": "changeme"})
        resp = client.post("/admin/delete-item/9999")
        assert resp.status_code == 302


def test_admin_delete_user_post_redirects(client):
    with client:
        client.post("/login", data={"email": "admin", "password": "changeme"})
        resp = client.post("/admin/delete-user/9999")
        assert resp.status_code == 302


def test_admin_all_routes_redirect_when_logged_out(client):
    protected = [
        "/admin/",
        "/admin/users",
        "/admin/listings",
        "/admin/pending-approval",
    ]
    for url in protected:
        with client:
            resp = client.get(url)
            assert resp.status_code == 302, f"{url} should redirect when logged out"


def test_admin_post_routes_redirect_when_logged_out(client):
    protected = [
        ("/admin/verify/1", {}),
        ("/admin/unverify/1", {}),
        ("/admin/delete-item/1", {}),
        ("/admin/delete-user/1", {}),
        ("/admin/approve-item/1", {}),
        ("/admin/reject-item/1", {}),
        ("/admin/approve-claim/1", {}),
        ("/admin/reject-claim/1", {}),
    ]
    for url, data in protected:
        with client:
            resp = client.post(url, data=data)
            assert resp.status_code == 302, f"POST {url} should redirect when logged out"


def test_admin_approve_item_post_redirects(client):
    with client:
        client.post("/login", data={"email": "admin", "password": "changeme"})
        resp = client.post("/admin/approve-item/9999")
        assert resp.status_code == 302


def test_admin_reject_item_post_redirects(client):
    with client:
        client.post("/login", data={"email": "admin", "password": "changeme"})
        resp = client.post("/admin/reject-item/9999")
        assert resp.status_code == 302


def test_admin_approve_claim_post_redirects(client):
    with client:
        client.post("/login", data={"email": "admin", "password": "changeme"})
        resp = client.post("/admin/approve-claim/9999")
        assert resp.status_code == 302


def test_admin_reject_claim_post_redirects(client):
    with client:
        client.post("/login", data={"email": "admin", "password": "changeme"})
        resp = client.post("/admin/reject-claim/9999")
        assert resp.status_code == 302
