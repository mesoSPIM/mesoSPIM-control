"""Small acquisition containers for the in-memory test state.

Production command execution still imports mesoSPIM's real acquisition classes. These containers
only seed the fake Core before the application has registered its image-writer plugins.
"""


class Acquisition(dict):
    """Dict-like geometry used by the fake acquisition list."""

    def __init__(self):
        super().__init__(z_start=0, z_end=100, z_step=10, planes=10)

    def get_image_count(self):
        return abs(round((self["z_end"] - self["z_start"]) / self["z_step"])) + 1


class AcquisitionList(list):
    """List-like container matching the Core state surface used by Remote Control."""
