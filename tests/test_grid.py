import pytest

from kaucjowicze.grid import Grid


def test_obstacle_blocks_cell():
    grid = Grid(10, 10)
    grid.add_obstacle(2, 3, 2, 2)
    assert not grid.is_free((2, 3))
    assert not grid.is_free((3, 4))
    assert grid.is_free((4, 3))


def test_obstacle_outside_map_is_ignored():
    grid = Grid(10, 10)
    grid.add_obstacle(-5, 0, 2, 2)
    grid.add_obstacle(0, 12, 3, 3)
    assert grid.obstacles.sum() == 0


def test_obstacle_partially_outside_map_is_clipped():
    grid = Grid(10, 10)
    grid.add_obstacle(-1, -1, 3, 3)
    grid.add_obstacle(8, 8, 5, 5)
    assert grid.obstacles.sum() == 4 + 4


def test_take_can_out_of_bounds_does_not_wrap():
    grid = Grid(5, 5)
    grid.add_can((4, 0))
    assert not grid.take_can((-1, 0))
    assert not grid.take_can((5, 0))
    assert grid.total_cans == 1


def test_out_of_bounds_is_not_free():
    grid = Grid(5, 5)
    assert not grid.is_free((-1, 0))
    assert not grid.is_free((5, 0))
    assert not grid.is_free((0, 5))


def test_add_and_take_cans():
    grid = Grid(5, 5)
    grid.add_can((1, 1), 2)
    assert grid.total_cans == 2
    assert grid.take_can((1, 1))
    assert grid.take_can((1, 1))
    assert not grid.take_can((1, 1))
    assert grid.total_cans == 0


def test_cannot_place_on_obstacle():
    grid = Grid(5, 5)
    grid.add_obstacle(0, 0, 1, 1)
    with pytest.raises(ValueError):
        grid.add_can((0, 0))
    with pytest.raises(ValueError):
        grid.add_base((0, 0))


def test_render_ascii_shape():
    grid = Grid(4, 3)
    grid.add_base((0, 0))
    grid.add_obstacle(3, 2, 1, 1)
    lines = grid.render_ascii().splitlines()
    assert len(lines) == 3
    assert all(len(line) == 4 for line in lines)
    assert lines[0][0] == "B"
    assert lines[2][3] == "#"
