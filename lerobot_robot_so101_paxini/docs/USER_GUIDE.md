# User guide: lerobot_robot_so101_paxini

SO-101 follower arm with Paxini PX-6AX GEN3 tactile fingertips, packaged as a LeRobot plugin. Installing it adds a `so101_paxini` robot type to stock lerobot. Recording, training, and rollout all run in one environment with no fork.

## What you need

1. An SO-101 follower arm (and a leader arm if you record by teleoperation).
2. One or two Paxini GEN3 fingertip sensors on the gripper.
3. A Paxini communication board. The High-Speed Communication Board pushes about 91 Hz and handles both fingertips on one port. The Serial Converter Board is request and response, one sensor per port.
4. Python 3.10 or later, lerobot 0.6.2 or later.

## Install

```bash
pip install lerobot
pip install paxini-sdk
pip install lerobot_robot_so101_paxini
```

Verify the plugin is discovered:

```bash
python -c "from lerobot.utils.import_utils import register_third_party_plugins as r; r(); \
from lerobot.robots.config import RobotConfig; print('so101_paxini' in RobotConfig.get_known_choices())"
```

Expected output: `True`. Takes under a minute.

## Record an episode

```bash
lerobot-record \
  --robot.type=so101_paxini \
  --robot.port=/dev/ttyACM0 \
  --robot.id=follower \
  --robot.cameras='{top: {type: opencv, index_or_path: 2, width: 640, height: 480, fps: 30}, wrist: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30}}' \
  --robot.sensors='{paxini_fingertip: {port: /dev/ttyUSB0, module_indices: [14, 18], output_format: combined, record_raw_csv: true, raw_csv_dir: /data/paxini_raw}}' \
  --teleop.type=so101_leader --teleop.port=/dev/ttyACM1 --teleop.id=leader \
  --dataset.repo_id=<user>/<dataset> --dataset.fps=30 --dataset.num_episodes=10 \
  --dataset.single_task="Pick up the red foam ball and place it into the container" \
  --display_data=false
```

Everything except `--robot.type` and `--robot.sensors` is a normal SO-101 recording command.

## Where the tactile data lands

Stock lerobot concatenates every non-image robot feature into `observation.state`. With two 52-taxel fingertips the state vector is 318 floats: 6 joint positions first, then one named float per taxel axis.

```
observation.state  float32 [318]
  names: shoulder_pan.pos, ..., gripper.pos,
         paxini_fingertip.f0.p00.fx, ..., paxini_fingertip.f1.p51.fz
```

Select the tactile block downstream by name prefix, never by column position. Cameras stay on the normal video path, so datasets remain small.

## The force sidecar

The dataset stream is sampled at your recording fps, typically 30 Hz. With `record_raw_csv: true` the plugin also writes one CSV per finger for the whole session under `<raw_csv_dir>/sensors/<sensor_name>/session_<stamp>/`, rows stamped with epoch nanoseconds at the full board rate. Cut it per episode afterwards using the dataset frame timestamps.

## Sensor configuration reference

| Field | Default | Meaning |
|---|---|---|
| `port` | /dev/ttyUSB0 | Serial port of the communication board |
| `board_type` | high_speed | `high_speed` or `serial` |
| `module_indices` | none | High-speed combined mode, list of finger slots in order |
| `module_index` | none | High-speed single module mode |
| `sensor_part_code` | none | Serial board only, the vendor part code |
| `output_format` | combined | `combined`, `distributed`, `resultant`, or `both` |
| `auto_calibrate` | true | Zero the sensor at connect, pads must be contact free |
| `record_raw_csv` | false | Session-long raw sidecar on or off |
| `raw_csv_dir` | none | Where the sidecar lands |

## Troubleshooting

1. `so101_paxini` missing from robot choices: the package is not installed in the active environment. `pip show lerobot_robot_so101_paxini` to confirm.
2. Sensor initializes but every tactile value is 0: pads were touching something during auto calibration. Reconnect with the gripper open and contact free.
3. Occasional warning about reusing the last reading: a transient serial hiccup. One warning per event is normal. Constant warnings mean a cable or port problem.
4. Wrong finger order in the data: `module_indices` list order defines f0 and f1. Press one fingertip and check which block moves.
5. Camera indices: capture nodes are usually even numbers. Check with `v4l2-ctl --list-devices`.
