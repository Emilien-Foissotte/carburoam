import streamlit as st

from utils import init_authenticator
from models import User
from session import db_session

authenticator, config = init_authenticator()

if st.session_state["authentication_status"] is None:
    try:
        (
            email_of_registered_user,
            username_of_registered_user,
            name_of_registered_user,
        ) = authenticator.register_user(preauthorization=False)
        if email_of_registered_user:
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
            st.success("User registered successfully")
    except Exception as e:
        st.error(e)
st.sidebar.page_link("home.py", label="Click here to go back to main page")
