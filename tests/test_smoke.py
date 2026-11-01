import pytest

from tests.helpers import login


@pytest.mark.parametrize("path", ["/", "/items", "/categories", "/login", "/register"])
def test_public_pages(client, seed, path):
    assert client.get(path).status_code == 200


@pytest.mark.parametrize("path", ["/publish", "/my/items", "/my/favorites", "/my/history", "/profile"])
def test_member_pages(client, seed, path):
    login(client)
    assert client.get(path).status_code == 200


@pytest.mark.parametrize("path", ["/admin", "/admin/items", "/admin/categories", "/admin/reports"])
def test_admin_pages(client, seed, path):
    login(client, "admin", "Admin@12345")
    assert client.get(path).status_code == 200
