import asyncio
import logging
import platform
from collections.abc import Callable
from enum import Enum
from typing import Any, Literal

from bleak import BleakError
from bleak.assigned_numbers import AdvertisementDataType
from bleak.backends.scanner import (
    AdvertisementDataCallback,
    BaseBleakScanner,
    get_platform_scanner_backend_type,
)

_LOGGER = logging.getLogger(__name__)

SYSTEM = platform.system()
IS_LINUX = SYSTEM == "Linux"
IS_MACOS = SYSTEM == "Darwin"


if IS_LINUX:
    from bleak.backends.bluezdbus.advertisement_monitor import OrPattern
    from bleak.backends.bluezdbus.scanner import BlueZScannerArgs

    # or_patterns is a workaround for the fact that passive scanning
    # needs at least one matcher to be set. The below matcher
    # will match all devices.
    PASSIVE_SCANNER_ARGS = BlueZScannerArgs(
        or_patterns=[
            OrPattern(0, AdvertisementDataType.FLAGS, b"\x02"),
            OrPattern(0, AdvertisementDataType.FLAGS, b"\x06"),
            OrPattern(0, AdvertisementDataType.FLAGS, b"\x1a"),
        ]
    )

if IS_MACOS:
    from bleak.backends.corebluetooth.scanner import CBScannerArgs


class BluetoothScanningMode(Enum):
    """The mode of scanning for bluetooth devices."""

    PASSIVE = "passive"
    ACTIVE = "active"


SCANNING_MODE_TO_BLEAK: dict[BluetoothScanningMode, str] = {
    BluetoothScanningMode.ACTIVE: "active",
    BluetoothScanningMode.PASSIVE: "passive",
}


class AdvertisementReceiver:
    def __init__(
        self,
        detection_callback: AdvertisementDataCallback,
        service_uuids: list[str] | None = None,
        scanning_mode: Literal["active", "passive"] = "active",
        *,
        backend: type[BaseBleakScanner] | None = None,
        **kwargs,
    ) -> None:
        PlatformBleakScanner = (
            get_platform_scanner_backend_type() if backend is None else backend
        )

        self._backend = PlatformBleakScanner(
            detection_callback,
            service_uuids,
            scanning_mode,
            **kwargs,
        )
        self._backend_lock = asyncio.Lock()
        self._remove_callback: Callable[[], None] = None

    async def start(self) -> None:
        """Start scanning for devices."""
        async with self._backend_lock:
            await self._backend.start()

    async def stop(self) -> None:
        """Stop scanning for devices."""
        async with self._backend_lock:
            await self._backend.stop()

    def set_adv_callback(self, callback: AdvertisementDataCallback) -> None:
        if self._remove_callback:
            self._remove_callback()

        self._remove_callback = self._backend.register_detection_callback(callback)

    def unset_adv_callback(self) -> None:
        if self._remove_callback:
            self._remove_callback()

        self._remove_callback = None


def create_adv_receiver(
    detection_callback: AdvertisementDataCallback,
    scanning_mode: BluetoothScanningMode = BluetoothScanningMode.ACTIVE,
    adapter: str | None = None,
) -> AdvertisementReceiver:
    """Create and return an AdvertisementReceiver instance.

    Args:
        detection_callback: Callback function for detected advertisements.
        scanning_mode: The mode of scanning (active or passive).
        adapter: The Bluetooth adapter to use (Linux only).

    Returns:
        An instance of AdvertisementReceiver.

    """
    scanner_kwargs: dict[str, Any] = {
        "detection_callback": detection_callback,
        "scanning_mode": SCANNING_MODE_TO_BLEAK[scanning_mode],
        "bluez": {},
        "cb": {},
    }
    if IS_LINUX:
        # Only Linux supports multiple adapters
        if adapter:
            scanner_kwargs["adapter"] = adapter
        if scanning_mode == BluetoothScanningMode.PASSIVE:
            scanner_kwargs["bluez"] = PASSIVE_SCANNER_ARGS
    elif IS_MACOS:
        # We want mac address on macOS
        scanner_kwargs["cb"] = {"use_bdaddr": True}
    _LOGGER.debug("Initializing bluetooth scanner with %s", scanner_kwargs)

    try:
        return AdvertisementReceiver(**scanner_kwargs)
    except (FileNotFoundError, BleakError) as ex:
        raise RuntimeError(f"Failed to initialize Bluetooth: {ex}") from ex

def sum_checksum(
    data: bytearray,
    offset: int,
    length: int,
) -> int:
    checksum = 0
    for i in range(offset, offset + length - 1):
        checksum += data[i]
    return checksum