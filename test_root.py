from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest


@pytest.fixture
def mock_load_mode(monkeypatch):
    monkeypatch.setenv("LOAD_MODE", "local")


@pytest.fixture
def mock_config_path(monkeypatch, tmpdir):
    mock_config = tmpdir.join("config.yaml")
    mock_config.write("""
cookie:
  expiry_days: 30
  key: dummy_signature_key
  name: test_gas_app_login
credentials:
  usernames:
    test_user:
      email: test_user@example.com
      failed_login_attempts: 0
      logged_in: false
      name: Test User
      password: $2b$12$dummyhashedpassword
preauthorized:
  emails:
  - test_user@example.com
    """)
    monkeypatch.setattr("utils.CONFIG_PATH", Path(mock_config))


def test_dummy():
    assert True


def test_home_page(mock_load_mode, mock_config_path):
    """
    Test the home page of the application.

    This test loads the home page script, sets the load mode to local,
    runs the application, and checks for any exceptions. It also verifies
    that the title of the home page is as expected.
    """
    at = AppTest.from_file("home.py")
    at.secrets["LOAD_MODE"] = "local"
    at.run()

    assert not at.exception

    assert at.title[0].value == "Welcome on Carburoam 🚘💸🛢️ newcomer !"


def test_register_page(mock_load_mode, mock_config_path):
    at = AppTest.from_file("home.py")
    at.secrets["LOAD_MODE"] = "local"
    at.switch_page("pages/register.py")
    at.run()
    assert not at.exception
    assert at.title[0].value == "Register to Carburoam 🚘💸🛢️"
