import logging

import sqlalchemy
import streamlit as st

from models import GasType, User
from session import db_session
from sidebar import make_sidebar
from utils import VERSION, dump_config, init_authenticator

logger = logging.getLogger("gas_station_app")
st.set_page_config(
    page_title="Carburoam",
    page_icon="⛽",
)


authenticator, config = init_authenticator()

if st.session_state["authentication_status"]:
    logger.info("Profile page loaded")
    name = st.session_state["name"]
    username = st.session_state["username"]
    st.write(f"Welcome *{name}*")
    st.title("Profile dashboard 📝")
    st.markdown("This is your profile dashboard.")
    st.divider()
    st.write("Your details are as follows:")
    st.write(f"Username: {username}")
    st.write(f"Name: {name}")
    st.write(f"Email: {config['credentials']['usernames'][username]['email']}")
    st.divider()
    with st.form(key="add_preferred_gastypes"):
        st.subheader("Manage preferred gas types")
        user = db_session.query(User).filter_by(username=username).first()
        gas_types = db_session.query(GasType).all()
        gastypes_followed = user.gastypes
        id_gastypes_followed = [gastype.id for gastype in gastypes_followed]
        checkboxs_dict = {}
        is_followed_list = []
        for gas_type in gas_types:
            is_followed = gas_type.id in id_gastypes_followed
            is_followed_list.append(is_followed)
            value = st.checkbox(label=gas_type.name, value=is_followed)
            checkboxs_dict[gas_type.id] = value
        submitted = st.form_submit_button()
        if submitted:
            logger.info("User modified preferred gas types")
            for key, value in checkboxs_dict.items():
                if value and key not in id_gastypes_followed:
                    gas_type = db_session.query(GasType).filter_by(id=key).first()
                    user.gastypes.append(gas_type)
                    st.toast(f"Preferred gas type {gas_type.name} added", icon="🛢️")

                elif not value and key in id_gastypes_followed:
                    gas_type = db_session.query(GasType).filter_by(id=key).first()
                    st.toast(f"Preferred gas type {gas_type.name} removed", icon="🛢️")
                    user.gastypes.remove(gas_type)
            try:
                db_session.commit()
            except sqlalchemy.exc.IntegrityError as e:
                print(e)
                db_session.rollback()
                st.error("Error adding preferred gas types")

    with st.expander("Modify details for name/email"):
        try:
            if authenticator.update_user_details(st.session_state["username"]):
                logger.info("User modified details")
                st.success("Entries modified successfully")
            dump_config(config)
        except Exception as e:
            st.error(e)
    with st.expander("Reset password"):
        try:
            if authenticator.reset_password(st.session_state["username"]):
                logger.info("User modified password")
                st.success("Password modified successfully")
            dump_config(config)
        except Exception as e:
            st.error(e)
    with st.expander("Delete account"):
        with st.form(key="delete_account"):
            st.warning("This action is irreversible")
            submitted = st.form_submit_button()
            if submitted:
                logger.info("User deleted account")
                try:
                    del config["credentials"]["usernames"][st.session_state["username"]]
                    st.success("Account deleted successfully")
                    dump_config(config)
                    authenticator.logout(location="unrendered")
                except Exception as e:
                    st.error(e)
else:
    st.error("You must be logged in to access this page")
st.sidebar.page_link("home.py", label="🏠 Back to main page")
make_sidebar(VERSION)
