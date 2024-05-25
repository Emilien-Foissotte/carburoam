import folium
import streamlit as st
from streamlit_folium import st_folium
from streamlit_geolocation import streamlit_geolocation

from models import CustomStation, Station, User
from session import db_session
from sidebar import make_sidebar
from utils import VERSION, bounding_stations, init_authenticator

st.set_page_config(
    page_title="Carburoam",
    page_icon="⛽",
)

authenticator, config = init_authenticator()


def on_click_delete_custom_station(custom_station_id):
    custom_station = (
        db_session.query(CustomStation).filter_by(id=custom_station_id).first()
    )
    db_session.delete(custom_station)
    db_session.commit()
    st.toast("Station deleted", icon="🗑️")
    # flush the session state for stations
    st.session_state["stations"] = {}


def render_stations(user_id):
    custom_stations = db_session.query(CustomStation).filter_by(user_id=user.id).all()
    col1, col2, col3 = st.columns(3)
    with col1:
        st.write("Name (Click to center map 🎯)")
    with col2:
        st.write("Edit 📝")
    with col3:
        st.write("Delete 🗑️")

    # create a dataframe from the custom stations
    for custom_station in custom_stations:
        name = custom_station.custom_name.upper()
        with col1:
            st.button(
                name,
                on_click=on_click_center_map,
                type="secondary",
                args=(custom_station.id,),
                key=f"{custom_station.id}-center",
            )
        with col2:
            st.button(
                f"Edit {name}",
                on_click=on_click_edit_custom_station,
                type="secondary",
                args=(custom_station.id,),
                key=f"{custom_station.id}-edit",
            )
        with col3:
            st.button(
                f"Delete {name}",
                on_click=on_click_delete_custom_station,
                args=(custom_station.id,),
                type="primary",
                key=f"{custom_station.id}-delete",
            )


def on_click_center_map(station_id):
    # grab the station from the id
    station = db_session.query(Station).filter_by(id=station_id).first()
    # update the center of the map
    st.session_state["center"] = [station.latitude / 100000, station.longitude / 100000]
    st.session_state["map_zoom"] = 16


def on_click_edit_custom_station(station_id):
    if st.session_state.get("edit_station_id") is not None:
        if st.session_state["edit_station_id"] == station_id:
            st.session_state["edit_station_id"] = None
        else:
            st.session_state["edit_station_id"] = station_id
            # center on the map
            on_click_center_map(station_id)

    else:
        st.session_state["edit_station_id"] = station_id
        # center on the map
        on_click_center_map(station_id)


if st.session_state["authentication_status"]:
    ### header
    name = st.session_state["name"]
    username = st.session_state["username"]
    st.write(f"Welcome *{name}*")
    st.title(" Stations dashboard ⛽")
    st.markdown("This is your stations dashboard.")
    st.divider()
    ### list of stations
    user = db_session.query(User).filter_by(username=username).first()
    render_stations(user.id)
    st.divider()
    ### edit station if clicked
    if st.session_state.get("edit_station_id") is not None:
        station_id = st.session_state.get("edit_station_id")
        custom_station = (
            db_session.query(CustomStation)
            .filter_by(user_id=user.id, id=station_id)
            .first()
        )
        if custom_station is not None:
            with st.form(key="edit_station"):
                st.write("Edit this station 👇")
                station = db_session.query(Station).filter_by(id=station_id).first()
                st.write(f"Address: {station.address.upper()}")
                st.write(f"Town: {station.town.upper()}")
                st.write(f"Zip code: {station.zip_code}")
                st.write(f"Name: {custom_station.custom_name.upper()}")
                # add a custom name to the station
                custom_name = st.text_input("New Custom name")
                custom_name = custom_name.upper()
                submitted = st.form_submit_button("Edit station")
                if submitted:
                    if custom_name != custom_station.custom_name:
                        custom_station.custom_name = custom_name
                        db_session.add(custom_station)
                        db_session.commit()
                        st.toast(f"Station {custom_name} edited", icon="🎉")
                        # flush the session state for stations
                        st.session_state["stations"] = {}
                    else:
                        st.warning("Custom Name is the same")
    st.subheader("Add a new station")
    if "geolocated" not in st.session_state:
        st.session_state["geolocated"] = False

    CENTER_START = [45.920587344733654, 2.8234863281250004]
    ZOOM_START = 6
    # CENTER_START = [47.8278, -0.6905]
    # ZOOM_START = 16
    if not st.session_state["geolocated"]:
        st.write("Click here to automatically be geolocated 👇")
        location = streamlit_geolocation()
        if (
            location.get("latitude") is not None
            and location.get("longitude") is not None
        ):
            CENTER_START = [location["latitude"], location["longitude"]]
            ZOOM_START = 16
            if not st.session_state["geolocated"]:
                st.toast("You have been geolocated", icon="🌍")
                st.session_state["map_zoom"] = ZOOM_START
                st.session_state["center"] = CENTER_START
                st.session_state["geolocated"] = True
    # load center map
    if "center" not in st.session_state:
        st.session_state["center"] = CENTER_START
    # load session state map zoom
    if "map_zoom" not in st.session_state:
        st.session_state["map_zoom"] = ZOOM_START
    # load stations
    if "stations" not in st.session_state:
        st.session_state["stations"] = {}
    # display station toast
    if "toast_display" not in st.session_state:
        st.session_state["toast_display"] = False

    # list of stations
    # map of stations
    map_center = st.session_state["center"]
    map_zoom = st.session_state["map_zoom"]
    st.info("Zoom in to see the markers and click to add a new station👇", icon="ℹ️")
    m = folium.Map(location=CENTER_START, zoom_start=map_zoom)
    fg = folium.FeatureGroup(name="Stations markers")
    for key, station in st.session_state["stations"].items():
        # color is red if the station is in the user's stations
        if station.id in [s.id for s in user.stations]:
            color = "red"
            # retrieve the custom name of the station
            for station_user in user.stations:
                if station_user.id == station.id:
                    tooltip = f"{station_user.custom_name.upper()}"
        else:
            color = "blue"
            tooltip = f"{station.address.upper()}"
        fg.add_child(
            folium.Marker(
                [station.latitude / 100000, station.longitude / 100000],
                popup=station.id,
                tooltip=tooltip,
                icon=folium.Icon(color=color),
            )
        )
    # call to render Folium map in Streamlit
    st_data = st_folium(
        m,
        center=map_center,
        zoom=map_zoom,
        feature_group_to_add=fg,
        width=725,
        returned_objects=[
            "zoom",
            "center",
            "bounds",
            "last_object_clicked_popup",
            "last_object_clicked_tooltip",
        ],
    )
    if st_data is not None:
        if st_data.get("center") is not None:
            st.session_state["map_center"] = [
                st_data["center"]["lat"],
                st_data["center"]["lng"],
            ]
        if (
            st_data.get("bounds", {}).get("_southWest", {}).get("lat") is not None
            and st_data.get("zoom", 16) > 12
        ):
            if not st.session_state["toast_display"]:
                st.toast("Stations display activated ✅")
                st.session_state["toast_display"] = True

            stations = bounding_stations(st_data["bounds"])
            # udpate stations by sync dict in session state and stations
            # remove stations not in the bounds
            items = list(st.session_state["stations"].items())
            for key, station in items:
                if station not in stations:
                    st.session_state["stations"].pop(key)
            # add stations in the bounds
            for station in stations:
                if station.id not in st.session_state["stations"].keys():
                    st.session_state["stations"][station.id] = station
        elif (
            st_data.get("bounds", {}).get("_southWest", {}).get("lat") is not None
            and st_data.get("zoom", 16) < 12
        ):
            if st.session_state["toast_display"]:
                st.toast("Stations display deactivated ❌")
                st.session_state["toast_display"] = False

        if st_data.get("last_object_clicked_tooltip") is not None:
            st.session_state["last_object_clicked_popup"] = st_data[
                "last_object_clicked_popup"
            ]
            # get the station from the tooltip
            station_id = st_data["last_object_clicked_popup"]
            col1, col2, col3 = st.columns(3)
            with col2:
                st.button(
                    "Center map on selected station",
                    on_click=on_click_center_map,
                    args=(station_id,),
                    type="primary",
                )
            # if station is not in the user's stations
            if station_id not in [str(s.id) for s in user.stations]:
                with st.form(key="add_station"):
                    # write information about the station
                    st.write("Add this station to your stations 👇")
                    station = db_session.query(Station).filter_by(id=station_id).first()
                    st.write(f"Address: {station.address.upper()}")
                    st.write(f"Town: {station.town.upper()}")
                    st.write(f"Zip code: {station.zip_code}")
                    # add a custom name to the station
                    custom_name = st.text_input("Custom name")
                    custom_name = custom_name.upper()
                    submitted = st.form_submit_button("Add station")
                    if submitted:
                        custom_station = CustomStation()
                        custom_station.id = station_id
                        custom_station.user_id = user.id
                        custom_station.custom_name = custom_name
                        db_session.add(custom_station)
                        db_session.commit()
                        st.toast(f"Station {custom_name} added", icon="🎉")
                        # flush the session state for stations
                        st.session_state["stations"] = {}
else:
    st.error("You must be logged in to access this page")
st.sidebar.page_link("home.py", label="🏠 Back to main page")
make_sidebar(VERSION)
