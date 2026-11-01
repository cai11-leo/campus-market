import re


def get_csrf(client, path="/login"):
    html = client.get(path).get_data(as_text=True)
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match, f"no csrf token found on {path}"
    return match.group(1)


def login(client, student_id="2023001", password="Demo@12345"):
    token = get_csrf(client, "/login")
    return client.post(
        "/login",
        data={
            "student_id": student_id,
            "password": password,
            "csrf_token": token,
        },
        follow_redirects=True,
    )
