import asyncio
import threading
import time
from typing import List, Optional

import requests
from pymobiledevice3.lockdown import create_using_usbmux
from pymobiledevice3.remote.remote_service_discovery import (
    RemoteServiceDiscoveryService,
)
from pymobiledevice3.services.amfi import AmfiService
from pymobiledevice3.services.dvt.dvt_secure_socket_proxy import (
    DvtSecureSocketProxyService,
)
from pymobiledevice3.services.dvt.instruments.location_simulation import (
    LocationSimulation,
)
from pymobiledevice3.usbmux import list_devices

from src.core.models import DeviceInfo
from src.utils.logger import logger


class DeviceManager:
    """
    Manages iOS device connection and location simulation using pymobiledevice3.
    Supports iOS 17+ via the RSD tunnel mechanism.
    """

    def __init__(self):
        self.service_provider = None
        self.connected = False
        self.current_device: Optional[DeviceInfo] = None
        self._lock = threading.Lock()
        # Keep DVT service alive to prevent location reset
        self._dvt_service = None
        self._location_sim = None

    @staticmethod
    def discover_devices() -> List[DeviceInfo]:
        """
        Discover connected iOS devices via tunneld.
        Returns a list of DeviceInfo objects.
        """
        devices = []
        try:
            # Try to get devices from tunneld HTTP API (root endpoint /)
            try:
                response = requests.get("http://127.0.0.1:49151/", timeout=2)
                if response.status_code == 200:
                    tunnels_data = response.json()
                    # Response format: {UDID: [{tunnel-address, tunnel-port, interface}, ...]}
                    for udid, tunnel_list in tunnels_data.items():
                        if not tunnel_list:
                            continue
                        # Use the first tunnel for each device
                        tunnel_info = (
                            tunnel_list[0]
                            if isinstance(tunnel_list, list)
                            else tunnel_list
                        )
                        try:
                            rsd_address = tunnel_info.get("tunnel-address", "")
                            rsd_port = tunnel_info.get("tunnel-port", 0)

                            if rsd_address and rsd_port:
                                # Try to get device name from lockdown
                                device_name = f"iOS Device ({udid[:8]}...)"
                                product_type = "Unknown"
                                ios_version = "17+"

                                try:
                                    lockdown = create_using_usbmux(serial=udid)
                                    device_name = (
                                        lockdown.display_name
                                        or lockdown.get_value(key="DeviceName")
                                        or device_name
                                    )
                                    product_type = lockdown.product_type or product_type
                                    ios_version = (
                                        lockdown.product_version or ios_version
                                    )
                                    lockdown.close()
                                except Exception:
                                    pass

                                device_info = DeviceInfo(
                                    udid=udid,
                                    name=device_name,
                                    product_type=product_type,
                                    ios_version=ios_version,
                                    rsd_address=rsd_address,
                                    rsd_port=rsd_port,
                                )
                                devices.append(device_info)
                                logger.info(
                                    f"Found device: {device_name} ({product_type} - iOS {ios_version})"
                                )
                        except Exception as e:
                            logger.warning(f"Failed to parse tunnel info: {e}")
            except requests.exceptions.ConnectionError:
                logger.warning("tunneld HTTP API not available on port 49151")
            except Exception as e:
                logger.warning(f"Failed to get devices from tunneld API: {e}")

        except Exception as e:
            logger.error(f"Failed to discover devices: {e}")

        return devices

    @staticmethod
    def discover_devices_via_browse() -> List[DeviceInfo]:
        """
        Alternative discovery using usbmux to find connected devices.
        Gets device name from lockdown and checks for tunnel availability.
        """
        devices = []
        try:
            # Get list of USB-connected devices
            usb_devices = list_devices()

            # Try to get device info for each
            for usb_dev in usb_devices:
                try:
                    # Get device info from lockdown
                    device_name = "iOS Device"
                    product_type = "Unknown"
                    ios_version = "17+"

                    try:
                        lockdown = create_using_usbmux(serial=usb_dev.serial)
                        device_name = (
                            lockdown.display_name
                            or lockdown.get_value(key="DeviceName")
                            or "iOS Device"
                        )
                        product_type = lockdown.product_type or "Unknown"
                        ios_version = lockdown.product_version or "17+"
                        lockdown.close()
                    except Exception as e:
                        logger.warning(
                            f"Could not get lockdown info for {usb_dev.serial[:8]}: {e}"
                        )

                    # Try to get tunnel from tunneld API (root endpoint /)
                    rsd_address = ""
                    rsd_port = 0
                    try:
                        response = requests.get("http://127.0.0.1:49151/", timeout=2)
                        if response.status_code == 200:
                            tunnels = response.json()
                            if usb_dev.serial in tunnels:
                                tunnel_list = tunnels[usb_dev.serial]
                                if tunnel_list:
                                    tunnel_info = (
                                        tunnel_list[0]
                                        if isinstance(tunnel_list, list)
                                        else tunnel_list
                                    )
                                    rsd_address = tunnel_info.get("tunnel-address", "")
                                    rsd_port = tunnel_info.get("tunnel-port", 0)
                    except Exception:
                        pass

                    # Only add device if we have valid RSD address
                    if rsd_address and rsd_port:
                        device_info = DeviceInfo(
                            udid=usb_dev.serial,
                            name=device_name,
                            product_type=product_type,
                            ios_version=ios_version,
                            rsd_address=rsd_address,
                            rsd_port=rsd_port,
                        )
                        devices.append(device_info)
                        logger.info(
                            f"Found device: {device_name} ({product_type} - iOS {ios_version})"
                        )
                    else:
                        logger.warning(
                            f"Device {device_name} found but no tunnel available. "
                            "Please restart the application as Administrator to enable connectivity."
                        )

                except Exception as e:
                    logger.warning(f"Failed to process USB device: {e}")

        except Exception as e:
            logger.error(f"Failed to browse devices: {e}")

        return devices

    def connect_to_device(self, device: DeviceInfo) -> bool:
        """Connect to a specific iOS device via RSD tunnel."""
        try:
            with self._lock:
                # Disconnect if already connected
                if self.service_provider:
                    try:
                        close_result = self.service_provider.close()
                        if asyncio.iscoroutine(close_result):
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            try:
                                loop.run_until_complete(close_result)
                            finally:
                                loop.close()
                    except Exception:
                        pass
                    self.service_provider = None

                # Create RSD connection
                self.service_provider = RemoteServiceDiscoveryService(
                    (device.rsd_address, device.rsd_port)
                )

                # Handle async connect
                connect_result = self.service_provider.connect()
                if asyncio.iscoroutine(connect_result):
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        loop.run_until_complete(connect_result)
                    finally:
                        loop.close()

                self.current_device = device
                self.connected = True
                logger.info(f"Connected to device: {device.display_name()}")
                return True

        except Exception as e:
            logger.error(f"Failed to connect to device: {e}")
            self.connected = False
            self.current_device = None
            return False

    def set_location(self, latitude: float, longitude: float) -> bool:
        """Set the simulated GPS location on the device."""
        try:
            with self._lock:
                if not self.connected or self.service_provider is None:
                    logger.error("Device not connected")
                    return False

                # Create or reuse DVT service to keep location simulation alive
                if self._dvt_service is None:
                    self._dvt_service = DvtSecureSocketProxyService(
                        self.service_provider
                    )
                    self._dvt_service.__enter__()
                    self._location_sim = LocationSimulation(self._dvt_service)
                    logger.info(
                        "Created persistent DVT connection for location simulation"
                    )

                self._location_sim.set(latitude, longitude)
                logger.debug(f"Location set to: {latitude}, {longitude}")
                return True

        except Exception as e:
            logger.error(f"Failed to set location: {e}")
            # Reset DVT service on error so it can be recreated
            self._close_dvt_service()
            return False

    def _close_dvt_service(self):
        """Close the DVT service if open."""
        if self._dvt_service is not None:
            try:
                self._dvt_service.__exit__(None, None, None)
            except Exception:
                pass
            self._dvt_service = None
            self._location_sim = None

    def clear_location(self) -> bool:
        """Clear the simulated location."""
        try:
            with self._lock:
                if not self.connected or self.service_provider is None:
                    logger.error("Device not connected")
                    return False

                # Use existing location sim if available
                if self._location_sim is not None:
                    self._location_sim.clear()
                    logger.info("Location simulation cleared")
                    # Close the DVT service since we're done
                    self._close_dvt_service()
                    return True
                else:
                    logger.info("No active location simulation to clear")
                    return True

        except Exception as e:
            logger.error(f"Failed to clear location: {e}")
            self._close_dvt_service()
            return False

    def disconnect(self):
        """Disconnect from the device."""
        with self._lock:
            self._close_dvt_service()

            if self.service_provider:
                try:
                    close_result = self.service_provider.close()
                    if asyncio.iscoroutine(close_result):
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            loop.run_until_complete(close_result)
                        finally:
                            loop.close()
                except Exception:
                    pass
                self.service_provider = None
            self.connected = False
            self.current_device = None
            logger.info("Disconnected from device")

    def check_developer_mode(self, udid: str = None) -> Optional[bool]:
        """Check developer mode status."""
        try:
            target_udid = udid
            if not target_udid and self.current_device:
                target_udid = self.current_device.udid

            if not target_udid:
                # Attempt to discover first USB device
                devices = list_devices()
                if devices:
                    target_udid = devices[0].serial

            if not target_udid:
                return None

            with create_using_usbmux(serial=target_udid) as lockdown:
                return lockdown.developer_mode_status
        except Exception as e:
            logger.warning(f"Failed to check developer mode: {e}")
            return None

    def enable_developer_mode(self, udid: str = None) -> bool:
        """trigger enable developer mode."""
        try:
            target_udid = udid
            if not target_udid and self.current_device:
                target_udid = self.current_device.udid

            if not target_udid:
                devices = list_devices()
                if devices:
                    target_udid = devices[0].serial

            if not target_udid:
                return False

            with create_using_usbmux(serial=target_udid) as lockdown:
                amfi = AmfiService(lockdown)
                amfi.enable_developer_mode()
                return True
        except Exception as e:
            logger.error(f"Failed to enable developer mode: {e}")
            return False

    def auto_mount_developer_disk_image(self, udid: str = None) -> bool:
        """
        Auto-mount Developer Disk Image.
        """
        try:
            from pymobiledevice3.services.mobile_image_mounter import auto_mount

            target_udid = udid
            if not target_udid and self.current_device:
                target_udid = self.current_device.udid

            if not target_udid:
                devices = list_devices()
                if devices:
                    target_udid = devices[0].serial

            if not target_udid:
                return False

            async def _run_async_mount():
                async with create_using_usbmux(serial=target_udid) as lockdown:
                    await auto_mount(lockdown)

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(_run_async_mount())
                return True
            except Exception as e:
                logger.warning(f"Auto-mount warning: {e}")
                return True
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"Failed to run auto-mount: {e}")
            return False
