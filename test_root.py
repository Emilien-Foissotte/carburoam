from streamlit.testing.v1 import AppTest


def test_dummy():
    assert True


def test_home_page():
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


def test_register_page():
    at = AppTest.from_file("home.py")
    at.secrets["LOAD_MODE"] = "local"
    at.switch_page("pages/register.py")
    at.run()
    assert not at.exception
    assert at.title[0].value == "Register to Carburoam 🚘💸🛢️"
