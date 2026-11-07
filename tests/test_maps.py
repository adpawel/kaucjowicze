import numpy as np
import pytest
from PIL import Image

from kaucjowicze.config import CAMPUS_MAP, SimulationConfig
from kaucjowicze.factory import build_simulation
from kaucjowicze.maps import (
    BASE_COLOR,
    DORMITORY_COLOR,
    FREE_COLOR,
    OBSTACLE_COLOR,
    build_map,
    load_mask,
    map_photo,
)
from kaucjowicze.pathfinding import UNREACHABLE, distance_map


def _save_mask(path, rows):
    colors = {".": FREE_COLOR, "#": OBSTACLE_COLOR, "B": BASE_COLOR, "?": (10, 20, 30)}
    pixels = np.array([[colors[c] for c in row] for row in rows], dtype=np.uint8)
    Image.fromarray(pixels, "RGB").save(path)
    return path


def test_load_mask_reads_obstacles_and_base(tmp_path):
    grid = load_mask(_save_mask(tmp_path / "map.png", ["B.#", "..#"]))
    assert (grid.width, grid.height) == (3, 2)
    assert grid.bases == [(0, 0)]
    assert grid.obstacles.tolist() == [[False, False, True], [False, False, True]]


def test_load_mask_accepts_several_bases(tmp_path):
    grid = load_mask(_save_mask(tmp_path / "map.png", ["B.B"]))
    assert grid.bases == [(0, 0), (2, 0)]


def test_load_mask_rejects_unknown_color(tmp_path):
    with pytest.raises(ValueError, match=r"Unknown color \(10, 20, 30\) at \(1, 0\)"):
        load_mask(_save_mask(tmp_path / "map.png", ["B?."]))


def test_load_mask_requires_a_base(tmp_path):
    with pytest.raises(ValueError, match="No base"):
        load_mask(_save_mask(tmp_path / "map.png", ["..#"]))


def test_load_mask_rejects_enclosed_area(tmp_path):
    with pytest.raises(ValueError, match=r"1 cells cannot reach a base, e\.g\. \(4, 0\)"):
        load_mask(_save_mask(tmp_path / "map.png", ["B.##.", "..###"]))


def test_campus_map_has_one_base_and_every_free_cell_reaches_it():
    grid = build_map(SimulationConfig(map_name=CAMPUS_MAP))
    assert (grid.width, grid.height) == (100, 91)
    assert len(grid.bases) == 1
    assert not (distance_map(grid)[~grid.obstacles] == UNREACHABLE).any()


def test_unknown_map_name_is_rejected():
    with pytest.raises(ValueError, match="Unknown map"):
        SimulationConfig(map_name="nope")


@pytest.mark.parametrize(
    ("algorithm", "reward"), [("random", None), ("aco", "shared"), ("aco", "individual")]
)
def test_all_variants_run_on_the_campus(algorithm, reward):
    config = SimulationConfig(map_name=CAMPUS_MAP, max_steps=100)
    sim = build_simulation(algorithm, 0, reward, config)
    assert sim.grid.total_cans == 270
    assert not sim.grid.cans[sim.grid.obstacles].any()
    sim.run()
    assert sim.step_count == 100


def test_only_the_campus_has_a_photo_and_it_covers_the_whole_map():
    assert map_photo(SimulationConfig()) is None
    config = SimulationConfig(map_name=CAMPUS_MAP)
    grid = build_map(config)
    with Image.open(map_photo(config)) as photo:
        assert photo.size == (grid.width * 10, grid.height * 10)


def test_load_mask_reads_dormitories_as_obstacles(tmp_path):
    pixels = np.array([[BASE_COLOR, DORMITORY_COLOR, OBSTACLE_COLOR]], dtype=np.uint8)
    path = tmp_path / "map.png"
    Image.fromarray(pixels, "RGB").save(path)
    grid = load_mask(path)
    assert grid.obstacles.tolist() == [[False, True, True]]
    assert grid.dormitories.tolist() == [[False, True, False]]


def test_campus_clusters_start_near_dormitories():
    config = SimulationConfig(map_name=CAMPUS_MAP)
    grid = build_map(config)
    assert grid.dormitories.any()
    assert not (grid.dormitories & ~grid.obstacles).any()
