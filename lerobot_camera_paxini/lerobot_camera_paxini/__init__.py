"""LeRobot camera plugin for Paxini PX-6AX GEN3 tactile sensors.

Importing this package registers the ``paxini`` camera type with lerobot.
Works with every GEN3 variant (9 to 239 taxels): the taxel layout is read
from the sensor registry bundled in paxini-sdk, never hardcoded.
"""

from .configuration_paxini import PaxiniCameraConfig
from .camera_paxini import PaxiniCamera

__all__ = ["PaxiniCameraConfig", "PaxiniCamera"]
