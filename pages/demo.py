import folium
import streamlit as st
from streamlit_folium import st_folium
from streamlit_geolocation import streamlit_geolocation

from models import GasType, Station
from session import db_session
from utils import bounding_stations

st.title(" Stations dashboard ⛽")
st.caption("Welcome to the demo stations dashboard.")
st.caption(
    (
        "*NB: Keep in mind that followed stations won't be saved. Create an account to"
        " save your followed stations.*"
    )
)
st.divider()
st.subheader("Manage preferred gas types")
gas_types = db_session.query(GasType).all()
default_gas_types = [gas.name for gas in gas_types if gas.name in ["SP95", "Gazole"]]

options = st.multiselect(
    label="Which gas type would you like to follow?",
    options=[gas.name for gas in gas_types],
    default=default_gas_types,
)
st.subheader("Add a new station")
if "geolocated" not in st.session_state:
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
            st.toast("You have been geolocated", icon="🌍")
            st.session_state["map_zoom_demo"] = ZOOM_START
            st.session_state["center_demo"] = CENTER_START
            st.session_state["geolocated_demo"] = True
# load center map
if "center_demo" not in st.session_state:
    st.session_state["center_demo"] = CENTER_START
# load session state map zoom
if "map_zoom_demo" not in st.session_state:
    st.session_state["map_zoom_demo"] = ZOOM_START
# load stations
if "stations_demo" not in st.session_state:
    st.session_state["stations_demo"] = {}
if "stations_followed_demo" not in st.session_state:
    st.session_state["stations_followed_demo"] = []

# list of stations
# map of stations
map_center = st.session_state["center_demo"]
map_zoom = st.session_state["map_zoom_demo"]
st.info("Click on a marker on the map to add a new station 👇")
m = folium.Map(location=CENTER_START, zoom_start=map_zoom)
fg = folium.FeatureGroup(name="Stations markers")
for key, station in st.session_state["stations_demo"].items():
    # color is red if the station is in the user's stations followed
    if station.id in [s.id for s in st.session_state["stations_followed_demo"]]:
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
