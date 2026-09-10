"""Hardware-free tests: naming, ordering, and the obs -> state contract."""

import numpy as np

from lerobot_robot_so101_paxini.so101_paxini import flatten_names


def test_combined_names_match_ravel_order():
    names = flatten_names("tac", (2, 52, 3), "combined")
    assert len(names) == 312
    assert names[0] == "tac.f0.p00.fx"
    assert names[2] == "tac.f0.p00.fz"
    assert names[3] == "tac.f0.p01.fx"
    assert names[156] == "tac.f1.p00.fx"
    assert names[-1] == "tac.f1.p51.fz"
    # index arithmetic agrees with np.ravel of a (2, 52, 3) array
    a = np.arange(2 * 52 * 3).reshape(2, 52, 3)
    k, i, c = 1, 17, 2
    assert names[a[k, i, c]] == f"tac.f{k}.p{i:02d}.fz"


def test_other_formats_sizes():
    assert len(flatten_names("t", (10, 3), "resultant")) == 30
    assert len(flatten_names("t", (10, 52, 3), "distributed")) == 1560
    assert len(flatten_names("t", (10, 3 + 52 * 3), "both")) == 1590


def test_plugin_registers_robot_type():
    import lerobot_robot_so101_paxini  # noqa: F401
    from lerobot.robots.config import RobotConfig

    assert "so101_paxini" in RobotConfig.get_known_choices()
