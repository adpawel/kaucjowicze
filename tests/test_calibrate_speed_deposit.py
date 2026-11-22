import importlib.util
from pathlib import Path

import pytest

from kaucjowicze.config import SimulationConfig

_PATH = Path(__file__).resolve().parents[1] / "tools" / "calibrate_speed_deposit.py"
_SPEC = importlib.util.spec_from_file_location("calibrate_speed_deposit", _PATH)
tool = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(tool)

SMALL = SimulationConfig(
    width=30, height=20, n_clusters=2, cans_per_cluster=8, n_agents=4, max_steps=200
)


def test_calibrated_speed_trail_matches_the_source_trail():
    q_s, mean, target = tool.calibrate(SMALL, seeds=[0, 1], tolerance=0.05)
    assert q_s > 0
    assert mean == pytest.approx(target, rel=0.05)


def test_mean_trail_counts_cells_without_trail_too():
    mean = tool.mean_trail(SMALL, seeds=[0])
    assert 0 < mean


def test_calibration_that_cannot_settle_is_reported():
    with pytest.raises(RuntimeError, match="did not settle"):
        tool.calibrate(SMALL, seeds=[0], tolerance=0.0, max_rounds=1)
