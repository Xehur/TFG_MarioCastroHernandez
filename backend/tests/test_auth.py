"""
Tests para autenticación: registro, login, perfil y protección de endpoints.
"""
from fastapi import status


def test_register_success(anon_client):
    """Registro de un usuario nuevo devuelve token y datos del usuario."""
    resp = anon_client.post(
        "/auth/register",
        json={
            "email": "newuser@example.com",
            "password": "secret123",
            "full_name": "New User",
        },
    )
    assert resp.status_code == status.HTTP_201_CREATED
    data = resp.json()
    assert data["token_type"] == "bearer"
    assert "access_token" in data
    assert data["user"]["email"] == "newuser@example.com"
    assert data["user"]["is_active"] is True
    # La contraseña nunca debe exponerse
    assert "password" not in data["user"]
    assert "hashed_password" not in data["user"]


def test_register_duplicate_email(anon_client):
    """No se puede registrar dos veces el mismo email."""
    payload = {"email": "dup@example.com", "password": "secret123"}
    first = anon_client.post("/auth/register", json=payload)
    assert first.status_code == status.HTTP_201_CREATED

    second = anon_client.post("/auth/register", json=payload)
    assert second.status_code == status.HTTP_400_BAD_REQUEST


def test_register_short_password(anon_client):
    """Contraseña demasiado corta es rechazada por validación."""
    resp = anon_client.post(
        "/auth/register",
        json={"email": "shortpw@example.com", "password": "123"},
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_login_success(anon_client):
    """Login con credenciales correctas devuelve token."""
    anon_client.post(
        "/auth/register",
        json={"email": "login@example.com", "password": "mypassword"},
    )
    resp = anon_client.post(
        "/auth/login",
        json={"email": "login@example.com", "password": "mypassword"},
    )
    assert resp.status_code == status.HTTP_200_OK
    assert "access_token" in resp.json()


def test_login_wrong_password(anon_client):
    """Login con contraseña incorrecta devuelve 401."""
    anon_client.post(
        "/auth/register",
        json={"email": "wrongpw@example.com", "password": "correctpass"},
    )
    resp = anon_client.post(
        "/auth/login",
        json={"email": "wrongpw@example.com", "password": "incorrect"},
    )
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


def test_login_nonexistent_user(anon_client):
    """Login de un usuario inexistente devuelve 401."""
    resp = anon_client.post(
        "/auth/login",
        json={"email": "ghost@example.com", "password": "whatever"},
    )
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


def test_me_with_token(anon_client):
    """GET /auth/me con token válido devuelve el usuario."""
    reg = anon_client.post(
        "/auth/register",
        json={"email": "me@example.com", "password": "secret123", "full_name": "Me"},
    )
    token = reg.json()["access_token"]
    resp = anon_client.get(
        "/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["email"] == "me@example.com"


def test_me_without_token(anon_client):
    """GET /auth/me sin token devuelve 401."""
    resp = anon_client.get("/auth/me")
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


def test_me_invalid_token(anon_client):
    """GET /auth/me con token inválido devuelve 401."""
    resp = anon_client.get(
        "/auth/me", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


def test_protected_images_requires_auth(anon_client):
    """El listado de imágenes requiere autenticación."""
    resp = anon_client.get("/images/")
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


def test_protected_users_requires_auth(anon_client):
    """El listado de usuarios requiere autenticación."""
    resp = anon_client.get("/users/")
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


def _register_and_headers(anon_client, email, password="secret123", full_name="U"):
    reg = anon_client.post(
        "/auth/register",
        json={"email": email, "password": password, "full_name": full_name},
    )
    token = reg.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_update_profile_name_and_email(anon_client):
    """PATCH /auth/me actualiza nombre y email."""
    headers = _register_and_headers(anon_client, "edit@example.com")
    resp = anon_client.patch(
        "/auth/me",
        headers=headers,
        json={"full_name": "Nuevo Nombre", "email": "edited@example.com"},
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["full_name"] == "Nuevo Nombre"
    assert data["email"] == "edited@example.com"


def test_update_profile_email_conflict(anon_client):
    """No se puede cambiar el email a uno ya registrado por otro usuario."""
    _register_and_headers(anon_client, "taken@example.com")
    headers = _register_and_headers(anon_client, "mover@example.com")
    resp = anon_client.patch(
        "/auth/me", headers=headers, json={"email": "taken@example.com"}
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST


def test_update_password_wrong_current(anon_client):
    """Cambiar contraseña con la actual incorrecta devuelve 400."""
    headers = _register_and_headers(anon_client, "pw1@example.com", password="original123")
    resp = anon_client.patch(
        "/auth/me",
        headers=headers,
        json={"current_password": "incorrecta", "new_password": "nuevapass123"},
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST


def test_update_password_success(anon_client):
    """Cambio de contraseña correcto permite iniciar sesión con la nueva."""
    headers = _register_and_headers(anon_client, "pw2@example.com", password="original123")
    resp = anon_client.patch(
        "/auth/me",
        headers=headers,
        json={"current_password": "original123", "new_password": "nuevapass123"},
    )
    assert resp.status_code == status.HTTP_200_OK

    login = anon_client.post(
        "/auth/login",
        json={"email": "pw2@example.com", "password": "nuevapass123"},
    )
    assert login.status_code == status.HTTP_200_OK


def test_update_profile_requires_auth(anon_client):
    """PATCH /auth/me sin token devuelve 401."""
    resp = anon_client.patch("/auth/me", json={"full_name": "X"})
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED
