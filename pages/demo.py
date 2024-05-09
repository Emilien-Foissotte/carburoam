import logging
from datetime import datetime

import folium
import streamlit as st
from streamlit_folium import st_folium
from streamlit_geolocation import streamlit_geolocation

from models import GasType, Station
from session import db_session
from utils import bounding_stations, get_prices_demo

logger = logging.getLogger("gas_station_app")


def on_click_center_map(station_id):
    logger.info("Center map on station")
    # grab the station from the id
    station = db_session.query(Station).filter_by(id=station_id).first()
    # update the center of the map
    st.session_state["center"] = [station.latitude / 100000, station.longitude / 100000]
    st.session_state["map_zoom"] = 16


logger.info("Demo page loaded")
if "stations_followed_demo" not in st.session_state:
    st.session_state["stations_followed_demo"] = []
if "gastypes_followed_demo" not in st.session_state:
    st.session_state["gastypes_followed_demo"] = ["SP95", "Gazole"]

st.title(" Stations dashboard ⛽")
st.caption("Welcome to the demo stations dashboard.")
st.caption(
    (
        "*NB: Keep in mind that followed stations won't be saved. Create an account to"
        " save your followed stations.*"
    )
)
get_prices_demo(
    followed_gastypes_list=st.session_state["gastypes_followed_demo"],
    followed_stations_list=st.session_state["stations_followed_demo"],
)
if st.session_state.get("lastjob"):
    st.metric(
        datetime.strftime(st.session_state["lastjob"], "%Y-%m-%d"),
        "last extract of prices",
    )
st.divider()
st.subheader("Manage preferred gas types")
gas_types = db_session.query(GasType).all()
default_gas_types = []
for gas_name in st.session_state["gastypes_followed_demo"]:
    gas = db_session.query(GasType).filter_by(name=gas_name).first()
    if gas:
        default_gas_types.append(gas.name)

options = st.multiselect(
    label="Which gas type would you like to follow?",
    options=[gas.name for gas in gas_types],
    default=default_gas_types,
)
options_set = set(options)
gastypes_followed_set = set(st.session_state["gastypes_followed_demo"])
evolutions_gas = {
    "add": options_set - gastypes_followed_set,
    "remove": gastypes_followed_set - options_set,
}
for gastype_name_selected in evolutions_gas["remove"]:
    gas_type = db_session.query(GasType).filter_by(name=gastype_name_selected).first()
    st.session_state["gastypes_followed_demo"].remove(gastype_name_selected)
    st.toast(f"Gas type {gastype_name_selected} removed", icon="🛢️")
for gastype_name_selected in evolutions_gas["add"]:
    if gastype_name_selected not in st.session_state["gastypes_followed_demo"]:
        st.session_state["gastypes_followed_demo"].append(gastype_name_selected)
        st.toast(f"Gas type {gastype_name_selected} added", icon="🛢️")


st.subheader("Add a new station")
if "geolocated_demo" not in st.session_state:
    st.session_state["geolocated_demo"] = False

CENTER_START = [45.920587344733654, 2.8234863281250004]
ZOOM_START = 6
# CENTER_START = [47.8278, -0.6905]
# ZOOM_START = 16
if not st.session_state["geolocated_demo"]:
    st.write("Click here to automatically be geolocated 👇")
    location = streamlit_geolocation()
    if location.get("latitude") is not None and location.get("longitude") is not None:
        CENTER_START = [location["latitude"], location["longitude"]]
        ZOOM_START = 16
        if not st.session_state["geolocated_demo"]:
            st.session_state["geolocated_demo"] = True
            st.toast("You have been geolocated", icon="🌍")
            st.session_state["map_zoom_demo"] = ZOOM_START
            st.session_state["center_demo"] = CENTER_START
# load center map
if "center_demo" not in st.session_state:
    st.session_state["center_demo"] = CENTER_START
# load session state map zoom
if "map_zoom_demo" not in st.session_state:
    st.session_state["map_zoom_demo"] = ZOOM_START
# load followed stations
if "stations_demo" not in st.session_state:
    st.session_state["stations_demo"] = {}
if "toast_display_demo" not in st.session_state:
    st.session_state["toast_display_demo"] = False


# list of stations
# map of stations
map_center = st.session_state["center_demo"]
map_zoom = st.session_state["map_zoom_demo"]
st.info("Zoom in to see the markers and click to add a new station👇", icon="ℹ️")

m = folium.Map(location=CENTER_START, zoom_start=map_zoom)
fg = folium.FeatureGroup(name="Stations markers")
for key, station in st.session_state["stations_demo"].items():
    # color is red if the station is in the user's stations followed
    if str(station.id) in [
        s.get("id") for s in st.session_state["stations_followed_demo"]
    ]:
        color = "red"
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
        if not st.session_state["toast_display_demo"]:
            st.toast("Stations display activated ✅")
            st.session_state["toast_display_demo"] = True
        stations = bounding_stations(st_data["bounds"])
        # udpate stations by sync dict in session state and stations
        # remove stations not in the bounds
        items = list(st.session_state["stations_demo"].items())
        for key, station in items:
            if station not in stations:
                st.session_state["stations_demo"].pop(key)
        # add stations in the bounds
        for station in stations:
            if station.id not in st.session_state["stations_demo"].keys():
                st.session_state["stations_demo"][station.id] = station
    elif (
        st_data.get("bounds", {}).get("_southWest", {}).get("lat") is not None
        and st_data.get("zoom", 16) < 12
    ):
        if st.session_state["toast_display_demo"]:
            st.toast("Stations display deactivated ❌")
            st.session_state["toast_display_demo"] = False

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
        if station_id not in [
            s.get("id") for s in st.session_state["stations_followed_demo"]
        ]:
            with st.form(key="add_station"):
                # write information about the station
                st.write("Add this station to demo stations 👇")
                station = db_session.query(Station).filter_by(id=station_id).first()
                st.write(f"Address: {station.address.upper()}")
                st.write(f"Town: {station.town.upper()}")
                st.write(f"Zip code: {station.zip_code}")
                # add a custom name to the station
                custom_name = st.text_input("Custom name")
                custom_name = custom_name.upper()
                submitted = st.form_submit_button("Add station")
                if submitted:
                    custom_station = {
                        "id": station_id,
                        "custom_name": custom_name,
                    }
                    st.session_state["stations_followed_demo"].append(custom_station)
                    st.toast(f"Station {custom_name} added", icon="🎉")
                    # flush the session state for stations
                    st.session_state["stations_demo"] = {}
        else:
            with st.form(key="remove_station"):
                # write information about the station
                st.write("Remove this station from demo stations 👇")
                station = db_session.query(Station).filter_by(id=station_id).first()
                st.write(f"Address: {station.address.upper()}")
                st.write(f"Town: {station.town.upper()}")
                st.write(f"Zip code: {station.zip_code}")
                for custom_station in st.session_state["stations_followed_demo"]:
                    if custom_station.get("id") == station_id:
                        custom_name = custom_station.get("custom_name")
                        break
                st.write(f"Custom name: {custom_name}")
                submitted = st.form_submit_button("Remove station")
                if submitted:
                    custom_station = {
                        "id": station_id,
                        "custom_name": custom_name,
                    }
                    st.session_state["stations_followed_demo"].remove(custom_station)
                    st.toast(f"Station {custom_name} removed", icon="🗑️")
                    # flush the session state for stations
                    st.session_state["stations_demo"] = {}

st.sidebar.page_link("home.py", label="Back to main page 🏠")
