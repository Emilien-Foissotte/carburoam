from importlib.metadata import version
from pathlib import Path

import pytest
import requests
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


@pytest.fixture
def mock_config_path_dynamically(monkeypatch, tmpdir):
    mock_config = tmpdir.join("config.yaml")
    version_stauth = version("streamlit_authenticator")
    # request github repo demo config
    response = requests.get(
        f"https://raw.githubusercontent.com/mkhorasani/Streamlit-Authenticator/refs/tags/{version_stauth}/config.yaml"
    )

    # dump result to config
    mock_config.write(response.raw)
    monkeypatch.setattr("utils.CONFIG_PATH", Path(mock_config))


def test_dummy():
    assert True


def test_about_page(mock_load_mode, mock_config_path):
    """
    Test the about page of the application.
    """
    at = AppTest.from_file("home.py")
    at.secrets["LOAD_MODE"] = "local"
    at.switch_page("pages/about.py")
    at.run()
    assert not at.exception


@pytest.mark.online
def test_about_page_dynamic(mock_load_mode, mock_config_path_dynamically):
    """
    Test the about page of the application.
    """
    at = AppTest.from_file("home.py")
    at.secrets["LOAD_MODE"] = "local"
    at.switch_page("pages/about.py")
    at.run()
    assert not at.exception


def test_demo_page(mock_load_mode, mock_config_path):
    """
    Test the demo page of the application.
    """
    at = AppTest.from_file("home.py")
    at.secrets["LOAD_MODE"] = "local"
    at.switch_page("pages/demo.py")
    at.run()
    assert not at.exception
    assert at.title[0].value == "Stations dashboard ⛽"


def test_forgot_page(mock_load_mode, mock_config_path):
    """
    Test the forgot page of the application.
    """
    at = AppTest.from_file("home.py")
    at.secrets["LOAD_MODE"] = "local"
    at.switch_page("pages/forgot.py")
    at.run()
    assert not at.exception
    assert at.title[0].value == "Need Help ? 🆘"


def test_home_page(mock_load_mode, mock_config_path):
    """
    Test the home page of the application.
    """
    at = AppTest.from_file("home.py")
    at.secrets["LOAD_MODE"] = "local"
    at.run()

    assert not at.exception

    assert at.title[0].value == "Welcome on Carburoam 🚘💸🛢️ newcomer !"


def test_profile_page(mock_load_mode, mock_config_path):
    at = AppTest.from_file("home.py")
    at.secrets["LOAD_MODE"] = "local"
    at.switch_page("pages/profile.py")
    at.run()
    assert not at.exception


def test_register_page(mock_load_mode, mock_config_path):
    at = AppTest.from_file("home.py")
    at.secrets["LOAD_MODE"] = "local"
    at.switch_page("pages/register.py")
    at.run()
    assert not at.exception
    assert at.title[0].value == "Register to Carburoam 🚘💸🛢️"


def test_stations_page(mock_load_mode, mock_config_path):
    at = AppTest.from_file("home.py")
    at.secrets["LOAD_MODE"] = "local"
    at.switch_page("pages/stations.py")
    at.run()
    assert not at.exception


### for more automation, we need Playwright plugins and codegen
# import re
# from playwright.sync_api import Playwright, sync_playwright, expect
#
#
#
#
# def test_go_to_demo(playwright: Playwright) -> None:
#     browser = playwright.chromium.launch(headless=False)
#     context = browser.new_context()
#     page = context.new_page()
#     page.goto("http://localhost:8501/")
#     page.get_by_role("link", name="Demo without registration").click()
