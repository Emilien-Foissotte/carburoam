from typing import List, Optional

import sqlalchemy as sa
import utm
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


association_table = sa.Table(
    "association_table",
    Base.metadata,
    sa.Column("gastype_id", sa.ForeignKey("gas_types.id"), primary_key=True),
    sa.Column("user_id", sa.ForeignKey("users.id"), primary_key=True),
)


class GasType(Base):
    __tablename__ = "gas_types"
    # id = sa.Column(sa.Integer, primary_key=True)
    id: Mapped[int] = mapped_column(primary_key=True)
    xml_id = sa.Column(sa.String, nullable=False)
    name = sa.Column(sa.String, nullable=False)
    users: Mapped[List["User"]] = relationship(
        secondary=association_table, back_populates="gastypes"
    )

    def __repr__(self):
        return f"<GasType {self.name}>"


class User(Base):
    __tablename__ = "users"
    # id = sa.Column(sa.Integer, primary_key=True)
    id: Mapped[int] = mapped_column(primary_key=True)
    email = sa.Column(sa.String, unique=True, nullable=False)
    username = sa.Column(sa.String, unique=True, nullable=False)
    name = sa.Column(sa.String, nullable=False)
    # add a reference to the stations
    stations = relationship("CustomStation")
    # add a reference to the gas types followed
    gastypes: Mapped[List["GasType"]] = relationship(
        secondary=association_table, back_populates="users"
    )

    def __repr__(self):
        return f"<User {self.username}>"

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "username": self.username,
            "name": self.name,
        }

    def to_csv(self):
        return f"{self.id},{self.email},{self.username},{self.name}"


class VerificationCode(Base):
    __tablename__ = "verification_codes"
    id = sa.Column(sa.Integer, primary_key=True)
    user_id = sa.Column(sa.Integer, sa.ForeignKey("users.id"), nullable=False)
    code = sa.Column(sa.String, nullable=False)
    created_at = sa.Column(sa.DateTime, nullable=False)

    def __repr__(self):
        return f"<VerificationCode {self.id}>"


class Station(Base):
    __tablename__ = "stations"
    id = sa.Column(sa.Integer, primary_key=True)
    latitude = sa.Column(sa.Float, nullable=False)
    longitude = sa.Column(sa.Float, nullable=False)
    town = sa.Column(sa.String, nullable=False)
    address = sa.Column(sa.String, nullable=False)
    zip_code = sa.Column(sa.String, nullable=False)
    sa.Index("latitude_longitude_index", latitude, longitude, unique=True)

    def __repr__(self):
        return f"<Station {self.id}>"

    def to_dict(self):
        return {
            "id": self.id,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "town": self.town,
            "address": self.address,
            "zip_code": self.zip_code,
        }


class CustomStation(Base):
    __tablename__ = "custom_stations"
    id = sa.Column(sa.Integer, sa.ForeignKey("stations.id"), primary_key=True)
    user_id = sa.Column(sa.Integer, sa.ForeignKey("users.id"), nullable=False)
    custom_name = sa.Column(sa.String, nullable=False)

    def __repr__(self):
        return f"<CustomStation {self.id}-{self.user_id}>"

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "custom_name": self.custom_name,
        }


class Price(Base):
    __tablename__ = "prices"
    gastype_id = sa.Column(sa.Integer, sa.ForeignKey("gas_types.id"), primary_key=True)
    station_id = sa.Column(sa.Integer, sa.ForeignKey("stations.id"), primary_key=True)
    updated_at = sa.Column(sa.DateTime, nullable=False)
    price = sa.Column(sa.Float, nullable=False)
