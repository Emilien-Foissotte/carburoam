import logging
import os
from datetime import datetime, timedelta
from pathlib import Path

import streamlit as st
from sqlalchemy.sql import text

from models import VerificationCode
from session import db_session
from utils import init_authenticator, send_email

logger = logging.getLogger("gas_station_app")

authenticator, config = init_authenticator()

if st.session_state["authentication_status"]:
    if st.session_state["username"] == "admin":
        st.write(f'Welcome *{st.session_state["name"]}*')
        st.title("Admin dashboard 🛠️")
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
                    # Random password to be transferred to user securely
                    body = f"Your new password is {random_password}"
                    send_email(
                        subject="Your password",
                        body=body,
                        recipients=[email_forgot_password],
                    )
                elif username_forgot_pw == False:
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
                            result = s.execute(query)
                            st.write(result)
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
        st.subheader("Admin actions on Stations")
        with st.expander("Show status files for ETL Job"):
            files = list(Path("outputs/").glob("*.txt"))
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
        st.divider()

    else:
        st.error("You are not authorized to access this page")
st.sidebar.page_link("home.py", label="Back to main page 🏠")
