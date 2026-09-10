"""Configuration for the Paxini tactile camera plugin."""

from dataclasses import dataclass

from lerobot.cameras.configs import CameraConfig


@CameraConfig.register_subclass("paxini")
@dataclass(kw_only=True)
class PaxiniCameraConfig(CameraConfig):
    """One Paxini GEN3 sensor rendered as a camera image.

    Every GEN3 variant works: the taxel coordinates come from the sensor
    registry in paxini-sdk (or, for the high-speed board, the point count is
    read from the board and matched against the registry).

    Rendering:
    - ``render="vector_rgb"`` (default): per-taxel (Fx, Fy, Fz) splatted into
      the R, G, B channels, signed forces centered at 128. Lossless enough for
      policies while staying a normal uint8 image.
    - ``render="heatmap"``: force magnitude on a green-yellow-red colormap,
      matching the vendor host app. For humans and demos.

    Record with ``--dataset.video=false`` (PNG) if the exact per-taxel values
    matter downstream; the default video path is lossy and subsamples chroma.
    """

    # Serial port of the communication board.
    port: str
    # "high_speed" (auto-push ~91 Hz, up to 28 modules) or "serial" (request/response).
    board_type: str = "high_speed"
    # High-speed board: which module slot. None = first active.
    module_index: int | None = None
    # Serial board: the vendor part code (the board cannot report its sensor).
    # Optional on high_speed; if set it must agree with the board's point count.
    sensor_part_code: str | None = None
    baud_rate: int = 921_600
    # Serial board only: fin-protocol device id. GEN3 USB fingertips have been
    # observed at 3 (255 is broadcast); older docs assume 1. If the sensor is
    # silent, scan ids 0-255 with a resultant-force read.
    device_id: int = 3

    render: str = "vector_rgb"
    # Force in newtons that maps to full channel deflection (vector_rgb) or
    # saturates red (heatmap).
    force_max_n: float = 5.0
    # Gaussian splat radius in pixels; 0 = nearest-pixel only.
    splat_sigma_px: float = 3.0

    auto_calibrate: bool = True

    def __post_init__(self) -> None:
        if self.board_type not in ("high_speed", "serial"):
            raise ValueError(f"board_type must be high_speed or serial, got {self.board_type!r}")
        if self.board_type == "serial" and not self.sensor_part_code:
            raise ValueError("board_type='serial' requires sensor_part_code")
        if self.render not in ("vector_rgb", "heatmap"):
            raise ValueError(f"render must be vector_rgb or heatmap, got {self.render!r}")
        if self.fps is None:
            self.fps = 30
        # Image size defaults; any aspect works, the taxel cloud is fit inside.
        if self.width is None:
            self.width = 240
        if self.height is None:
            self.height = 320
