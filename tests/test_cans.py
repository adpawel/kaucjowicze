import numpy as np
import pytest

from kaucjowicze.cans import _cluster_candidates, scatter_cans
from kaucjowicze.config import SimulationConfig
from kaucjowicze.grid import Grid
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


def _grid_with_dormitory() -> Grid:
    grid = Grid(60, 40)
    grid.add_obstacle(5, 5, 4, 4)
    grid.dormitories[5:9, 5:9] = True
    return grid


def test_cluster_centres_lie_close_to_a_dormitory():
    grid = _grid_with_dormitory()
    config = SimulationConfig(cluster_dorm_distance=4)
    candidates = _cluster_candidates(grid, config, grid.free_cells())
    assert len(candidates) > 0
    assert candidates[:, 0].min() >= 1 and candidates[:, 0].max() <= 12
    assert candidates[:, 1].min() >= 1 and candidates[:, 1].max() <= 12
    assert not grid.obstacles[candidates[:, 1], candidates[:, 0]].any()


def test_without_dormitories_any_free_cell_can_be_a_centre():
    grid = Grid(10, 10)
    grid.add_obstacle(2, 2, 2, 2)
    free = grid.free_cells()
    assert (_cluster_candidates(grid, SimulationConfig(), free) == free).all()


def test_cans_gather_around_the_dormitory():
    grid = _grid_with_dormitory()
    config = SimulationConfig(
        n_clusters=3, cans_per_cluster=30, cluster_spread=1.0, n_background_cans=0
    )
    scatter_cans(grid, config, np.random.default_rng(0))
    assert grid.total_cans == 90
    assert grid.cans[:, 25:].sum() == 0
    assert not grid.cans[grid.obstacles].any()
