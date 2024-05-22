import os
import signal
import smtplib
import threading
import time
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime
from email.mime.text import MIMEText
from pathlib import Path
from threading import Timer

import boto3
import pandas as pd
import requests
import sqlalchemy
import streamlit as st
import streamlit_authenticator as stauth
import utm
import yaml
from dotenv import load_dotenv
from requests.exceptions import HTTPError
from tqdm import tqdm
from yaml.loader import SafeLoader

from models import Price  # , ProcessingEvent
from models import GasType, Station, User
from session import db_session

#################
##AUTHENTICATOR##
#################


# load the configuration file from parent folder
current_path = os.path.dirname(__file__)
CONFIG_PATH = Path(current_path) / "config.yaml"

load_dotenv()

AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")
BUCKET_NAME_STORE = os.environ.get("BUCKET_NAME_STORE")


@st.cache_data
def load_users_to_db(config):
    # add each user to Database if not exists
    for username in config["credentials"]["usernames"]:
        # if user not exists
        gas_list = []
        for gas_type in db_session.query(GasType).all():
            gas_list.append(gas_type)
        if not db_session.query(User).filter(User.username == username).first():
            # add all gas types to the user

            user = User(
                username=username,
                email=config["credentials"]["usernames"][username]["email"],
                name=config["credentials"]["usernames"][username]["name"],
                gastypes=[gas for gas in gas_list],
            )
            db_session.add(user)
        # if user exists, update the email and name
        else:
            user = db_session.query(User).filter(User.username == username).first()
            # if email or name has changed
            email_changed = (
                user.email == config["credentials"]["usernames"][username]["email"]
            )
            if email_changed:
                user.email = config["credentials"]["usernames"][username]["email"]
            name_changed = user.name = config["credentials"]["usernames"][username][
                "name"
            ]
            if name_changed:
                user.name = config["credentials"]["usernames"][username]["name"]
            if email_changed or name_changed:
                db_session.add(user)
    # delete users that are not in the config file
    for user in db_session.query(User):
        if user.username not in config["credentials"]["usernames"]:
            db_session.delete(user)
    try:
        db_session.commit()
    except sqlalchemy.exc.IntegrityError as e:
        print(e)
        db_session.rollback()
        st.error("Username or email already exists")


def init_authenticator():
    """
    This function initializes the authenticator and loads the configuration file.

    Returns:
        authenticator: streamlit_authenticator.Authenticate
        config: dict
    """
    if os.environ.get("LOAD_MODE") == "local":
        with open(CONFIG_PATH) as file:
            config = yaml.load(file, Loader=SafeLoader)
    elif os.environ.get("LOAD_MODE") == "remote":
        s3 = boto3.client(
            "s3",
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        )
        # retrieve the config file from the bucket
        response = s3.get_object(
            Bucket=BUCKET_NAME_STORE,
            Key="config.yaml",
        )
        config = yaml.load(response["Body"].read(), Loader=SafeLoader)
    else:
        raise NotImplementedError(f"{os.environ.get('LOAD_MODE')} mode is supported")

    load_users_to_db(config)

    authenticator = stauth.Authenticate(
        config["credentials"],
        config["cookie"]["name"],
        config["cookie"]["key"],
        config["cookie"]["expiry_days"],
        config["preauthorized"],
    )
    return authenticator, config


def dump_config(config):
    """
    This function writes the configuration file.

    Args:
        config: dict

    Returns:
        None
    """
    if os.environ.get("LOAD_MODE") == "local":
        with open(CONFIG_PATH, "w") as file:
            yaml.dump(config, file, default_flow_style=False)
    elif os.environ.get("LOAD_MODE") == "remote":
        s3 = boto3.client(
            "s3",
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        )
        # put the config file in the bucket
        yaml_data = yaml.dump(config, default_flow_style=False)
        s3.put_object(
            Bucket=BUCKET_NAME_STORE,
            Key="config.yaml",
            Body=yaml_data,
        )
    else:
        raise NotImplementedError(f"{os.environ.get('LOAD_MODE')} mode is supported")


###################
## DATASET LOADER##
###################


def loadXML():
    """
    This function downloads the XML file from the url and extracts it.

    Args:
        None
    """
    urls = ["https://donnees.roulez-eco.fr/opendata/instantane_ruptures"]
    for url in urls:
        try:
            response = requests.get(url, verify=False)
            # If the response was successful, no Exception will be raised
            response.raise_for_status()
            ziped = open("ZIP.zip", "wb")
            ziped.write(response.content)
            ziped.close()
            with zipfile.ZipFile("ZIP.zip", "r") as zip_ref:
                zip_ref.extractall("./")
                zip_ref.close()
            os.remove("ZIP.zip")
        except HTTPError as http_err:
            print(f"HTTP error occurred: {http_err}")
        else:
            print("Success!")


def create_gastypes():
    gas_dict = {"Gazole": 1, "SP95": 2, "SP98": 6, "E85": 3, "GPLc": 4, "E10": 5}

    for name, xml_id in gas_dict.items():
        if not db_session.query(GasType).filter(GasType.name == name).first():
            gas_type = GasType(name=name, xml_id=xml_id)
            db_session.add(gas_type)
    try:
        db_session.commit()
    except sqlalchemy.exc.IntegrityError:
        db_session.rollback()
        st.error("Gas type already exists")


def dump_stations():
    xmlfile = "PrixCarburants_instantane_ruptures.xml"
    # create element tree object
    tree = ET.parse(xmlfile)
    # get root element
    root = tree.getroot()
    for pdv in tqdm(root.iter("pdv"), total=10006):
        id_station = pdv.get("id")
        latitude = pdv.get("latitude")
        longitude = pdv.get("longitude")
        address = pdv.find("adresse").text
        town = pdv.find("ville").text
        zip_code = pdv.get("cp")
        if not db_session.query(Station).filter(Station.id == id_station).first():
            station = Station(
                id=id_station,
                latitude=latitude,
                longitude=longitude,
                address=address,
                town=town,
                zip_code=zip_code,
            )
            db_session.add(station)
        # fetch all the prices
        for prix in pdv.findall("prix"):
            id_price = prix.get("id")
            valeur = prix.get("valeur")
            maj_str = prix.get("maj")
            maj = datetime.strptime(maj_str, "%Y-%m-%d %H:%M:%S")
            price_from_db = (
                db_session.query(Price)
                .filter(Price.gastype_id == id_price, Price.station_id == id_station)
                .first()
            )
            if price_from_db is None:
                price = Price(
                    gastype_id=id_price,
                    station_id=id_station,
                    updated_at=maj,
                    price=valeur,
                )
                db_session.add(price)
            else:
                # update the price
                price_from_db.price = valeur
                price_from_db.updated_at = maj
                db_session.add(price_from_db)
        try:
            db_session.commit()
        except sqlalchemy.exc.IntegrityError:
            db_session.rollback()
            st.error("Station already exists")
    # remove xml file
    Path("PrixCarburants_instantane_ruptures.xml").unlink()


def bounding_stations(bounds):
    # bounds_example = {
    #   "_southWest": {
    #     "lat": 47.98739410650529,
    #     "lng": -0.8809661865234376
    #   },
    #   "_northEast": {
    #     "lat": 48.147992238446264,
    #     "lng": -0.6320571899414062
    #   }
    # }
    lat_min = bounds["_southWest"]["lat"] * 100000
    lat_max = bounds["_northEast"]["lat"] * 100000
    lon_min = bounds["_southWest"]["lng"] * 100000
    lon_max = bounds["_northEast"]["lng"] * 100000
    nearby_states = (
        db_session.query(Station)
        .filter(
            Station.latitude > lat_min,
            Station.latitude < lat_max,
            Station.longitude > lon_min,
            Station.longitude < lon_max,
        )
        .all()
    )
    return nearby_states


def k_stations(geoloc, k):
    """
    This function returns the k nearest stations to a given geolocation.

    Args:
        geoloc: tuple (float:lon, float:lat)
        k: int
    """
    stations_candidates = []
    search_dist, increment = (3000, 1000)
    while len(stations_candidates) < k:
        stations_candidates = candidate_stations(geoloc=geoloc, max_dist=search_dist)
        search_dist += increment
    return stations_candidates


def candidate_stations(geoloc, max_dist):
    """
    This function returns the stations within a given distance from a geolocation.

    Args:
        geoloc: tuple (float:lon, float:lat)
        max_dist: int
    """
    (lon, lat) = geoloc

    easting_utm, northing_utm, zone_number, zone_letter = utm.from_latlon(lat, lon)
    lat_max, lon_max = utm.to_latlon(
        easting=easting_utm + max_dist,
        northing=northing_utm + max_dist,
        zone_number=zone_number,
        zone_letter=zone_letter,
    )

    lat_min, lon_min = utm.to_latlon(
        easting=easting_utm - max_dist,
        northing=northing_utm - max_dist,
        zone_number=zone_number,
        zone_letter=zone_letter,
    )
    # convert to WSG84
    lat_min = lat_min * 100000
    lon_min = lon_min * 100000
    lat_max = lat_max * 100000
    lon_max = lon_max * 100000

    nearby_states = (
        db_session.query(Station)
        .filter(
            Station.latitude > lat_min,
            Station.latitude < lat_max,
            Station.longitude > lon_min,
            Station.longitude < lon_max,
        )
        .all()
    )

    return nearby_states


def get_prices_user(user_name):
    user = db_session.query(User).filter_by(username=user_name).first()
    # get custom stations
    data = {"Name": [], "Type": [], "Price": [], "Updated_at": []}
    gastypes_followed_id = [gastype.xml_id for gastype in user.gastypes]
    for custom_station in user.stations:
        # get prices for each custom station
        prices = db_session.query(Price).filter_by(station_id=custom_station.id).all()
        for price in prices:
            if str(price.gastype_id) in gastypes_followed_id:
                gas_type = (
                    db_session.query(GasType).filter_by(xml_id=price.gastype_id).first()
                )
                data["Name"].append(custom_station.custom_name)
                data["Type"].append(gas_type.name)
                # round the price at 2 decimals
                data["Price"].append(price.price)
                data["Updated_at"].append(price.updated_at)
    columns = ["Name", "Type", "Price", "Updated_at"]
    df = pd.DataFrame(data, columns=columns)
    column_config = {
        col: st.column_config.Column(disabled=True) for col in ["Name", "Type"]
    }
    column_config["Price"] = st.column_config.NumberColumn(
        disabled=True, format="%.3f €"
    )
    column_config["Updated_at"] = st.column_config.DateColumn(
        disabled=True,
        format="DD-MM-YYYY",
    )
    # apply a style to highlight the min price
    # data=df.style.highlight_min(subset=["Price"], color="red"),
    # order the df by the lowest price
    df = df.sort_values(by=["Price"], ascending=True)
    st.dataframe(
        data=df,
        hide_index=True,
        use_container_width=True,
        column_config=column_config,
        column_order=["Name", "Type", "Price", "Updated_at"],
    )
    # create a metric showing gain
    if df.shape[0] >= 2:
        st.metric(
            "Annual Savings 💰",
            f"{round((df['Price'].max() - df['Price'].min()) * 650, 2)} €",
        )


def get_prices_demo(followed_stations_list, followed_gastypes_list):
    # get custom stations
    data = {"Name": [], "Type": [], "Price": [], "Updated_at": []}
    for custom_station in followed_stations_list:
        # get prices for each custom station
        custom_station_id = int(custom_station["id"])
        prices = db_session.query(Price).filter_by(station_id=custom_station_id).all()
        followed_gastypes_id_list = []
        for gas_name in followed_gastypes_list:
            gas_type = db_session.query(GasType).filter_by(name=gas_name).first()
            if gas_type:
                followed_gastypes_id_list.append(int(gas_type.xml_id))
        for price in prices:
            if price.gastype_id in followed_gastypes_id_list:
                gas_type = (
                    db_session.query(GasType).filter_by(xml_id=price.gastype_id).first()
                )
                data["Name"].append(custom_station.get("custom_name"))
                data["Type"].append(gas_type.name)
                # round the price at 2 decimals
                data["Price"].append(price.price)
                data["Updated_at"].append(price.updated_at)
    columns = ["Name", "Type", "Price", "Updated_at"]
    df = pd.DataFrame(data, columns=columns)
    column_config = {
        col: st.column_config.Column(disabled=True) for col in ["Name", "Type"]
    }
    column_config["Price"] = st.column_config.NumberColumn(
        disabled=True, format="%.3f €"
    )
    column_config["Updated_at"] = st.column_config.DateColumn(
        disabled=True,
        format="DD-MM-YYYY",
    )
    # apply a style to highlight the min price
    # data=df.style.highlight_min(subset=["Price"], color="red"),
    # order the df by the lowest price
    df = df.sort_values(by=["Price"], ascending=True)
    st.dataframe(
        data=df,
        hide_index=True,
        use_container_width=True,
        column_config=column_config,
        column_order=["Name", "Type", "Price", "Updated_at"],
    )
    # create a metric showing gain
    if df.shape[0] >= 2:
        st.metric(
            "Annual Savings 💰",
            f"{round((df['Price'].max() - df['Price'].min()) * 650, 2)} €",
        )


#############
#### UI #####
#############


# create a function that increase wait time
# for login page if user failed to login,
# by power of 2 of the number of failed attempts
def wait_time(try_number):
    if try_number > 3:
        with st.spinner("Please wait..."):
            time.sleep(2 ** (try_number - 3))


def send_email(subject, body, recipients):
    password = GMAIL_APP_PASSWORD
    sender = "emilienstreamlit@gmail.com"
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp_server:
        smtp_server.login(sender, password)
        smtp_server.sendmail(sender, recipients, msg.as_string())


##################
###SIMPLE ETL#####
##################

WAIT_TIME_SECONDS = 60 * 60 * 6  # each 6 hours


class ProgramKilled(Exception):
    pass


def signal_handler(signum, ffoorame):
    raise ProgramKilled


class Job(threading.Thread):
    def __init__(self, interval, execute, *args, **kwargs):
        threading.Thread.__init__(self)
        self.daemon = False
        self.stopped = threading.Event()
        self.interval = interval
        self.execute = execute
        self.args = args
        self.kwargs = kwargs

    def stop(self):
        self.stopped.set()
        self.join()

    def run(self):
        while not self.stopped.wait(self.interval.total_seconds()):
            self.execute(*self.args, **self.kwargs)


def main_etl():
    print("Running ETL job at ", datetime.now())
    # print the process pid
    print("Process ID: ", os.getpid())
    with open("lastjob.txt", "w") as file:
        file.write(str(datetime.now()))
    loadXML()
    dump_stations()


def etl_job():
    # check if status file exists
    if not os.path.exists("pid.txt"):
        with open("pid.txt", "w") as file:
            file.write(str(os.getpid()))
        # start etl at beginning of the thread
        main_etl()
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        job = Timer(WAIT_TIME_SECONDS, main_etl)
        job.start()

        while True:
            try:
                time.sleep(1)
            except ProgramKilled:
                print("Program killed: running cleanup code")
                # remove the pid file
                if os.path.exists("pid.txt"):
                    os.remove("pid.txt")
                job.cancel()
                break
    else:
        print("PID file already found, job as already started. Exiting...")
        exit(1)


if __name__ == "__main__":
    # loadXML()
    # create_gastypes()
    # dump_stations()
    # geoloc = (-0.6789, 47.9217)
    # geoloc = (48.70671, 2.07337)
    # geoloc = (-0.6789, 47.9217)
    # list_stations = k_stations(geoloc=geoloc,k=5)
    #
    # for station in list_stations:
    #     print(station.to_dict())
    etl_job()
