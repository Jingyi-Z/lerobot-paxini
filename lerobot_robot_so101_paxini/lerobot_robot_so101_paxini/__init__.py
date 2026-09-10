"""LeRobot robot plugin: SO-101 follower with Paxini tactile fingertips.

Importing this package registers the ``so101_paxini`` robot type with lerobot.
"""

from .config_so101_paxini import PaxiniSensorConfig, SO101PaxiniConfig
from .so101_paxini import SO101Paxini

__all__ = ["PaxiniSensorConfig", "SO101PaxiniConfig", "SO101Paxini"]
