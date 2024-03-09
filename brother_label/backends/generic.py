import typing
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class DeviceInfo:
    backend: str = ""
    manufacturer: str = ""
    device: str = ""
    serial: str = ""
    usb_product_id: str = ""
    usb_vendor_id: str = ""
    usb_bus_num: int = ""
    usb_dev_num: int = ""
    device_specifier: str = ""
    handle: object = None


class BrotherQLBackendGeneric(object):
    def __init__(self, device_specifier):
        """
        device_specifier can be either a string or an instance
        of the required class type.
        """
        self.write_dev = None
        self.read_dev = None
        raise NotImplementedError()

    def _write(self, data):
        self.write_dev.write(data)

    def _read(self, length=32):
        return bytes(self.read_dev.read(length))

    def write(self, data):
        logger.debug("Writing %d bytes.", len(data))
        self._write(data)

    def read(self, length=32):
        try:
            ret_bytes = self._read(length)
            if ret_bytes:
                logger.debug("Read %d bytes.", len(ret_bytes))
            return ret_bytes
        except Exception as e:
            logger.debug("Error reading... %s", e)
            raise

    def dispose(self):
        try:
            self._dispose()
        except:
            pass

    def _dispose(self):
        raise NotImplementedError()

    def __del__(self):
        self.dispose()

    @staticmethod
    def discover() -> list[DeviceInfo]:
        return []
