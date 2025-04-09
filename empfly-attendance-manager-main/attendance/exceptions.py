
from typing import List


class KioskScanError(Exception):
    """ Check in and check out kiosk
    """

    message:str
    def __init__(self, *args: object) -> None:
        super().__init__(*args)
        self.message = args[0]

class CaptureFRImagError(Exception):
    """ Check in and check out kiosk
    """

    message:str
    def __init__(self, *args: object) -> None:
        super().__init__(*args)
        self.message = args[0]


class DitAuthError(Exception):
    """ device identifier token is invalid
    """

    message:str
    def __init__(self, *args: object) -> None:
        super().__init__(*args)
        self.message = args[0]
