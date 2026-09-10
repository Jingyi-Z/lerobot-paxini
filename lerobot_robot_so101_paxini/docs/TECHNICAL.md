# Technical notes: lerobot_robot_so101_paxini

For maintainers. Covers the design decisions, the data contract, and what was deliberately left out. Read the user guide first for the basics.

## Context

The plugin replaces the lerobotac fork. The fork carried three core changes to lerobot: a `FeatureType.SENSOR` category with `observation.sensors.<name>` dataset keys, per-episode raw CSV hooks inside `lerobot_record.py`, and rerun blueprint panels. A plugin cannot change lerobot core, so each of those needed a decision: reproduce the effect another way, or drop it.

## Decision 1: tactile as named floats, not a sensor feature type

Stock `hw_to_dataset_features` (lerobot `utils/feature_utils.py`) has exactly two buckets. Tuple-shaped features become images or video. Everything else is concatenated into a flat `observation.state` with one name per element. There is no third category, so a plugin cannot create an `observation.sensors.paxini_fingertip` key with shape (2, 52, 3).

The plugin therefore declares one float feature per taxel axis. `flatten_names()` in `so101_paxini.py` produces the names, and its element order is exactly `np.ravel` order of the sensor array, verified by test. The contract:

```
combined    (F, P, 3)  ->  <sensor>.f<k>.p<ii>.<fx|fy|fz>
distributed (N, P, 3)  ->  <sensor>.t<n>.p<ii>.<fx|fy|fz>
resultant   (N, 3)     ->  <sensor>.t<n>.<fx|fy|fz>
both        (N, 3+3P)  ->  resultant names then distributed names per row
```

Consequences accepted: policies that consume `observation.state` see tactile automatically (this is what the sotac_vp trick removed for baselines, and a derived view can do the same here), and any downstream tooling must select by name prefix, never by position.

## Decision 2: sensors come up in `__init__`, not `connect()`

`lerobot-record` reads `robot.observation_features` (line 423 in 0.6.2) before it calls `robot.connect()` (line 484). The taxel count, and therefore the feature list, is only known after the board is opened. So `SO101Paxini.__init__` connects each sensor and starts its read thread, and `connect()` only handles the arm. The fork made the same choice for the same reason.

Cost: constructing the object touches hardware. Tests replace `PaxiniSensor` with a fake before instantiation.

## Decision 3: session-long raw CSV instead of per-episode hooks

The fork patched `lerobot_record.py` to call `start_raw_episode`, `finish_raw_episode`, and `discard_raw_episode` on the robot at episode boundaries. Stock lerobot has no such calls, and a robot object is never told where episodes start.

Replacement: `start_raw_session()` opens one CSV per finger when continuous reading starts, under `sensors/<name>/session_<stamp>/`, same column layout as the vendor files, every row stamped with epoch nanoseconds. Episode cutting moves downstream, using the dataset's own frame timestamps. This is the same shape as the existing sotac pipeline, where `apply_trim.py` already cuts sidecar CSVs by `calibrated_timestamp_ns`. The per-episode methods remain in the driver for callers that do have episode boundaries.

## Failure semantics

`get_observation()` never raises on a transient sensor failure. A failed or empty read reuses the last good reading, and only a first-ever failure with no history falls back to zeros. Rationale, inherited from the fork: a zero frame is indistinguishable from a real contact loss and corrupts event detection downstream, while a repeated frame at 30 Hz is a bounded, visible artifact. A shape mismatch between the sensor read and the declared names does raise, because it means the feature schema no longer matches the data and every subsequent frame would be silently misaligned.

## What was dropped and why

1. Rerun blueprint panels. They required lerobot core changes to the visualization utils. `display_rerun` still logs force arrows into an existing rerun session, nothing more.
2. The MLX90393 sensor type. Out of scope for this package, the driver stays in the fork until it earns its own plugin.
3. `FeatureType.SENSOR`. See decision 1.

## Testing strategy

Everything except the serial protocol runs without hardware. `test_flatten.py` pins the name-to-ravel contract and plugin registration. The feature-layout test constructs the robot with a fake sensor and asserts the 318-name state vector and the one-obs-key-per-name contract that `lerobot-record` relies on. The serial protocol itself is covered by paxini-sdk's own test suite against recorded byte dumps.

## Known limitations

1. The dataset tactile stream is sampled at recording fps. At 30 fps you store 30 Hz tactile even though the board pushes 91 Hz. The raw sidecar exists for exactly this reason.
2. Finger order inside `module_indices` is a config convention, nothing in the data self-describes which physical finger is f0.
3. `pyproject.toml` declares no dependencies on purpose, matching the community plugin convention, so installation never re-resolves lerobot or numpy. paxini-sdk is an optional extra pinned to git until it is on PyPI.
