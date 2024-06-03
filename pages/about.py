import logging

import streamlit as st

from sidebar import make_sidebar
from utils import VERSION

logger = logging.getLogger("gas_station_app")

st.set_page_config(
    page_title="Carburoam",
    page_icon="⛽",
)

"""
# About this project 🚀

[![Star](https://img.shields.io/github/stars/Emilien-Foissotte/stationsdashboard.svg?logo=github&style=social)](https://github.com/Emilien-Foissotte/stationsdashboard/stargazers)
[![Follow](https://img.shields.io/github/followers/Emilien-Foissotte.svg?style=social)](https://github.com/Emilien-Foissotte)
"""

st.markdown(
    """
This webpage is a demonstration of use of a fun Data Engineering project.  \n  \n
The goal is :
- To scrap public API to retrieve price of Gas Stations in France 🇫🇷 \n \n
- Allow users to save their favorites gas stations and pick them from a map 🌍
- Allow users to save their favorite gas types and see the relevant prices of their nearby stations 👤
\n
"""
)
st.divider()
logger.info("About page loaded")
st.write(
    "Deep dive using tabs on the left, read more about the behind the scenes of the app following my blog"
    "post available [here in french](https://emilien-foissotte.github.io/fr/posts/"
    "2024/05/streamlit-gas-stations/?utm_campaign=GasWebApp) or [here in english](https://emilien-foissotte.github.io/posts/"
    "posts/2024/05/streamlit-gas-stations/?utm_campaign=GasWebApp)"
)

st.success(
    "[Star the repo](https://github.com/Emilien-Foissotte/stationsdashboard/) to show your :heart:",
    icon="⭐",
)
st.sidebar.page_link("home.py", label="Back to main page 🏠")
make_sidebar(VERSION)
