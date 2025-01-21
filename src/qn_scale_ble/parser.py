from __future__ import annotations

import asyncio
import dataclasses
import logging
import struct
from collections.abc import Callable
from enum import IntEnum
import time

from bleak import BleakClient
from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from bleak_retry_connector import establish_connection

from .bluetooth import create_adv_receiver, sum_checksum
from .const import (
#    ALIRO_CHARACTERISTIC_UUID,
    BATTERY_LEVEL_CHARACTERISTIC_UUID,
    DISPLAY_UNIT_KEY,
#    HW_REVISION_STRING_CHARACTERISTIC_UUID,
    IMPEDANCE_KEY,
    MANUFACTURER_STRING_CHARACTERISTIC_UUID,
    SW_REVISION_STRING_CHARACTERISTIC_UUID,
#    UNIT_UPDATE_COMMAND,
#    WEIGHT_CHARACTERISTIC_UUID_NOTIFY,
    WEIGHT_KEY,
)

_LOGGER = logging.getLogger(__name__)


# UUIDs (based on OpenScale impl)
#NEW_WEIGHT_MEASUREMENT_SERVICE = "0000ffe0-0000-1000-8000-00805f9b34fb"
# NEW_WEIGHT_MEASUREMENT_SERVICE = "0000fff0-0000-1000-8000-00805f9b34fb"
# NEW_CUSTOM1_MEASUREMENT_CHARACTERISTIC = "0000ffe1-0000-1000-8000-00805f9b34fb"
# NEW_CUSTOM2_MEASUREMENT_CHARACTERISTIC = "0000ffe2-0000-1000-8000-00805f9b34fb"
# NEW_CUSTOM3_MEASUREMENT_CHARACTERISTIC = "0000ffe3-0000-1000-8000-00805f9b34fb"
# NEW_CUSTOM4_MEASUREMENT_CHARACTERISTIC = "0000ffe4-0000-1000-8000-00805f9b34fb"
# NEW_CUSTOM5_MEASUREMENT_CHARACTERISTIC = "0000ffe5-0000-1000-8000-00805f9b34fb"

# 2nd Type Service and Characteristics (2nd Type doesn't need to indicate, and 4th characteristic is shared with 3rd.)
WEIGHT_MEASUREMENT_SERVICE_ALTERNATIVE = "0000fff0-0000-1000-8000-00805f9b34fb"
CUSTOM1_MEASUREMENT_CHARACTERISTIC_ALTERNATIVE = "0000fff1-0000-1000-8000-00805f9b34fb" # notify, read-only
CUSTOM3_MEASUREMENT_CHARACTERISTIC_ALTERNATIVE = "0000fff2-0000-1000-8000-00805f9b34fb" # write-only

# Scale time is in seconds since 2000-01-01 00:00:00 (utc).
SCALE_UNIX_TIMESTAMP_OFFSET = 946702800

class WeightUnit(IntEnum):
    """Weight units."""

    KG = 0  # Kilograms
    LB = 1  # Pounds
    ST = 2  # Stones


@dataclasses.dataclass
class ScaleData:
    """Response data with information about the scale."""

    name: str = ""
    address: str = ""
    hw_version: str = ""
    sw_version: str = ""
    display_unit: WeightUnit = WeightUnit.KG
    measurements: dict[str, str | float | None] = dataclasses.field(
        default_factory=dict
    )

def _decode_weight(byte1: int, byte2: int) -> float:
    # Decode weight from bytes
    # return ((float) (((a & 255) << 8) + (b & 255))) / this.weightScale;
    return (((byte1 & 255) << 8) + (byte2 & 255)) / 100.0

def _decode_impedance(byte1: int, byte2: int) -> int:
    # Decode impedance from bytes
    return (byte1 << 8) + byte2

def parse(payload: bytearray) -> dict[str, int | float | None]:
    _LOGGER.info("parse called")
    if (
        payload is not None
        and payload[0] == 16
        and payload[5] == 1
    ):
        _LOGGER.info("Payload starts with 16, trying to decode")
        # \x10\x0b\xff\x1f\x95\x01\x00\x00\x00\x00\xcf

        # Parse weight and impedance
        weight = _decode_weight(payload[3], payload[4])
        _LOGGER.info("Got weight: %f kg", weight)
        impedance = _decode_impedance(payload[6], payload[7])
        if (weight > 0):
            # TODO: Calculate impedance using resistances in bytes 6-9

            data = dict[str, int | float | None]()
            #weight = struct.unpack("<I", payload[10:13].ljust(4, b"\x00"))[0]
            #impedance = struct.unpack("<H", payload[13:15])[0]
            data[DISPLAY_UNIT_KEY] = WeightUnit.KG
            data[WEIGHT_KEY] = round(weight, 2)
#            if payload[20] == 1:
#                if impedance := struct.unpack("<H", payload[13:15])[0]:
#                    data[IMPEDANCE_KEY] = int(impedance)
            return data
        else:
            _LOGGER.info("Did not find a weight in this packet")
    elif (payload[0] == 35):
        # TODO
        pass
    return None

    if (
        payload is not None
        and len(payload) == 22
        and payload[19] == 1
        and payload[0:2] == b"\xa5\x02"
        and payload[3:5] == b"\x10\x00"
        and payload[6:10] == b"\x01\x61\xa1\x00"
    ):
        data = dict[str, int | float | None]()
        weight = struct.unpack("<I", payload[10:13].ljust(4, b"\x00"))[0]
        impedance = struct.unpack("<H", payload[13:15])[0]
        data[DISPLAY_UNIT_KEY] = int(payload[21])
        data[WEIGHT_KEY] = round(float(weight) / 1000, 2)
        if payload[20] == 1:
            if impedance := struct.unpack("<H", payload[13:15])[0]:
                data[IMPEDANCE_KEY] = int(impedance)
        return data
    return None


class QnScale:
    _client: BleakClient = None
    _hw_version: str = None
    _sw_version: str = None
    _mfr_name: str = None
    _display_unit: WeightUnit = None
    _unit_update_flag: bool = False

    def __init__(
        self,
        address: str,
        notification_callback: Callable[[ScaleData], None],
        display_unit: WeightUnit = None,
    ) -> None:
        self.address = address
        self._notification_callback = notification_callback
        self._scanner = create_adv_receiver(self._advertisement_callback)
        self._connect_lock = asyncio.Lock()
        #self._unit_update_buff = bytearray.fromhex(UNIT_UPDATE_COMMAND)
        if display_unit != None:
            self.display_unit = display_unit

    @property
    def hw_version(self) -> str:
        return self._hw_version

    @property
    def sw_version(self) -> str:
        return self._sw_version

    @property
    def display_unit(self):
        return self._display_unit

    @display_unit.setter
    def display_unit(self, value):
        if value != None:
            self._display_unit = value
            self._unit_update_flag = True

    async def async_start(self) -> None:
        """Start the callbacks."""
        _LOGGER.info(
            "Starting QnScale for address: %s", self.address
        )
        await self._scanner.start()

    async def async_stop(self) -> None:
        """Stop the callbacks."""
        _LOGGER.info(
            "Stopping QnScale for address: %s", self.address
        )
        await self._scanner.stop()

    def _notification_handler(
        self, _: BleakGATTCharacteristic, payload: bytearray, name: str, address: str
    ) -> None:
        _LOGGER.info("Notification handler start: ")
        _LOGGER.info(bytes(payload))
        # Handle notifications as per the new device model
        if data := parse(payload):
            _LOGGER.info(
                "Received stable weight notification from %s (%s): %s",
                name,
                address,
                data,
            )
            device = ScaleData()
            device.name = name
            device.address = address
            device.hw_version = self.hw_version
            device.sw_version = self.sw_version
            _LOGGER.info("%s (%s): %s", name, address, data)
            device.display_unit = WeightUnit(data.pop(DISPLAY_UNIT_KEY))

            if self._display_unit == None:
                self._display_unit = device.display_unit
                self._unit_update_flag = False
            else:
                self._unit_update_flag = device.display_unit != self._display_unit

            device.measurements = data
            self._notification_callback(device)

    # AI got this wrong
    def _process_data(self, weight: float, impedance: int) -> None:
        # Process the parsed weight and impedance
        scale_data = ScaleData(
            weight=weight,
            impedance=impedance,
            # Add other necessary fields
        )
        self._notification_callback(scale_data)

    def _unavailable_callback(self, _: BleakClient) -> None:
        self._client = None
        self._scanner.set_adv_callback(self._advertisement_callback)
        _LOGGER.info("Scale disconnected")

    async def _advertisement_callback(
        self, ble_device: BLEDevice, _: AdvertisementData
    ) -> None:
        """Connects to the device through BLE and retrieves relevant data."""
        if ble_device.address != self.address or self._client:
            return
        try:
            _LOGGER.info("Trying")
            async with self._connect_lock:
                if self._client:
                    return
                self._scanner.unset_adv_callback()
                self._client = await establish_connection(
                    BleakClient,
                    ble_device,
                    self.address,
                    self._unavailable_callback,
                )
                _LOGGER.info("Connected to scale: %s", self.address)
            
            # Tell the scale to use the unit we've selected, if any
            _LOGGER.info("If unit update flag")
            if self._unit_update_flag:
                if self._display_unit != None:
                    self._unit_update_buff[5] = 43 - self._display_unit
                    self._unit_update_buff[10] = self._display_unit
                    #await self._client.write_gatt_char(
                    #    ALIRO_CHARACTERISTIC_UUID, self._unit_update_buff, False
                    #)
                    _LOGGER.info(
                        "Trying to update display unit to %s (buffer: %s)",
                        self._display_unit,
                        self._unit_update_buff.hex(),
                    )
            
            # Grab the manufacturer name
            _LOGGER.info("If not mfr name")
            if not self._mfr_name:
                _LOGGER.info("Reading manufacturer name")
                self._mfr_name = (
                    await self._client.read_gatt_char(
                        MANUFACTURER_STRING_CHARACTERISTIC_UUID
                    )
                ).decode()
            _LOGGER.info("Manufacturer name: %s", self._mfr_name)

            # Grab the firmware version
            _LOGGER.info("If not self sw version")
            if not self._sw_version:
                _LOGGER.info("Reading sw version")
                self._sw_version = (
                    await self._client.read_gatt_char(
                        SW_REVISION_STRING_CHARACTERISTIC_UUID
                    )
                ).decode()
            
            # Grab the sw version
            # _LOGGER.info("Scale SW version: %s", self._sw_version)
            # self._sw_version = (
            #     await self._client.read_gatt_char(
            #         SW_REVISION_STRING_CHARACTERISTIC_UUID
            #     )
            # ).decode()
            #_LOGGER.info("Scale HW version: %s", self._hw_version)
            
            # Subscribe to notifications on the custom1 characteristic
            _LOGGER.info("Await start_notify")
            await self._client.start_notify(
                CUSTOM1_MEASUREMENT_CHARACTERISTIC_ALTERNATIVE,
                lambda char, data: self._notification_handler(
                    char, data, ble_device.name, ble_device.address
                ),
            )

            # Write magic number 0x130915[WEIGHT_BYTE]10000000[CHECK_SUM] to 0xffe3
            _LOGGER.info("Building magic ffe3 bytes")
            weight_unit_byte = 2 # 0x01 for kg, 0x02 for pounds
            ffe3_magic_bytes = bytearray(b"\x13\x09\x15\x00\x10\x00\x00\x00\x00")
            ffe3_magic_bytes[3] = 2
            ffe3_magic_bytes[-1] = sum_checksum(ffe3_magic_bytes, 0, len(ffe3_magic_bytes) - 1)
            await self._client.write_gatt_char(
                CUSTOM3_MEASUREMENT_CHARACTERISTIC_ALTERNATIVE,
                ffe3_magic_bytes
            )
            _LOGGER.info("Wrote magic ffe3 bytes")

            # Write magic number with timestamp - SCALE_UNIX_TIMESTAMP_OFFSET
            timestamp = int(time.time()) - SCALE_UNIX_TIMESTAMP_OFFSET
            date = bytearray(struct.pack('<I', timestamp))
            date.extend(bytearray(b"x02"))
            await self._client.write_gatt_char(
                CUSTOM3_MEASUREMENT_CHARACTERISTIC_ALTERNATIVE,
                date
            )
            _LOGGER.info("Wrote magic date bytes")

            
        except Exception as ex:
            self._client = None
            self._unit_update_flag = True
            self._scanner.set_adv_callback(self._advertisement_callback)
            _LOGGER.exception("%s(%s)", type(ex), ex.args)
