import numpy as np
import pytest

from kaucjowicze.cans import scatter_cans
from kaucjowicze.config import SimulationConfig
from kaucjowicze.maps import build_test_map


def _generate(seed: int):
    config = SimulationConfig(seed=seed)
    grid = build_test_map(config)
    scatter_cans(grid, config, np.random.default_rng(seed))
    return config, grid


def test_total_can_count():
    config, grid = _generate(seed=1)
    expected = config.n_clusters * config.cans_per_cluster + config.n_background_cans
    assert grid.total_cans == expected


def test_no_cans_on_obstacles():
    _, grid = _generate(seed=2)
    assert grid.cans[grid.obstacles].sum() == 0


def test_same_seed_gives_same_map():
    _, a = _generate(seed=42)
    _, b = _generate(seed=42)
    np.testing.assert_array_equal(a.cans, b.cans)


def test_test_map_has_reachable_base():
    _, grid = _generate(seed=3)
    assert len(grid.bases) == 1
    assert grid.is_free(grid.bases[0])


def test_invalid_config_rejected():
    with pytest.raises(ValueError):
        SimulationConfig(bag_capacity=0)
