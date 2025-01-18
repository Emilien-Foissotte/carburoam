# borrowed from https://github.com/SiddhantSadangi/pdf-workdesk
import streamlit as st
from st_social_media_links import SocialMediaIcons


def make_sidebar(version: str):
    with st.sidebar:
        st.page_link("pages/about.py", label=f"About Carburoam v{version}", icon="ℹ️")

        with open("sidebar.html", "r", encoding="UTF-8") as sidebar_file:
            sidebar_html = sidebar_file.read().replace("{VERSION}", version)

        st.components.v1.html(sidebar_html, height=247)

        st.html(
            """
            <div style="text-align:center; font-size:14px; color:lightgrey">
                <hr style="margin-bottom: 6%; margin-top: 0%;">
                Share the ❤️ on social media
            </div>"""
        )

        social_media_links = [
            "https://www.facebook.com/sharer/sharer.php?kid_directed_site=0&sdk=joey&u=https%3A%2F%2Fcarburoam.streamlit.app%2F&display=popup&ref=plugin&src=share_button",
            "https://www.linkedin.com/sharing/share-offsite/?url=https%3A%2F%2Fcarburoam.streamlit.app%2F",
            "https://x.com/intent/tweet?original_referer=https%3A%2F%2Fcarburoam.streamlit.app%2F&ref_src=twsrc%5Etfw%7Ctwcamp%5Ebuttonembed%7Ctwterm%5Eshare%7Ctwgr%5E&text=Check%20out%20this%20open-source%20Gas%20Stations-tracking%20Streamlit%20app%21&url=https%3A%2F%2Fcarburoam.streamlit.app%2F",
        ]

        social_media_icons = SocialMediaIcons(
            social_media_links, colors=["lightgray"] * len(social_media_links)
        )

        social_media_icons.render(sidebar=True)

        st.html(
            """
                <div style="text-align:center; font-size:12px; color:lightgrey">
                    <hr style="margin-bottom: 6%; margin-top: 6%;">
                    <a rel="license" href="https://creativecommons.org/licenses/by-nc-sa/4.0/">
                        <img alt="Creative Commons License" style="border-width:0"
                            src="https://i.creativecommons.org/l/by-nc-sa/4.0/88x31.png" />
                    </a><br><br>
                    This work is licensed under a <b>Creative Commons
                        Attribution-NonCommercial-ShareAlike 4.0 International License</b>.<br>
                    You can modify and build upon this work non-commercially. All derivatives should be
                    credited to Émilien Foissotte and
                    be licenced under the same terms.
                </div>
            """
        )
