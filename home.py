import os
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path

import streamlit as st

from utils import WAIT_TIME_SECONDS, get_prices_user, init_authenticator, wait_time


def trigger_etl():
    # create a new uuid for process opening
    uuid_str = str(uuid.uuid4())
    with open(f"outputs/stdout_{uuid_str}.txt", "wb") as out, open(
        f"outputs/stderr_{uuid_str}.txt", "wb"
    ) as err:
        subprocess.Popen([f"{sys.executable}", "utils.py"], stdout=out, stderr=err)


# check if the pid file exists
if not os.path.exists("pid.txt"):
    # if it doesn't exist, trigger the subprocess job
    # delete and remove output files under outputs
    for file in Path("outputs").glob("*.txt"):
        file.unlink()

    if os.path.exists("lastjob.txt"):
        # check the last job date, do not start subprocess if recent
        with open("lastjob.txt", "r") as file:
            date = file.read()
            # parse the date (dumped as datetime.now())
            date = datetime.strptime(date, "%Y-%m-%d %H:%M:%S.%f")
            st.session_state["lastjob"] = date
            # if the detla from now is greater than WAIT_TIME_SECONDS
            if (datetime.now() - date).total_seconds() > WAIT_TIME_SECONDS:
                trigger_etl()
    else:
        trigger_etl()

authenticator, config = init_authenticator()
with st.sidebar:
    st.page_link("pages/demo.py", label="Demo without registration", icon="👀")
authenticator.login(location="sidebar")
if st.session_state["authentication_status"]:
    authenticator.logout("Logout", "sidebar")
    st.write(f'Welcome *{st.session_state["name"]}*')
    st.title("Stations 🚘💸🛢️")
    # create a dataframe from the custom stations and the prices
    get_prices_user(st.session_state["username"])
    st.divider()
    if st.session_state.get("lastjob"):
        st.metric(
            datetime.strftime(st.session_state["lastjob"], "%Y-%m-%d %H:%M:%S"),
            "Last extract of prices",
        )
    st.caption("Customize your experience ⬇️")
    if st.session_state["username"] == "admin":
        st.title("Admin dashboard 🛠️")
        st.page_link("pages/admin.py", label="Click here to go to admin dashboard")
    st.title("Profile dashboard 📝")
    st.page_link("pages/profile.py", label="Click here to go to your profile dashboard")
    st.title("Stations dashboard ⛽")
    st.page_link(
        "pages/stations.py", label="Click here to go to your stations dashboard"
    )

elif st.session_state["authentication_status"] is False:
    try_dict = st.session_state["failed_login_attempts"]
    try_number = try_dict.get(st.session_state["username"], 0)
    if try_number > 1:
        st.page_link("pages/forgot.py", label="Forgot credentials? Click here for help")
    st.error("Username/password is incorrect.")
    wait_time(try_number)
elif st.session_state["authentication_status"] is None:
    st.warning("👈 Please enter your username and password")
    st.page_link("pages/register.py", label="Not registered ? Click here to register")
    st.page_link("pages/forgot.py", label="Forgot credentials? Click here for help")
