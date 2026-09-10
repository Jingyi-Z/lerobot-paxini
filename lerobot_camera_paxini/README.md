# lerobot_camera_paxini

[Paxini](https://www.paxini.com/) PX-6AX GEN3 tactile sensors as LeRobot cameras. Every GEN3 variant works, from the 9-taxel fingernail to the 239-taxel palm pad: the taxel count is read from the hardware and the layout comes from the coordinate registry bundled in [paxini-sdk](https://github.com/Jingyi-Z/paxini-sdk). Registers the `paxini` camera type on stock lerobot; no lerobot changes needed.

## Install

```bash
pip install lerobot
pip install paxini-sdk
pip install lerobot_camera_paxini
```

## Use

```bash
lerobot-record \
  --robot.type=so101_follower --robot.port=/dev/ttyACM0 --robot.id=follower \
  --robot.cameras='{
    top: {type: opencv, index_or_path: 2, width: 640, height: 480, fps: 30},
    tactile: {type: paxini, port: /dev/ttyUSB0, width: 240, height: 320, fps: 30}
  }' \
  ...
```

Both communication boards are supported: the High-Speed Communication Board (`board_type: high_speed`, default, auto-push ~91 Hz, pick a slot with `module_index`) and the Serial Converter Board (`board_type: serial`, needs `sensor_part_code` because that board cannot report its sensor).

## Rendering

- `render: vector_rgb` (default): per-taxel (Fx, Fy, Fz) into R, G, B, signed forces centered at 128. Policies get the full force vector as an ordinary image.
- `render: heatmap`: force magnitude on the vendor-app green-to-red ramp. For demos and debugging.

`force_max_n` sets full-scale (default 5 N), `splat_sigma_px` the Gaussian splat width.

If exact per-taxel values matter downstream, record with `--dataset.video=false`: the default video path is lossy and halves chroma resolution. For tactile as float state features instead of images, see the companion robot plugin [lerobot_robot_so101_paxini](https://github.com/Jingyi-Z/lerobot-paxini).

## Test without hardware

```bash
pip install -e ".[dev]" && pytest
```
