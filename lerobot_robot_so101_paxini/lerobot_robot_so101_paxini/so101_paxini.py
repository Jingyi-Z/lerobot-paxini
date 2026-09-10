"""SO-101 follower with Paxini tactile fingertips, as a stock-lerobot robot."""

import logging
import warnings
from functools import cached_property
from typing import Any

import numpy as np

from lerobot.robots.so_follower.so_follower import SOFollower

from .config_so101_paxini import SO101PaxiniConfig
from .paxini_sensor import PaxiniSensor

logger = logging.getLogger(__name__)

_AXES = ("fx", "fy", "fz")


def flatten_names(sensor_name: str, shape: tuple[int, ...], output_format: str) -> list[str]:
    """Names for every scalar of one sensor sample, in C order, matching ``np.ravel``.

    Stock lerobot puts every non-image robot feature into ``observation.state`` as a
    flat float vector with one name per element, so a (n_fingers, P, 3) tactile sample
    becomes n_fingers*P*3 named floats. Names:

    - combined   (F, P, 3):  <sensor>.f<k>.p<ii>.<fx|fy|fz>
    - distributed(N, P, 3):  <sensor>.t<n>.p<ii>.<fx|fy|fz>   (t = history index, 0 = oldest)
    - resultant  (N, 3):     <sensor>.t<n>.<fx|fy|fz>
    - both       (N, 3+P*3): <sensor>.t<n>.<fx|fy|fz> then <sensor>.t<n>.p<ii>.<fx|fy|fz>
    """
    names: list[str] = []
    if output_format == "combined":
        f, p, c = shape
        for k in range(f):
            for i in range(p):
                names += [f"{sensor_name}.f{k}.p{i:02d}.{a}" for a in _AXES[:c]]
    elif output_format == "distributed":
        n, p, c = shape
        for t in range(n):
            for i in range(p):
                names += [f"{sensor_name}.t{t}.p{i:02d}.{a}" for a in _AXES[:c]]
    elif output_format == "resultant":
        n, c = shape
        for t in range(n):
            names += [f"{sensor_name}.t{t}.{a}" for a in _AXES[:c]]
    elif output_format == "both":
        n, d = shape
        p = (d - 3) // 3
        for t in range(n):
            names += [f"{sensor_name}.t{t}.{a}" for a in _AXES]
            for i in range(p):
                names += [f"{sensor_name}.t{t}.p{i:02d}.{a}" for a in _AXES]
    else:
        raise ValueError(f"Unknown output_format {output_format!r}")
    assert len(names) == int(np.prod(shape)), (len(names), shape)
    return names


class SO101Paxini(SOFollower):
    """SO-101 follower whose observation also carries Paxini fingertip forces.

    Each sensor in ``config.sensors`` is flattened into named float features so it
    lands in ``observation.state`` on stock lerobot. Joint positions come first
    (parent order), tactile after, in config order.
    """

    config_class = SO101PaxiniConfig
    name = "so101_paxini"

    def __init__(self, config: SO101PaxiniConfig):
        super().__init__(config)
        self.config: SO101PaxiniConfig = config
        self._sensors: dict[str, PaxiniSensor] = {}
        self._tactile_names: dict[str, list[str]] = {}
        self._last_sensor_data: dict[str, np.ndarray] = {}
        # Sensors come up here, not in connect(): lerobot-record reads
        # observation_features before robot.connect(), and the taxel count is
        # only known once the board has been opened.
        for sensor_name, scfg in config.sensors.items():
            sensor = PaxiniSensor(scfg)
            sensor.set_sensor_name(sensor_name)
            sensor.connect()
            sensor.start_continuous_read()
            self._sensors[sensor_name] = sensor
            self._tactile_names[sensor_name] = flatten_names(
                sensor_name, sensor.shape, scfg.output_format
            )
            logger.info(
                f"Sensor '{sensor_name}' up: shape={sensor.shape}, "
                f"{len(self._tactile_names[sensor_name])} state columns"
            )

    # ---- lifecycle -------------------------------------------------------

    def disconnect(self) -> None:
        for sensor_name, sensor in self._sensors.items():
            try:
                sensor.disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting sensor '{sensor_name}': {e}")
        super().disconnect()

    # ---- features --------------------------------------------------------

    @property
    def _tactile_ft(self) -> dict[str, type]:
        ft: dict[str, type] = {}
        for names in self._tactile_names.values():
            for n in names:
                ft[n] = float
        return ft

    @cached_property
    def observation_features(self) -> dict[str, type | tuple]:
        # Parent order first (motors then cameras), then tactile scalars.
        return {**self._motors_ft, **self._tactile_ft, **self._cameras_ft}

    # ---- observation -----------------------------------------------------

    def get_observation(self) -> dict[str, Any]:
        obs = super().get_observation()
        for sensor_name, sensor in self._sensors.items():
            names = self._tactile_names.get(sensor_name)
            if not names:
                continue
            data = None
            try:
                data = sensor.get_latest_data()
            except Exception as e:
                warnings.warn(
                    f"Sensor '{sensor_name}' read raised {type(e).__name__}: {e}",
                    RuntimeWarning, stacklevel=2,
                )
            if data is None:
                # Reuse the last good reading; zeros would fabricate a contact loss.
                data = self._last_sensor_data.get(sensor_name)
                if data is None:
                    data = np.zeros(sensor.shape, dtype=np.float32)
            else:
                self._last_sensor_data[sensor_name] = data
            flat = np.asarray(data, dtype=np.float32).ravel()
            if flat.shape[0] != len(names):
                raise RuntimeError(
                    f"Sensor '{sensor_name}' returned {flat.shape[0]} values, "
                    f"expected {len(names)}"
                )
            for n, v in zip(names, flat):
                obs[n] = float(v)
        return obs

    def sensor_metadata(self) -> dict[str, dict]:
        return {name: s.metadata() for name, s in self._sensors.items()}
