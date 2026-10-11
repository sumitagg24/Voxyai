"""GET /api/history pagination (P6.3): boundaries, clamping and totals."""

from __future__ import annotations

from tests.conftest import ApiUser


def _seed_history(web_app, user_id: int, count: int) -> None:
    conn = web_app._get_db()
    conn.executemany(
        "INSERT INTO transcriptions (user_id, text, mode, language) VALUES (?, ?, 'formal', 'en')",
        [(user_id, f"note {i}") for i in range(count)],
    )
    conn.commit()
    conn.close()


def test_history_pagination_walks_all_pages_without_gaps(app_client):
    client, web_app = app_client
    user = ApiUser(client, "pagination@gmail.com")
    _seed_history(web_app, user.user_id, 7)

    seen_ids = []
    first = client.get("/api/history?page=1&page_size=3", headers=user.headers).get_json()
    assert len(first["history"]) == 3
    assert first["pagination"] == {
        "page": 1,
        "page_size": 3,
        "total": 7,
        "total_pages": 3,
        "has_more": True,
    }
    seen_ids += [h["id"] for h in first["history"]]

    second = client.get("/api/history?page=2&page_size=3", headers=user.headers).get_json()
    assert len(second["history"]) == 3
    assert second["pagination"]["has_more"] is True
    seen_ids += [h["id"] for h in second["history"]]

    third = client.get("/api/history?page=3&page_size=3", headers=user.headers).get_json()
    assert len(third["history"]) == 1
    assert third["pagination"]["has_more"] is False
    assert third["pagination"]["total_pages"] == 3
    seen_ids += [h["id"] for h in third["history"]]

    # Past the end: empty page, no error, has_more false.
    past_end = client.get("/api/history?page=4&page_size=3", headers=user.headers).get_json()
    assert past_end["history"] == []
    assert past_end["pagination"]["has_more"] is False

    assert len(seen_ids) == 7
    assert len(set(seen_ids)) == 7, "pages must not overlap or repeat rows"


def test_history_page_size_is_clamped_to_100(app_client):
    client, web_app = app_client
    user = ApiUser(client, "clamp@gmail.com")
    _seed_history(web_app, user.user_id, 5)

    huge = client.get("/api/history?page=1&page_size=1000", headers=user.headers).get_json()
    assert huge["pagination"]["page_size"] == 100
    assert len(huge["history"]) == 5

    # Nonsense values fall back to server defaults rather than erroring.
    zero = client.get("/api/history?page=1&page_size=0", headers=user.headers).get_json()
    assert zero["pagination"]["page_size"] == 100
    negative_page = client.get("/api/history?page=-3&page_size=abc", headers=user.headers).get_json()
    assert negative_page["pagination"]["page"] == 1
    assert negative_page["pagination"]["page_size"] == 100


def test_history_default_page_keeps_the_old_100_row_window(app_client):
    """Clients that send no pagination parameters still get at most 100 rows."""
    client, web_app = app_client
    user = ApiUser(client, "defaultwindow@gmail.com")
    _seed_history(web_app, user.user_id, 105)

    payload = client.get("/api/history", headers=user.headers).get_json()
    assert len(payload["history"]) == 100
    assert payload["pagination"]["total"] == 105
    assert payload["pagination"]["has_more"] is True


def test_history_pagination_is_scoped_to_the_session_user(app_client):
    """Pagination must count and return only the caller's own rows."""
    client, web_app = app_client
    alice = ApiUser(client, "pag-alice@gmail.com")
    bob = ApiUser(client, "pag-bob@gmail.com")
    _seed_history(web_app, alice.user_id, 4)
    _seed_history(web_app, bob.user_id, 2)

    payload = client.get("/api/history?page=1&page_size=10", headers=alice.headers).get_json()
    assert payload["pagination"]["total"] == 4
    assert len(payload["history"]) == 4
