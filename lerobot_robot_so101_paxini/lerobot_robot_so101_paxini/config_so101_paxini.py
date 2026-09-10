"""Configuration for the SO-101 + Paxini robot plugin."""

from dataclasses import dataclass, field

from lerobot.robots.config import RobotConfig
from lerobot.robots.so_follower.config_so_follower import SOFollowerConfig


@dataclass
class PaxiniSensorConfig:
    """One Paxini sensor entry. Ported from lerobotac's PaxiniSensorConfig with
    the rerun display fields and the per-episode raw CSV hooks removed."""

    # Serial port of the communication board. Linux: /dev/ttyUSB0, macOS: /dev/cu.usbserial-XXXX.
    port: str = "/dev/ttyUSB0"
    baud_rate: int = 921_600

    # "high_speed" -> High-Speed Communication Board, auto-push ~91 Hz.
    # "serial"     -> Serial Converter Board, request/response, one sensor.
    board_type: str = "high_speed"

    # High-speed board, single module: which slot to read. None = first active slot.
    module_index: int | None = None
    # High-speed board, combined mode: all fingers to read, list order = finger order.
    module_indices: list[int] | None = None

    # Serial board only.
    sensor_part_code: str | None = None
    device_id: int = 0x01

    # "resultant"   -> (buffer_size, 3)
    # "distributed" -> (buffer_size, P, 3)
    # "both"        -> (buffer_size, 3 + P*3)
    # "combined"    -> (n_fingers, P, 3), latest sample per finger, no history buffer
    output_format: str = "combined"
    buffer_size: int = 10

    # 0 = native board rate. Otherwise the high-speed stream is downsampled to this rate
    # (non-combined modes only) or the serial poll loop is locked to it.
    poll_rate_hz: float = 0.0

    auto_calibrate: bool = True
    software_baseline_frames: int = 0

    # Session-long raw stream sidecar (91 Hz), cut per episode afterwards by timestamp.
    # Stock lerobot-record has no per-episode sensor hooks, so this replaces the
    # start/finish/discard_raw_episode lifecycle from the fork.
    record_raw_csv: bool = False
    raw_csv_dir: str | None = None
    raw_csv_filename: str = "sensor_{n}.csv"

    # Optional rerun 3D force arrows, only when a rerun session is already running
    # (e.g. lerobot-record --display_data=true). Default off.
    display_rerun: bool = False
    rerun_arrow_scale_mm_per_n: float = 2.0
    rerun_force_max_n: float = 5.0
    rerun_force_threshold_n: float = 0.15


@RobotConfig.register_subclass("so101_paxini")
@dataclass
class SO101PaxiniConfig(RobotConfig, SOFollowerConfig):
    """SO-101 follower plus Paxini fingertips.

    Example::

        lerobot-record --robot.type=so101_paxini --robot.port=/dev/ttyACM0 \\
          --robot.sensors='{paxini_fingertip: {port: /dev/ttyUSB0, module_indices: [10, 18]}}'
    """

    sensors: dict[str, PaxiniSensorConfig] = field(default_factory=dict)
