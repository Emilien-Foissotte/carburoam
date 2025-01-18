import argparse
import hashlib
import os
import signal
import smtplib
import threading
import time
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime
from email.mime.text import MIMEText
from io import BytesIO
from pathlib import Path
from threading import Timer

import boto3
import pandas as pd
import pytz
import requests
import sqlalchemy
import streamlit as st
import streamlit_authenticator as stauth
import yaml
from dotenv import load_dotenv
from requests.exceptions import HTTPError
from tqdm import tqdm
from yaml.loader import SafeLoader

from models import CustomStation, GasType, Price, Station, Transfer, User
from session import db_session

VERSION = "0.3.0"

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
            Path("ZIP.zip").unlink(missing_ok=True)
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
    # compute the total amount of stations for tqdm progress bar
    total_stations = len(root.findall("pdv"))
    for pdv in tqdm(root.iter("pdv"), total=total_stations):
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
    Path("PrixCarburants_instantane_ruptures.xml").unlink(missing_ok=True)


def get_hash_of_file(file_path):
    """
    Get the hash of a file.

    Args:
        file_path (str): The path to the file to hash.
        verbose (int): The level of verbosity to use.
    Returns:
        str: The hash of the file.
    """
    hash_md5 = hashlib.md5()
    try:
        with open(file_path, "rb") as file:
            for chunk in iter(lambda: file.read(4096), b""):
                hash_md5.update(chunk)
    except Exception as e:
        # Handle file open exception
        print(f"Error reading file {file_path}: {e}")
    return hash_md5.hexdigest()


def save_database():
    """
    Save the database to a file and export to S3 bucket.

    Returns:
        None
    """
    # no need to save stations, save only custom stations and gas types followed by users
    # create directory save
    Path("save").mkdir(parents=True, exist_ok=True)
    # save the gas types followed to a csv file
    # loop over users
    df_gastypes = pd.DataFrame(columns=["username", "gastype"], data=[])
    for user in db_session.query(User).all():
        for gas in user.gastypes:
            new_record = pd.DataFrame(
                [{"username": user.username, "gastype": gas.name}]
            )
            # add the line to dataframe
            df_gastypes = pd.concat([df_gastypes, new_record], ignore_index=True)

    # add the datetime of the save in the filename
    now = datetime.now()
    # convert to utc to avoid timezone issues
    now = now.astimezone(pytz.utc)

    # save the dataframe to a csv file
    filename_gastype_followed = Path("save") / Path(f"gastype_followed_{now}.csv")
    nb_gastypes = df_gastypes.shape[0]
    df_gastypes.to_csv(filename_gastype_followed, index=False)
    hash_gastype = get_hash_of_file(filename_gastype_followed)

    # loop over users and custom stations
    df_custom_stations = pd.DataFrame(
        columns=["username", "custom_name", "id"], data=[]
    )
    for user in db_session.query(User).all():
        for station in user.stations:
            new_record = pd.DataFrame(
                [
                    {
                        "username": user.username,
                        "custom_name": station.custom_name,
                        "id": station.id,
                    }
                ]
            )
            # add the line to dataframe
            df_custom_stations = pd.concat(
                [df_custom_stations, new_record], ignore_index=True
            )
    filename_custom_stations = Path("save") / Path(f"custom_stations_{now}.csv")
    # get the lenght of df_custom_stations
    nb_custom_stations = df_custom_stations.shape[0]
    df_custom_stations.to_csv(filename_custom_stations, index=False)
    hash_custom_stations = get_hash_of_file(filename_custom_stations)

    if os.environ.get("LOAD_MODE") == "local":
        print(f"File saved locally at {now}")
    elif os.environ.get("LOAD_MODE") == "remote":
        s3 = boto3.client(
            "s3",
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        )
        # put the two files in the bucket
        with open(filename_gastype_followed, "rb") as file:
            body = file.read()
            s3.put_object(
                Bucket=BUCKET_NAME_STORE,
                Key=f"gastype_followed_{now}.csv",
                Body=body,
            )
        with open(filename_custom_stations, "rb") as file:
            body = file.read()
            s3.put_object(
                Bucket=BUCKET_NAME_STORE,
                Key=f"custom_stations_{now}.csv",
                Body=body,
            )

    # create a new transfer object into DB

    transfer = Transfer(
        date=now,
        export=True,
        gas_types_followed_inserted=nb_gastypes,
        hash_gas_types_followed=hash_gastype,
        custom_stations_inserted=nb_custom_stations,
        hash_custom_stations=hash_custom_stations,
        local=True if os.environ.get("LOAD_MODE") == "local" else False,
    )
    try:
        db_session.add(transfer)
        db_session.commit()
        print(f"Export done at {now}")
    except sqlalchemy.exc.IntegrityError:
        db_session.rollback()
        print("Transfer already exists")

    # cleanup old files (save up to 3 saves) on disk or on S3 if remote.
    # remove the oldest one first
    if os.environ.get("LOAD_MODE") == "local":
        # sort the files by creation date and by name, followed gastypes* and custom stations*
        files_gastype = []
        files_customstations = []
        for file in Path("save").iterdir():
            if "gastype_followed" in file.name:
                files_gastype.append(file)
            elif "custom_stations" in file.name:
                files_customstations.append(file)
        # sort the files by creation date
        files_gastype = sorted(files_gastype, key=os.path.getctime)
        files_customstations = sorted(files_customstations, key=os.path.getctime)
        all_files = files_gastype[:-3] + files_customstations[:-3]
        for file in all_files:
            file.unlink()
        print("Old files locally removed")
    elif os.environ.get("LOAD_MODE") == "remote":
        s3 = boto3.client(
            "s3",
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        )
        # list object by file name, gas type and custom stations
        response_gastypes = s3.list_objects_v2(
            Bucket=BUCKET_NAME_STORE, Prefix="gastype_followed"
        )
        files_gastype = response_gastypes["Contents"]
        files_gastype = sorted(files_gastype, key=lambda x: x["LastModified"])
        response_customstations = s3.list_objects_v2(
            Bucket=BUCKET_NAME_STORE, Prefix="custom_stations"
        )
        files_customstations = response_customstations["Contents"]
        files_customstations = sorted(
            files_customstations, key=lambda x: x["LastModified"]
        )
        all_files = files_gastype[:-3] + files_customstations[:-3]
        for file in all_files:
            s3.delete_object(Bucket=BUCKET_NAME_STORE, Key=file["Key"])
        print("Old files on S3 removed")


def restore_database():
    """
    Restore elements dumped.
    """
    df_gastypes = None
    df_customstations = None
    if os.environ.get("LOAD_MODE") == "local":
        print("Restore locally")
        # read the last transfer
        transfer = db_session.query(Transfer).order_by(Transfer.date.desc()).first()
        # get the most recent file for each object, custom stations and gas types followed
        files_gastype = []
        files_customstations = []
        for file in Path("save").iterdir():
            if "gastype_followed" in file.name:
                files_gastype.append(file)
            elif "custom_stations" in file.name:
                files_customstations.append(file)
        # sort the files by creation date
        files_gastype = sorted(files_gastype, key=os.path.getctime)
        files_customstations = sorted(files_customstations, key=os.path.getctime)
        # get the most recent file
        file_gastype = files_gastype[-1]
        file_customstations = files_customstations[-1]
        if files_gastype is not None:
            # check the date of the file and ensure it is more recent than the last transfer
            # check the date using file name
            filename_gastype = file_gastype.name
            # remove the leading part
            filename_gastype = filename_gastype.replace("gastype_followed_", "")
            # remove the extension
            filename_gastype = filename_gastype.replace(".csv", "")
            # read the date from the filename
            date_gastype = datetime.strptime(filename_gastype, "%Y-%m-%d %H:%M:%S.%f%z")
            if transfer is None or date_gastype.timestamp() > transfer.date.timestamp():
                # read the file
                df_gastypes = pd.read_csv(file_gastype)
        if files_customstations is not None:
            # check the date of the file and ensure it is more recent than the last transfer
            # check the date using file name
            filename_customstations = file_customstations.name
            # remove the leading part
            filename_customstations = filename_customstations.replace(
                "custom_stations_", ""
            )
            # remove the extension
            filename_customstations = filename_customstations.replace(".csv", "")
            # read the date from the filename
            date_customstations = datetime.strptime(
                filename_customstations, "%Y-%m-%d %H:%M:%S.%f%z"
            )
            if (
                transfer is None
                or date_customstations.timestamp() > transfer.date.timestamp()
            ):
                # read the file
                df_customstations = pd.read_csv(file_customstations)
    elif os.environ.get("LOAD_MODE") == "remote":
        print("Restore remotely")
        s3 = boto3.client(
            "s3",
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        )
        # list object by file name, gas type and custom stations
        response_gastypes = s3.list_objects_v2(
            Bucket=BUCKET_NAME_STORE, Prefix="gastype_followed"
        )
        files_gastype = response_gastypes["Contents"]
        files_gastype = sorted(files_gastype, key=lambda x: x["LastModified"])
        response_customstations = s3.list_objects_v2(
            Bucket=BUCKET_NAME_STORE, Prefix="custom_stations"
        )
        files_customstations = response_customstations["Contents"]
        files_customstations = sorted(
            files_customstations, key=lambda x: x["LastModified"]
        )
        # get the most recent file
        file_gastype = files_gastype[-1]
        file_customstations = files_customstations[-1]
        if files_gastype is not None:
            # check the date of the file and ensure it is more recent than the last transfer
            # check the date using file name
            filename_gastype = file_gastype["Key"]
            # remove the leading part
            filename_gastype = filename_gastype.replace("gastype_followed_", "")
            # remove the extension
            filename_gastype = filename_gastype.replace(".csv", "")
            # read the date from the filename
            date_gastype = datetime.strptime(filename_gastype, "%Y-%m-%d %H:%M:%S.%f%z")
            transfer = db_session.query(Transfer).order_by(Transfer.date.desc()).first()
            if transfer is None or date_gastype.timestamp() > transfer.date.timestamp():
                # read the file
                response = s3.get_object(
                    Bucket=BUCKET_NAME_STORE, Key=file_gastype["Key"]
                )
                body = response["Body"].read()
                # read the file from bytes with pandas
                df_gastypes = pd.read_csv(BytesIO(body))
            # do the same for custom stations
            if files_customstations is not None:
                # check the date of the file and ensure it is more recent than the last transfer
                # check the date using file name
                filename_customstations = file_customstations["Key"]
                # remove the leading part
                filename_customstations = filename_customstations.replace(
                    "custom_stations_", ""
                )
                # remove the extension
                filename_customstations = filename_customstations.replace(".csv", "")
                # read the date from the filename
                date_customstations = datetime.strptime(
                    filename_customstations, "%Y-%m-%d %H:%M:%S.%f%z"
                )
                if (
                    transfer is None
                    or date_customstations.timestamp() > transfer.date.timestamp()
                ):
                    # read the file
                    response = s3.get_object(
                        Bucket=BUCKET_NAME_STORE, Key=file_customstations["Key"]
                    )
                    body = response["Body"].read()
                    df_customstations = pd.read_csv(BytesIO(body))
    if df_customstations is not None:
        # loop over the dataframe and add the custom stations to the users
        # iterate over unique users
        users = df_customstations["username"].unique()
        # filter out users that are not in the database
        users = [
            user
            for user in users
            if db_session.query(User).filter(User.username == user).first() is not None
        ]
        for user in users:
            db_user = db_session.query(User).filter(User.username == user).first()
            df_user_customstations = df_customstations.loc[
                df_customstations["username"] == user
            ]
            # we won't remove custom station as there is no auto creation mechanism
            for index, row in df_user_customstations.iterrows():
                station = (
                    db_session.query(Station).filter(Station.id == row["id"]).first()
                )
                if station is not None and station.id not in [
                    stat.id for stat in db_user.stations
                ]:
                    custom_station = CustomStation(
                        custom_name=row["custom_name"], id=row["id"]
                    )
                    db_user.stations.append(custom_station)
                    db_session.add(db_user)
        try:
            db_session.commit()
        except sqlalchemy.exc.IntegrityError:
            db_session.rollback()
            print("Custom station already exists")
        else:
            print(f"Custom stations restored {os.environ.get('LOAD_MODE')}")
    # do the same for gastypes
    if df_gastypes is not None:
        # loop over the dataframe and add the gas types to the users
        # iterate over unique users
        users = df_gastypes["username"].unique()
        # filter out users that are not in the database
        users = [
            user
            for user in users
            if db_session.query(User).filter(User.username == user).first() is not None
        ]
        for user in users:
            db_user = db_session.query(User).filter(User.username == user).first()
            df_user_gastypes = df_gastypes.loc[df_gastypes["username"] == user]
            # first remove gas types in user that are not in the file
            for gas in (
                db_session.query(User).filter(User.username == user).first().gastypes
            ):
                if gas.name not in df_user_gastypes["gastype"].values:
                    db_user.gastypes.remove(gas)
                    db_session.add(db_user)
            for index, row in df_user_gastypes.iterrows():
                gas_type = (
                    db_session.query(GasType)
                    .filter(GasType.name == row["gastype"])
                    .first()
                )
                if gas_type is not None and gas_type not in db_user.gastypes:
                    db_user.gastypes.append(gas_type)
                    db_session.add(db_user)
        try:
            db_session.commit()
        except sqlalchemy.exc.IntegrityError:
            db_session.rollback()
            print("Gas type already exists")
        else:
            print(f"Gas types restored {os.environ.get('LOAD_MODE')}")


def bounding_stations(bounds):
    """
    Filter the stations based on the bounds.

    Args:
        bounds: dict

    Returns:
        nearby_states: list of Station
    """
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
WAIT_TIME_SECONDS_SAVE = 60 * 60 * 24  # each 24 hours


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
        # check if the test user has custom stations, if not restore the database
        user = db_session.query(User).filter_by(username="test").first()
        if len(user.stations) == 0:
            print("No custom stations for test user, restoring database")
            restore_database()
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        job = Timer(WAIT_TIME_SECONDS, main_etl)
        job_save = Timer(WAIT_TIME_SECONDS_SAVE, save_database)
        job_save.start()
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
                job_save.cancel()
                break
    else:
        print("PID file already found, job as already started. Exiting...")
        exit(1)


if __name__ == "__main__":
    # parse kwargs from script
    parser = argparse.ArgumentParser()
    parser.add_argument("--action")
    args = parser.parse_args()
    if args.action == "etl":
        etl_job()
    elif args.action == "save":
        save_database()
    elif args.action == "restore":
        restore_database()
    else:
        print(f"Error : Bad action specified, {args.action} unknown. Exiting...")
        exit(1)
