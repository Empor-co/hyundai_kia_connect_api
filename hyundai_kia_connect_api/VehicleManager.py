import asyncio
import datetime as dt
import logging
from dataclasses import dataclass

import pytz

from .ApiImpl import ApiImpl, ClimateRequestOptions
from .const import (
    BRAND_HYUNDAI,
    BRAND_KIA,
    BRANDS,
    DOMAIN,
    REGION_CANADA,
    REGION_EUROPE,
    REGION_USA,
    REGIONS,
)
from .HyundaiBlueLinkAPIUSA import HyundaiBlueLinkAPIUSA
from .KiaUvoApiCA import KiaUvoApiCA
from .KiaUvoApiEU import KiaUvoApiEU
from .KiaUvoAPIUSA import KiaUvoAPIUSA
from .Vehicle import Vehicle

_LOGGER = logging.getLogger(__name__)


class VehicleManager:
    def __init__(self, region: int, brand: int, username: str, password: str, pin: str):
        self.region: int = region
        self.brand: int = brand
        self.username: str = username
        self.password: str = password
        self.pin: str = pin

        self.api: ApiImpl = self.get_implementation_by_region_brand(
            self.region, self.brand
        )

        self.token: token = None
        self.vehicles: dict = {}

    def initialize(self) -> None:
        self.token: Token = self.api.login(self.username, self.password)
        self.token.pin = self.pin
        vehicles = self.api.get_vehicles(self.token)
        for vehicle in vehicles:
            self.vehicles[vehicle.id] = vehicle
        self.update_all_vehicles_with_cached_state()
        
    def get_vehicle(self, vehicle_id) -> Vehicle:
        return self.vehicles[vehicle_id]

    def update_all_vehicles_with_cached_state(self) -> None:
        for vehicle_id in self.vehicles.keys():
            self.update_vehicle_with_cached_state(self.get_vehicle(vehicle_id))

    def update_vehicle_with_cached_state(self, vehicle: Vehicle) -> None:
        self.api.update_vehicle_with_cached_state(self.token, vehicle)

    def check_and_force_update_vehicles(self, force_refresh_interval: int) -> None:
        started_at_utc: datetime = dt.datetime.now(pytz.utc)
        for vehicle_id in self.vehicles.keys():
            vehicle: Vehicle = self.get_vehicle(vehicle_id)
            _LOGGER.debug(
                f"time diff - {(started_at_utc - vehicle.last_updated_at).total_seconds()}"
            )
            if (
                started_at_utc - vehicle.last_updated_at
            ).total_seconds() > force_refresh_interval:
                self.force_refresh_vehicle_state(vehicle)
                self.update_vehicle_with_cached_state(vehicle)

    def force_refresh_all_vehicles_states(self) -> None:
        for vehicle_id in self.vehicles.keys():
            self.force_refresh_vehicle_state(self.get_vehicle(vehicle_id))
        self.update_all_vehicles_with_cached_state()

    def force_refresh_vehicle_state(self, vehicle: Vehicle) -> None:
        self.api.force_refresh_vehicle_state(self.token, vehicle)

    def check_and_refresh_token(self) -> bool:
        if self.token is None:
            self.initialize()
        if self.token.valid_until <= dt.datetime.now(pytz.utc):
            _LOGGER.debug(f"{DOMAIN} - Refresh token expired")
            self.token = self.api.login(self.username, self.password)
            return True
        return False

    def remote_start(self, vehicleID: str, options: ClimateRequestOptions) -> None:
        self.api.start_climate(self.token, self.vehicles[vehicleID], options)
            
    def cancel_remote_start(self, vehicleID: str) -> None:
        self.api.stop_climate(self.token, self.vehicles[vehicleID])

    def lock(self, vehicleID: str) -> None:
        self.api.lock_action(self.token, self.vehicles[vehicleID], "close")
    
    def unlock(self, vehicleID: str) -> None:
        self.api.lock_action(self.token, self.vehicles[vehicleID], "open")

    def start_charge(self, vehicleID: str) -> None:
        self.api.start_charge(self.token, self.vehicles[vehicleID])

    def stop_charge(self, vehicleID: str) -> None:
        self.api.stop_charge(self.token, self.vehicles[vehicleID])

    def set_charge_limits(self, vehicleID: str, ac_limit: int, dc_limit: int) -> None:
        self.api.start_climate(self.token, self.vehicles[vehicleID], ac_limit, dc_limit)

    @staticmethod
    def get_implementation_by_region_brand(region: int, brand: int) -> ApiImpl:
        if REGIONS[region] == REGION_CANADA:
            return KiaUvoApiCA(region, brand)
        elif REGIONS[region] == REGION_EUROPE:
            return KiaUvoApiEU(region, brand)
        elif REGIONS[region] == REGION_USA and BRANDS[brand] == BRAND_HYUNDAI:
            return HyundaiBlueLinkAPIUSA(region, brand)
        elif REGIONS[region] == REGION_USA and BRANDS[brand] == BRAND_KIA:
            return KiaUvoAPIUSA(region, brand)
