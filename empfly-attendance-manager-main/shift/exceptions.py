
from typing import List


class EditShiftError(Exception):
    """If shift is not editable"""

    def __init__(self, *args: object) -> None:
        super().__init__(*args)
        self.err = args

    def error(self) -> List[str]:
        """throwed error"""
        return self.err



class ValidateLocSettingsErr(Exception):
    """Validation for location settings create and update"""

    def __init__(self, *args: object) -> None:
        super().__init__(*args)
        self.message = args[0]

class UploadCSVLocSettingsErr(Exception):
    """Validation for location settings create and update"""

    def __init__(self, *args: object) -> None:
        super().__init__(*args)
        self.message = args[0]
