import os
import pytest
from pathlib import Path
import json
from project.app import app, db, models

TEST_DB = "test.db"


@pytest.fixture
def client():
    BASE_DIR = Path(__file__).resolve().parent.parent
    app.config["TESTING"] = True
    app.config["DATABASE"] = BASE_DIR.joinpath(TEST_DB)
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{BASE_DIR.joinpath(TEST_DB)}"

    with app.app_context():
        db.create_all()  # setup
        yield app.test_client()  # tests run here
        db.drop_all()  # teardown


def login(client, username, password):
    """Login helper function"""
    return client.post(
        "/login",
        data=dict(username=username, password=password),
        follow_redirects=True,
    )


def logout(client):
    """Logout helper function"""
    return client.get("/logout", follow_redirects=True)


def test_index(client):
    response = client.get("/", content_type="html/text")
    assert response.status_code == 200


def test_database(client):
    """initial test. ensure that the database exists"""
    tester = Path("test.db").is_file()
    assert tester


def test_empty_db(client):
    """Ensure database is blank"""
    rv = client.get("/")
    assert b"No entries yet. Add some!" in rv.data


def test_login_logout(client):
    """Test login and logout using helper functions"""
    rv = login(client, app.config["USERNAME"], app.config["PASSWORD"])
    assert b"You were logged in" in rv.data
    rv = logout(client)
    assert b"You were logged out" in rv.data
    rv = login(client, app.config["USERNAME"] + "x", app.config["PASSWORD"])
    assert b"Invalid username" in rv.data
    rv = login(client, app.config["USERNAME"], app.config["PASSWORD"] + "x")
    assert b"Invalid password" in rv.data


def test_messages(client):
    """Ensure that user can post messages"""
    login(client, app.config["USERNAME"], app.config["PASSWORD"])
    rv = client.post(
        "/add",
        data=dict(title="<Hello>", text="<strong>HTML</strong> allowed here"),
        follow_redirects=True,
    )
    assert b"No entries here so far" not in rv.data
    assert b"&lt;Hello&gt;" in rv.data
    assert b"<strong>HTML</strong> allowed here" in rv.data


def test_delete_message(client):
    """Ensure the messages are being deleted"""
    rv = client.get("/delete/1")
    data = json.loads(rv.data)
    assert data["status"] == 1


def test_search_with_non_matching_query(client):
    # Create a post in the database with title and text
    post = models.Post(title="Test Post", text="This is a test post")
    db.session.add(post)
    db.session.commit()

    # Search with a query that does not match the post
    response = client.get("/search/?query=nothing")
    assert response.status_code == 200
    assert b"Test Post" not in response.data  # Ensure the post title does not appear
    assert (
        b"This is a test post" not in response.data
    )  # Ensure the post text does not appear


def test_search_with_matching_query(client):
    # Create a post in the database with title and text
    post = models.Post(title="Test Post", text="This is a test post")
    db.session.add(post)
    db.session.commit()

    # Search with a query that matches the post
    response = client.get("/search/?query=test")
    assert response.status_code == 200
    assert b"Test Post" in response.data  # Check if the post title appears
    assert b"This is a test post" in response.data  # Check if the post text appears


def test_protected_delete_route_without_login(client):
    """Ensure the delete route is not accessible without login"""
    # Attempt to access the delete route without logging in
    response = client.get("/delete/1")  # Assuming post with ID 1 exists

    # Verify that the status code is 401 (Unauthorized)
    assert response.status_code == 401

    # Parse the JSON response and check for the correct message
    data = json.loads(response.data)
    assert data["status"] == 0
    assert data["message"] == "Please log in."


def test_protected_delete_route_with_login(client):
    """Ensure the delete route is accessible when logged in"""

    # Log in the user by setting session data
    with client.session_transaction() as sess:
        sess["logged_in"] = True

    # Attempt to access the delete route
    response = client.get("/delete/1")  # Assuming post with ID 1 exists

    # Verify that the status code is 200 (OK)
    assert response.status_code == 200

    # Parse the JSON response and check for the correct message
    data = json.loads(response.data)
    assert data["status"] == 1
    assert data["message"] == "Post Deleted"


def test_delete_message(client):
    """Ensure the messages are being deleted"""
    rv = client.get("/delete/1")
    data = json.loads(rv.data)
    assert data["status"] == 0
    login(client, app.config["USERNAME"], app.config["PASSWORD"])
    rv = client.get("/delete/1")
    data = json.loads(rv.data)
    assert data["status"] == 1
