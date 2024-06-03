import logging
import os
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

import requests
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy.sql import text

from models import CustomStation, User, VerificationCode
from session import db_session
from sidebar import make_sidebar
from utils import VERSION, init_authenticator, send_email

logger = logging.getLogger("gas_station_app")
st.set_page_config(
    page_title="Carburoam",
    page_icon="⛽",
)

load_dotenv()
authenticator, config = init_authenticator()

if st.session_state["authentication_status"]:
    if st.session_state["username"] == "admin":
        st.write(f'Welcome *{st.session_state["name"]}*')
        st.title("Admin dashboard 🛠️")
        st.divider()
        st.subheader("Main KPIs about the app")
        # display view counts json from goatcounter
        st.subheader("View counts")
        # make a request with a json body
        last_week = datetime.now() - timedelta(days=7)
        url = "https://emilienfoissotte.goatcounter.com/api/v0/stats/total/"
        headers = {
            "Authorization": f"Bearer {os.getenv('GOATCOUNTER_API_KEY')}",
        }
        r_last_week = requests.get(
            url,
            headers=headers,
            # start is a date-time string, compute as last week
            data={"start": last_week, "include_paths": [34133008]},
        )
        r_last_month = requests.get(
            url,
            headers=headers,
            # start is a date-time string, compute as last month
            data={"start": last_week - timedelta(days=30), "include_paths": [34133008]},
        )

        if r_last_week.status_code == 200:
            data_count = r_last_week.json()
            c1, c2 = st.columns(2)
            with c1:
                st.metric("Total views last week", data_count["total"])
            if r_last_month.status_code == 200:
                data_count_month = r_last_month.json()
                with c2:
                    st.metric("Total views last month", data_count_month["total"])
        else:
            st.write(r_last_week.status_code)
            st.error("Failed to get the view counts")
            logger.error("Failed to get the view counts")
        # display a count of users
        st.subheader("Users")
        c1, c2 = st.columns(2)
        with c1:
            count_users = db_session.query(User).count()
            st.metric("Total users", count_users)
        with c2:
            # make a pure sql query on this one
            conn = st.connection("gas_db", type="sql")
            df_result = conn.query(
                "SELECT COUNT(DISTINCT(user_id)) as total FROM custom_stations", ttl=60
            )

            count_users_custom_stations = df_result.iloc[0]["total"]
            st.metric("Users with custom stations", count_users_custom_stations)
            # count expired verification codes
        st.subheader("Verification codes")
        c1, c2 = st.columns(2)
        with c1:
            count_verification_codes = db_session.query(VerificationCode).count()
            st.metric("Total verification codes", count_verification_codes)
        with c2:
            count_expired_codes = (
                db_session.query(VerificationCode)
                .filter(
                    VerificationCode.created_at < datetime.now() - timedelta(minutes=5)
                )
                .count()
            )
            st.metric("Expired verification codes", count_expired_codes)
        # count custom stations
        st.subheader("Custom stations")
        count_custom_stations = db_session.query(CustomStation).count()
        st.metric("Custom stations", count_custom_stations)
        st.divider()
        st.subheader("Admin actions on Users")
        with st.expander("Reset a user password"):
            try:
                username_forgot_pw, email_forgot_password, random_password = (
                    authenticator.forgot_password()
                )
                if username_forgot_pw:
                    logger.info("New password sent")
                    st.success("New password sent securely")
                    st.success(f"New password to sent to user is {random_password}")
                    # Random password to be transferred to user securely
                    body = f"Your new password is {random_password}"
                    send_email(
                        subject="Your password",
                        body=body,
                        recipients=[email_forgot_password],
                    )
                elif not username_forgot_pw and username_forgot_pw is not None:
                    st.error("Username not found")
            except Exception as e:
                st.error(e)
        # download config file
        with st.expander("Download Credentials file"):
            # if config file exists
            if os.path.exists("config.yaml"):
                logger.info("Config file found")
                with open("config.yaml", "rb") as file:
                    btn = st.download_button(
                        label="Download file",
                        data=file,
                        file_name="config.yaml",
                        mime="text/yaml",
                    )
            else:
                st.write("No config file found")
        st.divider()
        st.subheader("Admin actions on Database")
        # query the database
        with st.expander("Query database"):
            try:
                with st.form(key="form_query_database"):
                    query = st.text_input("Query")
                    submitted = st.form_submit_button("Submit")
                    if submitted:
                        logger.info("User queried the database")
                        conn = st.connection("gas_db", type="sql")
                        result = conn.query(query, ttl=60)
                        st.dataframe(result)
            except Exception as e:
                st.error(e)
        # query the database
        with st.expander("Commit database"):
            try:
                with st.form(key="form_modify_database"):
                    query = st.text_input("Query")
                    submitted = st.form_submit_button("Submit")
                    if submitted:
                        logger.info("User modified the database")
                        conn = st.connection("gas_db", type="sql")
                        with conn.session as s:
                            result = s.execute(text(query))
                            s.commit()
            except Exception as e:
                st.error(e)
        # flush expired verification codes
        with st.expander("Flush expired verification codes"):
            with st.form(key="form_flush_expired_verification_codes"):
                submitted = st.form_submit_button("Flush")
                if submitted:
                    logger.info("User flushed expired verification codes")
                    with st.spinner("Flushing expired verification codes"):
                        try:
                            db_session.query(VerificationCode).filter(
                                VerificationCode.created_at
                                < datetime.now() - timedelta(minutes=5)
                            ).delete()
                            st.success("Expired verification codes flushed")
                            db_session.commit()
                        except Exception as e:
                            st.error(e)
        # download database file db.sqlite3
        with st.expander("Download Database file"):
            with open("db.sqlite3", "rb") as file:
                btn = st.download_button(
                    label="Download file",
                    data=file,
                    file_name="db.sqlite3",
                    mime="application/sqlite3",
                )
        st.divider()
        st.subheader("Admin actions on ETL")
        # check if alive
        if os.path.exists("pid.txt"):
            with open("pid.txt", "r") as file:
                pid = int(file.read())
            # check if the process is still running
            status = subprocess.run(["ps", "-p", str(pid)], stdout=subprocess.PIPE)
            if status.returncode == 0:
                st.success("ETL is running")
            else:
                st.error("ETL is not running")
        else:
            st.error("No pid file found")
        # restart ETL
        with st.expander("Show status files for ETL Job"):
            files = list(Path("outputs/").glob("*.txt"))
            # add a form to remove output logs files
            with st.form(key="form_remove_logs"):
                submitted = st.form_submit_button("Remove logs")
                if submitted:
                    logger.info("User triggered log files removal")
                    for file in files:
                        file.unlink()
                    st.success("Files removed")
            files += ["pid.txt", "lastjob.txt"]
            for file in files:
                st.caption(file)
                if os.path.exists(file):
                    with open(file, "r") as file:
                        # read line by line
                        for line in file.readlines():
                            st.write(line)
                else:
                    st.write(f"No file {file} found")
        with st.expander("ETL thread"):
            with st.form(key="form_etl_command"):
                submitted = st.form_submit_button("Kill ETL")
                if submitted:
                    logger.info("User triggered etl reboot command")
                    if Path("pid.txt").exists():
                        # echo the content of the pid file
                        with open("pid.txt", "r") as file:
                            pid = file.read()
                            command = f"kill {pid}"
                            with st.spinner("Executing command"):
                                # write the output of the command
                                output = subprocess.run(
                                    command, shell=True, capture_output=True
                                )
                                st.write(output.stdout.decode())
                            # remove the pid file, ok even if not exists (means cleanup successfull)
                            Path("pid.txt").unlink(missing_ok=True)
                    else:
                        st.error("No pid file found")
            # form to remove last job txt file
            with st.form(key="form_remove_lastjob"):
                submitted = st.form_submit_button("Remove last job file")
                if submitted:
                    logger.info("User triggered lastjob file removal")
                    if Path("lastjob.txt").exists():
                        Path("lastjob.txt").unlink()
                        st.success("File removed")
                    else:
                        st.error("No lastjob file found")
        st.divider()
        st.subheader("Admin actions on Host")
        with st.expander("Trigger shell commands on host"):
            with st.form(key="form_shell_command"):
                command = st.text_input("Command")
                submitted = st.form_submit_button("Submit")
                if submitted:
                    logger.info("User triggered shell command")
                    with st.spinner("Executing command"):
                        # write the output of the command
                        output = subprocess.run(
                            command, shell=True, capture_output=True
                        )
                        st.write(output.stdout.decode())
    else:
        st.error("You are not authorized to access this page")
st.sidebar.page_link("home.py", label="🏠 Back to main page ")
make_sidebar(VERSION)
