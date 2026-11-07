import numpy as np

from kaucjowicze.grid import Grid
from kaucjowicze.pathfinding import (
    NEIGHBOURS,
    distance_map,
    first_step_to_nearest_can,
    seen_cans,
    step_closer,
    visible_cans,
)


def test_neighbours_are_eight_directions():
    assert len(NEIGHBOURS) == 8
    assert (0, 0) not in NEIGHBOURS
    assert all(max(abs(dx), abs(dy)) == 1 for dx, dy in NEIGHBOURS)


def test_distance_map_open_grid_is_chebyshev():
    grid = Grid(7, 5)
    grid.add_base((3, 2))
    dist = distance_map(grid)
    assert dist.shape == (5, 7)
    assert dist[2, 3] == 0
    assert dist[2, 4] == 1
    assert dist[3, 4] == 1  # diagonal
    assert dist[0, 0] == 3


def test_distance_map_detours_around_wall():
    grid = Grid(5, 5)
    grid.add_obstacle(1, 0, 1, 4)  # wall at x=1, gap only at y=4
    grid.add_base((0, 0))
    dist = distance_map(grid)
    assert dist[0, 1] == -1  # obstacle
    # (0,0) -> (0,3) -> (1,4) through the gap -> (2,3) -> (2,0)
    assert dist[4, 1] == 4
    assert dist[0, 2] == 8


def test_distance_map_marks_unreachable_cells():
    grid = Grid(5, 3)
    grid.add_obstacle(2, 0, 1, 3)  # full wall
    grid.add_base((0, 1))
    dist = distance_map(grid)
    assert dist[1, 4] == -1
    assert dist[1, 1] == 1


def test_distance_map_with_multiple_bases_uses_nearest():
    grid = Grid(9, 1)
    grid.add_base((0, 0))
    grid.add_base((8, 0))
    dist = distance_map(grid)
    np.testing.assert_array_equal(dist[0], [0, 1, 2, 3, 4, 3, 2, 1, 0])


def test_distance_map_from_chosen_sources_ignores_the_bases():
    grid = Grid(10, 1)
    grid.add_base((0, 0))
    dist = distance_map(grid, [(6, 0)])
    assert dist[0].tolist() == [6, 5, 4, 3, 2, 1, 0, 1, 2, 3]


def test_step_closer_decreases_distance():
    grid = Grid(10, 10)
    grid.add_obstacle(3, 0, 1, 8)
    grid.add_base((0, 0))
    dist = distance_map(grid)
    pos = (6, 0)
    steps = 0
    while pos != (0, 0):
        nxt = step_closer(grid, dist, pos)
        assert grid.is_free(nxt)
        assert dist[nxt[1], nxt[0]] == dist[pos[1], pos[0]] - 1
        pos = nxt
        steps += 1
    assert steps == dist[0, 6]


def test_nearest_can_on_current_cell():
    grid = Grid(5, 5)
    grid.add_can((2, 2))
    assert first_step_to_nearest_can(grid, (2, 2), radius=2) == (2, 2)


def test_nearest_can_within_radius_gives_first_step():
    grid = Grid(7, 7)
    grid.add_can((5, 3))
    assert first_step_to_nearest_can(grid, (3, 3), radius=2) == (4, 3)


def test_can_beyond_radius_is_not_seen():
    grid = Grid(7, 7)
    grid.add_can((6, 3))
    assert first_step_to_nearest_can(grid, (3, 3), radius=2) is None


def test_nearest_can_step_avoids_obstacle():
    grid = Grid(7, 7)
    grid.add_obstacle(4, 2, 1, 3)  # wall between agent and can
    grid.add_can((5, 3))
    step = first_step_to_nearest_can(grid, (3, 3), radius=2)
    assert step is not None
    assert grid.is_free(step)


def test_can_hidden_behind_wall_inside_window_is_not_seen():
    grid = Grid(7, 7)
    grid.add_obstacle(4, 0, 1, 7)  # full wall, can unreachable within window
    grid.add_can((5, 3))
    assert first_step_to_nearest_can(grid, (3, 3), radius=2) is None


def test_seen_cans_does_not_count_cans_behind_a_wall():
    grid = Grid(9, 7)
    grid.add_can((3, 3), 2)  # under the agent
    grid.add_can((4, 3))  # in the open
    grid.add_obstacle(5, 0, 1, 7)
    grid.add_can((6, 3), 5)  # within the radius, but no path inside the window leads there
    assert seen_cans(grid, (3, 3), radius=3) == 3
    assert visible_cans(grid, (3, 3), radius=3) == 8


def test_seen_cans_without_a_can_in_the_window_is_zero():
    grid = Grid(9, 7)
    grid.add_can((8, 6))
    assert seen_cans(grid, (1, 1), radius=2) == 0
