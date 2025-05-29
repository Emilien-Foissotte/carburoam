import logging

import sqlalchemy
import streamlit as st

from models import User
from session import db_session
from sidebar import make_sidebar
from utils import (
    VERSION,
    dump_config,
    init_authenticator,
    send_discord_notification,
)

logger = logging.getLogger("gas_station_app")
st.set_page_config(
    page_title="Carburoam",
    page_icon="⛽",
)


authenticator, config = init_authenticator()

st.title("Register to Carburoam 🚘💸🛢️")

if st.session_state["authentication_status"]:
    name = st.session_state["name"]
    # ask to logout before registering
    st.warning(
        (
            f"You are already logged in {name}, "
            "please logout before attempting to register"
        )
    )
else:
    try:
        (
            email_of_registered_user,
            username_of_registered_user,
            name_of_registered_user,
        ) = authenticator.register_user()
        if email_of_registered_user:
            logger.info("User registered")
            new_user = User(
                username=username_of_registered_user,
                email=email_of_registered_user,
                name=name_of_registered_user,
            )
            db_session.add(new_user)
            try:
                db_session.commit()
            except sqlalchemy.exc.IntegrityError:
                db_session.rollback()
                st.error("Username or email already exists")
            send_discord_notification(
                topic="new_user",
                message=f"New user registered: {name_of_registered_user} ({username_of_registered_user})",
            )
            st.success(
                (
                    "User registered successfully, "
                    f"welcome {name_of_registered_user}"
                )
            )
            dump_config(config)
    except Exception as e:
        st.error(e)
st.sidebar.page_link("home.py", label="🏠 Back to main page")
make_sidebar(VERSION)
