"""
Tests para endpoints de usuarios
"""
from app.models.user import User
from app.db import Base, engine


def test_create_user(client):
    """
    Test crear usuario
    """
    response = client.post(
        "/users/",
        json={"email": "test@example.com", "full_name": "Test User"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["full_name"] == "Test User"
    assert "id" in data


def test_list_users(client):
    """
    Test listar usuarios
    """
    # Crear un usuario primero
    client.post(
        "/users/",
        json={"email": "list@example.com", "full_name": "List User"}
    )

    response = client.get("/users/")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert any(u["email"] == "list@example.com" for u in data)


def test_get_user(client):
    """
    Test obtener usuario por ID
    """
    # Crear un usuario
    create_response = client.post(
        "/users/",
        json={"email": "get@example.com", "full_name": "Get User"}
    )
    user_id = create_response.json()["id"]

    # Obtener el usuario
    response = client.get(f"/users/{user_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "get@example.com"


def test_delete_user(client):
    """
    Test eliminar usuario
    """
    # Crear un usuario
    create_response = client.post(
        "/users/",
        json={"email": "delete@example.com", "full_name": "Delete User"}
    )
    user_id = create_response.json()["id"]

    # Eliminar el usuario
    response = client.delete(f"/users/{user_id}")
    assert response.status_code == 200

    # Verificar que no existe
    response = client.get(f"/users/{user_id}")
    assert response.status_code == 404


def test_duplicate_email(client):
    """
    Test que no se puede crear usuario con email duplicado
    """
    # Crear primer usuario
    client.post(
        "/users/",
        json={"email": "duplicate@example.com", "full_name": "User 1"}
    )

    # Intentar crear otro con el mismo email
    response = client.post(
        "/users/",
        json={"email": "duplicate@example.com", "full_name": "User 2"}
    )
    assert response.status_code == 400