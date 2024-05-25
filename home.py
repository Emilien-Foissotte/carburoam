import logging
import os
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path

import pytz
import streamlit as st

from applogging import init_logging
from sidebar import make_sidebar
from utils import (
    VERSION,
    WAIT_TIME_SECONDS,
    get_prices_user,
    init_authenticator,
    wait_time,
)

logger = logging.getLogger("gas_station_app")
st.set_page_config(
    page_title="Carburoam",
    page_icon="⛽",
)


def trigger_etl():
    """
    Trigger the ETL process in a subprocess.
    """
    # create a new uuid for process opening
    str_uuid = str(uuid.uuid4())
    with open(f"outputs/stdout_{str_uuid}.txt", "wb") as out, open(
        f"outputs/stderr_{str_uuid}.txt", "wb"
    ) as err:
        subprocess.Popen([f"{sys.executable}", "utils.py"], stdout=out, stderr=err)


def main():
    # check if the pid file exists
    if not os.path.exists("pid.txt"):
        logger.info("No pid file found, creating one")
        # if it doesn't exist, trigger the subprocess job
        # delete and remove output files under outputs
        for file in Path("outputs").glob("*.txt"):
            # get last modified date
            try:
                last_modified = datetime.fromtimestamp(file.stat().st_mtime)
                # if the file is older than 1 day, remove it
                if (datetime.now() - last_modified).days > 1:
                    logger.info(f"Removing {file}")
                    file.unlink()
            except FileNotFoundError:
                # it means another process has deleted the file
                pass

        if os.path.exists("lastjob.txt"):
            # check the last job date, do not start subprocess if recent
            with open("lastjob.txt", "r") as file:
                date = file.read()
                # parse the date (dumped as datetime.now())
                date = datetime.strptime(date, "%Y-%m-%d %H:%M:%S.%f")
                st.session_state["lastjob"] = date
                # if the detla from now is greater than WAIT_TIME_SECONDS
                if (datetime.now() - date).total_seconds() > WAIT_TIME_SECONDS:
                    logger.info("Last job was not recent, starting new job")
                    trigger_etl()
                else:
                    logger.info("Last job was recent, skipping")
        else:
            trigger_etl()
    if os.path.exists("lastjob.txt"):
        with open("lastjob.txt", "r") as file:
            date = file.read()
            date = datetime.strptime(date, "%Y-%m-%d %H:%M:%S.%f")
            st.session_state["lastjob"] = date

    authenticator, _ = init_authenticator()
    with st.sidebar:
        st.page_link("pages/demo.py", label="Demo without registration", icon="👀")
        authenticator.login(location="sidebar")
    if st.session_state["authentication_status"]:
        logger.info("User logged in")
        authenticator.logout("Logout", "sidebar")
        st.write(f'Welcome on Carburoam, *{st.session_state["name"]}*')
        st.title("Stations 🚘💸🛢️")
        # create a dataframe from the custom stations and the prices
        get_prices_user(st.session_state["username"])
        st.divider()
        if st.session_state.get("lastjob"):
            # convert the date to a string
            last_job_datetime = st.session_state["lastjob"]
            # convert to CET timezone
            last_job_datetime = last_job_datetime.replace(tzinfo=pytz.utc)
            last_job_datetime_paris = last_job_datetime.astimezone(
                pytz.timezone("Europe/Paris")
            )
            last_job_str = datetime.strftime(
                last_job_datetime_paris, "%A, %d %B %Y - %H:%M"
            )
            st.metric(
                last_job_str,
                "last extract of prices",
            )
        st.caption("Customize your experience ⬇️")
        if st.session_state["username"] == "admin":
            st.title("Admin dashboard 🛠️")
            st.page_link("pages/admin.py", label="Click here to go to admin dashboard")
        st.title("Profile dashboard 📝")
        st.page_link(
            "pages/profile.py", label="Click here to go to your profile dashboard"
        )
        st.title("Stations dashboard ⛽")
        st.page_link(
            "pages/stations.py", label="Click here to go to your stations dashboard"
        )

    elif st.session_state["authentication_status"] is False:
        if "failed_login_attempts" in st.session_state:
            try_dict = st.session_state["failed_login_attempts"]
            try_number = try_dict.get(st.session_state["username"], 0)
            logger.warning(f"User {st.session_state['username']} failed to login once")
        else:
            try_number = 0
        if try_number > 1:
            logger.warning(
                f"User {st.session_state['username']} failed to login several times"
            )
            st.page_link(
                "pages/forgot.py", label="Forgot credentials? Click here for help"
            )
        st.error("Username/password is incorrect.")
        wait_time(try_number)
    elif st.session_state["authentication_status"] is None:
        st.title("Welcome on Carburoam 🚘💸🛢️ newcomer !")

        st.warning("👈 Please enter your username and password")
        c0, c1 = st.columns(2)
        with c0:
            st.page_link(
                "pages/register.py", label="Not registered ? Click here to register"
            )
        with c1:
            st.caption(
                "*Want to see a demo of the website before register ?"
                " Sure ! Click on demo on the left 👈*"
            )

        st.write()
        c0, c1 = st.columns(2)
        with c0:
            st.page_link(
                "pages/forgot.py", label="Forgot credentials? Click here for help"
            )
        with c1:
            st.caption(
                "If you didn't entered a real email, don't worry, just DM me ! 🔒"
            )


if __name__ == "__main__":
    f"![](https://emilienfoissotte.goatcounter.com/count?p={os.getenv('TRACKING_NAME')})"
    init_logging()
    main()
    make_sidebar(VERSION)
