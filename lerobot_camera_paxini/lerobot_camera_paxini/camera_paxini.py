"""Paxini PX-6AX GEN3 tactile sensor as a LeRobot camera.

Any GEN3 variant works: the taxel count comes from the board (high-speed) or
the part code (serial converter), and the taxel coordinates come from the
sensor registry bundled with paxini-sdk. Nothing is hardcoded to one sensor.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

import numpy as np

from lerobot.cameras.camera import Camera

from .configuration_paxini import PaxiniCameraConfig
from .rasterize import TaxelRasterizer

logger = logging.getLogger(__name__)


class PaxiniCamera(Camera):
    """One Paxini GEN3 fingertip / pad rendered as an RGB image stream."""

    def __init__(self, config: PaxiniCameraConfig):
        super().__init__(config)
        self.config: PaxiniCameraConfig = config
        try:
            import paxini_sdk  # noqa: F401
        except ImportError as e:
            raise ImportError(
                "paxini-sdk is required: pip install "
                "'git+https://github.com/Jingyi-Z/paxini-sdk.git'"
            ) from e
        self._board = None
        self._module_name: str | None = None
        self._n_taxels: int | None = None
        self._raster: TaxelRasterizer | None = None
        self._connected = False
        self._latest: np.ndarray | None = None
        self._latest_lock = threading.Lock()
        self._new_frame = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def __str__(self) -> str:
        return f"PaxiniCamera({self.config.port}, {self._module_name or '?'})"

    @property
    def is_connected(self) -> bool:
        return self._connected

    @staticmethod
    def find_cameras() -> list[dict[str, Any]]:
        """List serial ports that look like Paxini communication boards."""
        try:
            from serial.tools import list_ports
        except ImportError:
            return []
        found = []
        for p in list_ports.comports():
            found.append(
                {"type": "paxini", "port": p.device, "description": p.description}
            )
        return found

    # ---- connect ---------------------------------------------------------

    def connect(self, warmup: bool = True) -> None:
        from paxini_sdk import sensor_registry

        cfg = self.config
        if cfg.board_type == "serial":
            self._connect_serial()
        else:
            self._connect_high_speed()

        variant = None
        if cfg.sensor_part_code:
            variant = sensor_registry.find_by_part_code(cfg.sensor_part_code)
            if variant and self._n_taxels and variant.n_points != self._n_taxels:
                raise RuntimeError(
                    f"sensor_part_code {cfg.sensor_part_code} has "
                    f"{variant.n_points} points but the board reports "
                    f"{self._n_taxels}"
                )
        if variant is None:
            variant = sensor_registry.find_by_point_count(self._n_taxels)
        if variant is None:
            raise RuntimeError(
                f"No registry entry for a {self._n_taxels}-point sensor; "
                "pass sensor_part_code explicitly."
            )
        points = np.asarray(sensor_registry.load_points(variant), np.float32)
        self._raster = TaxelRasterizer(
            points, cfg.width, cfg.height, cfg.splat_sigma_px
        )
        self._connected = True
        self._start_read_thread()
        if warmup:
            self._new_frame.wait(timeout=3.0)
        logger.info(
            f"{self}: {variant.vendor_part_code}, {self._n_taxels} taxels, "
            f"{cfg.render} {cfg.width}x{cfg.height}"
        )

    def _connect_high_speed(self) -> None:
        from paxini_sdk import HighSpeedHandBoard, registers

        self._board = HighSpeedHandBoard(
            self.config.port, baudrate=self.config.baud_rate
        )
        self._board.open()
        active = list(self._board.read_active_modules())
        if not active:
            raise RuntimeError("No active Paxini modules; check the FPC cable.")
        idx = self.config.module_index if self.config.module_index is not None else active[0]
        if idx not in active:
            raise RuntimeError(f"module {idx} not active (active: {active})")
        self._module_name = registers.MODULE_NAMES[idx]
        self._n_taxels = self._board.read_distribution_point_count(idx)
        if self.config.auto_calibrate:
            self._board.calibrate()

    def _connect_serial(self) -> None:
        from paxini_sdk import SingleSensorBoard, sensor_registry

        variant = sensor_registry.find_by_part_code(self.config.sensor_part_code)
        if variant is None:
            raise RuntimeError(f"unknown part code {self.config.sensor_part_code!r}")
        self._n_taxels = variant.n_points
        self._module_name = variant.vendor_part_code
        self._board = SingleSensorBoard(
            self.config.port,
            baudrate=self.config.baud_rate,
            sensor=variant,
            device_id=self.config.device_id,
        )
        self._board.open()
        if self.config.auto_calibrate:
            self._board.calibrate()

    # ---- read loop -------------------------------------------------------

    def _render(self, forces: np.ndarray) -> np.ndarray:
        if self.config.render == "heatmap":
            return self._raster.heatmap(forces, self.config.force_max_n)
        return self._raster.vector_rgb(forces, self.config.force_max_n)

    def _publish(self, forces: np.ndarray) -> None:
        img = self._render(forces)
        with self._latest_lock:
            self._latest = img
        self._new_frame.set()

    def _read_loop(self) -> None:
        cfg = self.config
        if cfg.board_type == "serial":
            period = 1.0 / cfg.fps if cfg.fps else 0.0
            while not self._stop.is_set():
                t0 = time.monotonic()
                try:
                    pts = self._board.read_distributed_force()
                    f = np.array(
                        [(p.fx, p.fy, p.fz) for p in pts], np.float32
                    ) * 0.1  # counts -> newtons
                    self._publish(f)
                except Exception as e:
                    logger.warning(f"{self}: read failed, retrying: {e}")
                    self._stop.wait(0.1)
                    continue
                rest = period - (time.monotonic() - t0)
                if rest > 0:
                    self._stop.wait(rest)
        else:
            try:
                for frame in self._board.stream_auto_push(per_frame_timeout=0.5):
                    if self._stop.is_set():
                        break
                    pts = frame.distributed_forces_newtons.get(self._module_name)
                    if not pts:
                        continue
                    f = np.asarray(pts, np.float32)
                    if f.shape[0] != self._n_taxels:
                        pad = np.zeros((self._n_taxels, 3), np.float32)
                        pad[: min(len(f), self._n_taxels)] = f[: self._n_taxels]
                        f = pad
                    self._publish(f)
            except Exception as e:
                if not self._stop.is_set():
                    logger.exception(f"{self}: stream terminated: {e}")

    def _start_read_thread(self) -> None:
        self._stop.clear()
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()

    # ---- Camera API ------------------------------------------------------

    def read(self, color_mode=None) -> np.ndarray:  # noqa: ANN001
        img = self.async_read(timeout_ms=1000)
        return img

    def async_read(self, timeout_ms: float = 200) -> np.ndarray:
        if not self._connected:
            raise RuntimeError(f"{self} is not connected")
        if self._latest is None and not self._new_frame.wait(timeout_ms / 1000):
            raise TimeoutError(f"{self}: no tactile frame within {timeout_ms} ms")
        with self._latest_lock:
            return self._latest.copy()

    def disconnect(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None
        if self._board is not None:
            try:
                self._board.close()
            except Exception:
                pass
            self._board = None
        self._connected = False
