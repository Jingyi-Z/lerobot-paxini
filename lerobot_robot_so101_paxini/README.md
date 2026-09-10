# lerobot_robot_so101_paxini

SO-101 follower with Paxini PX-6AX GEN3 tactile fingertips, packaged as a LeRobot robot plugin. Registers the `so101_paxini` robot type on stock lerobot (0.6.2 or later) without patching lerobot itself.

Driver: [paxini-sdk](https://github.com/Jingyi-Z/paxini-sdk). Ported from the `hall-sensor` branch of [lerobotac](https://github.com/Jingyi-Z/lerobotac).

## Install

```bash
pip install lerobot
pip install paxini-sdk
pip install -e lerobot_robot_so101_paxini
```

## Record

```bash
lerobot-record \
  --robot.type=so101_paxini \
  --robot.port=/dev/ttyACM0 \
  --robot.id=follower \
  --robot.cameras='{top: {type: opencv, index_or_path: 2, width: 640, height: 480, fps: 30}, wrist: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30}}' \
  --robot.sensors='{paxini_fingertip: {port: /dev/ttyUSB0, module_indices: [10, 18], output_format: combined, record_raw_csv: true, raw_csv_dir: /data/paxini_raw}}' \
  --teleop.type=so101_leader --teleop.port=/dev/ttyACM1 --teleop.id=leader \
  --dataset.repo_id=Jingyi-Z/sotac_v2 --dataset.fps=30 --dataset.num_episodes=10 \
  --dataset.single_task="Pick up the red foam ball and place it into the container" \
  --display_data=false
```

## Where the data lands

Stock lerobot has no sensor feature type. Non-image robot features are concatenated into `observation.state` with one name per element, so a `(2, 52, 3)` fingertip sample becomes 312 named floats after the 6 joint positions:

```
observation.state  float32 [318]
  names: shoulder_pan.pos, ..., gripper.pos,
         paxini_fingertip.f0.p00.fx, ..., paxini_fingertip.f1.p51.fz
```

Cameras stay on the normal video path. Select the tactile block downstream by name prefix, not by position.

## Raw 91 Hz sidecar

With `record_raw_csv: true`, one CSV per finger is written for the whole session under `<raw_csv_dir>/sensors/<sensor_name>/session_<stamp>/`, same column layout as the company files, rows stamped with epoch nanoseconds. Cut per episode afterwards using the dataset frame timestamps. Stock `lerobot-record` cannot signal episode boundaries to a robot, so the per-episode sidecar from the fork is not available here.

## Not carried over from the fork

- `FeatureType.SENSOR` and `observation.sensors.<name>` keys (needed a lerobot core change).
- Per-episode raw CSV start/finish/discard hooks in `lerobot-record`.
- Per-sensor rerun blueprint panels. `display_rerun: true` still logs force arrows if a rerun session is active.

## Test

```bash
pip install -e ".[dev]" && pytest
```
