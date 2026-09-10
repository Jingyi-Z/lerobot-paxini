# User guide: lerobot_camera_paxini

Any Paxini PX-6AX GEN3 tactile sensor as a LeRobot camera. Installing it adds a `paxini` camera type to stock lerobot. The sensor's taxel array is rendered as an ordinary RGB image, so it drops into any pipeline that takes cameras: recording, visualization, and image-based policies.

All GEN3 variants work, from the 9-taxel fingernail to the 239-taxel palm pad. The plugin reads the taxel count from your hardware and looks up the taxel coordinates in the registry bundled with paxini-sdk. You never enter a layout.

## What you need

1. Any PX-6AX GEN3 sensor.
2. A Paxini communication board. High-Speed Communication Board (many sensors, one port, about 91 Hz auto push) or Serial Converter Board (one sensor per port).
3. Python 3.10 or later, lerobot 0.6.2 or later.

## Install

```bash
pip install lerobot
pip install paxini-sdk
pip install lerobot_camera_paxini
```

## Use it like any camera

```bash
lerobot-record \
  --robot.type=so101_follower --robot.port=/dev/ttyACM0 --robot.id=follower \
  --robot.cameras='{
    top: {type: opencv, index_or_path: 2, width: 640, height: 480, fps: 30},
    tactile: {type: paxini, port: /dev/ttyUSB0, width: 240, height: 320, fps: 30}
  }' \
  ...
```

The tactile stream shows up as `observation.images.tactile`, an ordinary video alongside your real cameras.

For the Serial Converter Board add the part code, which that board cannot report by itself:

```
tactile: {type: paxini, port: /dev/ttyUSB0, board_type: serial, sensor_part_code: PXSR-STDDP03G}
```

## The two render modes

`render: vector_rgb` is the default and the one to train on. Each taxel's (Fx, Fy, Fz) force vector goes into the (R, G, B) channels, signed forces centered at gray 128, full scale set by `force_max_n` (default 5 N). The full 3-axis force field survives as an image.

`render: heatmap` shows force magnitude on the green to yellow to red ramp of the vendor app. Use it for demos, debugging, and checking which taxel is which.

## Configuration reference

| Field | Default | Meaning |
|---|---|---|
| `port` | required | Serial port of the communication board |
| `board_type` | high_speed | `high_speed` or `serial` |
| `module_index` | first active | High-speed board, which slot to render |
| `sensor_part_code` | none | Required for `serial`, optional cross-check for `high_speed` |
| `width`, `height` | 240 x 320 | Output image size, the taxel cloud is fit inside |
| `fps` | 30 | Poll rate for `serial`, ignored by the push stream |
| `render` | vector_rgb | `vector_rgb` or `heatmap` |
| `force_max_n` | 5.0 | Newtons at full channel deflection |
| `splat_sigma_px` | 3.0 | Gaussian splat radius, 0 gives single-pixel taxels |
| `auto_calibrate` | true | Zero the sensor at connect, keep the pad contact free |

## If exact force values matter

The default video path is lossy and halves chroma resolution. Two options, in order of preference:

1. Record with `--dataset.video=false`, which stores frames as lossless PNG for every camera in the run, including your real cameras. Expect much larger datasets.
2. Use the companion robot plugin `lerobot_robot_so101_paxini`, which stores tactile as float32 state features and leaves the cameras on the normal video path.

## Troubleshooting

1. `paxini` missing from camera choices: `pip show lerobot_camera_paxini`, then check the plugin import log line at startup.
2. `No registry entry for a N-point sensor`: your variant is missing from the paxini-sdk registry. Pass `sensor_part_code` explicitly, and open an issue with the part code.
3. Image is all gray (vector_rgb) or all dark (heatmap): that is zero force, which is correct at rest. Press the pad.
4. `No active Paxini modules`: the FPC cable between sensor and board is loose.
5. Everything saturates on light touch: raise `force_max_n`. Saturation means the forces exceed the configured full scale.
