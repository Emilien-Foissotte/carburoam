import logging
import random
import string
from datetime import datetime, timedelta

import bcrypt
import sqlalchemy
import streamlit as st

from models import User, VerificationCode
from session import db_session
from utils import dump_config, init_authenticator, send_email

logger = logging.getLogger("gas_station_app")

authenticator, config = init_authenticator()

st.title("Need Help ? 🆘")
with st.expander("Forgot username"):
    try:
        username_of_forgotten_username, email_of_forgotten_username = (
            authenticator.forgot_username()
        )
        if username_of_forgotten_username:
            logger.info("Username sent")
            # The developer should securely transfer the username to the user.
            body = f"Your username is {username_of_forgotten_username}"
            send_email(
                subject="Your username",
                body=body,
                recipients=[email_of_forgotten_username],
            )
            st.success("Username has been sent to your email. Please check your email.")
        elif username_of_forgotten_username == False:
            logger.error("Username not found")
            st.error("Email not found")
    except Exception as e:
        st.error(e)

with st.expander("Forgot password"):
    # check that the user is in the emails provided.
    with st.form(key="form_forgot_password"):
        mail = st.text_input("Email")
        submitted = st.form_submit_button("Submit")
        if submitted:
            logger.info("User asked for a password reset")
            user = db_session.query(User).filter(User.email == mail).first()
            if user:
                # check if a previous code exists
                user_id = user.id
                previous_code = (
                    db_session.query(VerificationCode)
                    .filter(VerificationCode.user_id == user_id)
                    .first()
                )
                if previous_code:
                    logger.info("Previous code exists")
                    if previous_code.created_at > datetime.now() - timedelta(minutes=5):
                        st.warning(
                            "A code has been already sent to your email. Please check your email and spam."
                        )
                    else:
                        logger.info("Code expired")
                        st.error("Code has expired. Please request a new one")
                        db_session.delete(previous_code)
                        try:
                            db_session.commit()
                        except sqlalchemy.exc.IntegrityError:
                            db_session.rollback()
                            st.error("Code already deleted")
                else:
                    logger.info("No previous code, generating new one")
                    # generate a random password to send by email and add to database
                    random_verification_code = "".join(
                        random.choices(string.ascii_letters + string.digits, k=6)
                    ).replace(" ", "")
                    new_verification_code = VerificationCode(
                        user_id=user.id,
                        created_at=datetime.now(),
                        code=random_verification_code,
                    )
                    db_session.add(new_verification_code)
                    try:
                        db_session.commit()
                    except sqlalchemy.exc.IntegrityError:
                        db_session.rollback()
                        st.error("Code already exists")
                    # send the email
                    body = f"Your verification code is {random_verification_code}"
                    send_email(
                        subject="Your verification code",
                        body=body,
                        recipients=[user.email],
                    )
                    st.success(
                        "A uniqude code to generate a new password has been sent to your email. Please check your email and spam."
                    )
                    st.warning("Code is valid for 5 minutes")

            else:
                st.error("Email not found")
    # make a form to reset password with code
    with st.form(key="form_reset_password"):
        code = st.text_input("Verification code")
        submitted = st.form_submit_button("Submit")
        if submitted:
            logger.info("User submitted a code")
            verification_code = (
                db_session.query(VerificationCode)
                .filter(VerificationCode.code == code)
                .first()
            )
            if verification_code:
                logger.info("Code found")
                if verification_code.created_at > datetime.now() - timedelta(minutes=5):
                    st.success("Code is valid")
                    logger.info("Code is valid")
                    # get the user
                    user = (
                        db_session.query(User)
                        .filter(User.id == verification_code.user_id)
                        .first()
                    )
                    # reset the password
                    st.success(user.username)
                    new_password = "".join(
                        random.choices(string.ascii_letters + string.digits, k=16)
                    ).replace(" ", "")
                    config["credentials"]["usernames"][user.username]["password"] = (
                        bcrypt.hashpw(
                            new_password.encode("utf-8"), bcrypt.gensalt()
                        ).decode("utf-8")
                    )
                    # send email
                    body = f"Your new password is {new_password}"
                    send_email(
                        subject="Your new password", body=body, recipients=[user.email]
                    )
                    dump_config(config)
                    st.success(
                        "New password has been sent to your email. Please check your email and spam."
                    )
                    db_session.delete(verification_code)
                    try:
                        db_session.commit()
                    except sqlalchemy.exc.IntegrityError:
                        db_session.rollback()
                        st.error("Code already deleted")
                else:
                    logger.info("Code expired")
                    st.error("Code has expired. Please request a new one")
                    db_session.delete(verification_code)
                    try:
                        db_session.commit()
                    except sqlalchemy.exc.IntegrityError:
                        db_session.rollback()
                        st.error("Code already deleted")
            else:
                st.error("Code not found")
st.sidebar.page_link("home.py", label="Back to main page 🏠")
