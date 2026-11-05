import numpy as np
import pytest

from kaucjowicze.agent import AgentState
from kaucjowicze.config import SimulationConfig
from kaucjowicze.grid import Grid
from kaucjowicze.policies import RandomWalkPolicy
from kaucjowicze.simulation import Simulation
from kaucjowicze.view import (
    BACKGROUND_COLOR,
    BASE_COLOR,
    CAN_SATURATION,
    OBSTACLE_COLOR,
    SPEEDS,
    Playback,
    agent_color,
    can_color,
    compose_map_image,
    hud_lines,
)


def _pixel(image: np.ndarray, x: int, y: int) -> tuple[int, int, int]:
    return tuple(int(channel) for channel in image[y, x])


def _small_sim(n_agents: int = 3) -> Simulation:
    grid = Grid(6, 4)
    grid.add_base((0, 0))
    grid.add_can((3, 2), 5)
    config = SimulationConfig(width=6, height=4, n_agents=n_agents, seed=0)
    policy = RandomWalkPolicy(config.direction_persistence)
    return Simulation(config, grid, policy, np.random.default_rng(0))


def test_can_color_changes_with_count():
    colors = [can_color(count) for count in range(1, CAN_SATURATION + 1)]
    assert len(set(colors)) == CAN_SATURATION


def test_can_color_saturates():
    assert can_color(CAN_SATURATION + 25) == can_color(CAN_SATURATION)


def test_states_have_distinct_colors():
    assert agent_color(AgentState.SEARCHING) != agent_color(AgentState.CARRYING)


def test_map_image_shows_every_layer():
    grid = Grid(5, 3)
    grid.add_obstacle(1, 0, 1, 1)
    grid.add_base((2, 1))
    grid.add_can((4, 2), 3)

    image = compose_map_image(grid)

    assert image.shape == (3, 5, 3)
    assert image.dtype == np.uint8
    assert _pixel(image, 0, 0) == BACKGROUND_COLOR
    assert _pixel(image, 1, 0) == OBSTACLE_COLOR
    assert _pixel(image, 2, 1) == BASE_COLOR
    assert _pixel(image, 4, 2) == can_color(3)


def test_map_image_does_not_change_the_grid():
    grid = Grid(3, 3)
    grid.add_can((1, 1), 2)
    compose_map_image(grid)
    assert grid.cans[1, 1] == 2


def test_pheromone_is_visible_only_when_enabled():
    grid = Grid(4, 1)
    pheromone = np.array([[0.0, 0.5, 1.0, 0.0]])

    hidden = compose_map_image(grid, pheromone, show_pheromone=False)
    shown = compose_map_image(grid, pheromone, show_pheromone=True)

    assert _pixel(hidden, 2, 0) == BACKGROUND_COLOR
    assert _pixel(shown, 0, 0) == BACKGROUND_COLOR
    assert _pixel(shown, 2, 0) != BACKGROUND_COLOR
    assert _pixel(shown, 1, 0) not in (BACKGROUND_COLOR, _pixel(shown, 2, 0))


def test_pheromone_lies_under_obstacles_and_cans():
    grid = Grid(2, 1)
    grid.add_obstacle(0, 0, 1, 1)
    grid.add_can((1, 0))
    image = compose_map_image(grid, np.ones((1, 2)), show_pheromone=True)
    assert _pixel(image, 0, 0) == OBSTACLE_COLOR
    assert _pixel(image, 1, 0) == can_color(1)


def test_zero_pheromone_is_drawn_as_background():
    grid = Grid(2, 2)
    with np.errstate(all="raise"):
        image = compose_map_image(grid, np.zeros((2, 2)), show_pheromone=True)
    assert _pixel(image, 1, 1) == BACKGROUND_COLOR


def test_paused_playback_gives_no_steps_and_keeps_no_backlog():
    playback = Playback()
    playback.toggle_pause()
    assert playback.steps_due(10.0) == 0
    playback.toggle_pause()
    assert playback.steps_due(0.0) == 0


def test_steps_due_follows_speed():
    playback = Playback()
    assert playback.steps_due(1.0) == playback.speed
    playback.faster()
    assert playback.steps_due(1.0) == playback.speed


def test_steps_due_accumulates_fractions():
    playback = Playback(speed_index=SPEEDS.index(10))
    total = sum(playback.steps_due(0.01) for _ in range(100))
    assert total == pytest.approx(10, abs=1)


def test_speed_stops_at_both_ends():
    playback = Playback()
    for _ in SPEEDS:
        playback.faster()
    assert playback.speed == SPEEDS[-1]
    for _ in SPEEDS:
        playback.slower()
    assert playback.speed == SPEEDS[0]


def test_hud_shows_progress_variant_and_seed():
    sim = _small_sim()
    sim.collected = 2
    sim.step_count = 7
    sim.agents[0].state = AgentState.CARRYING

    text = "\n".join(hud_lines(sim, "random", 42, Playback()))

    assert "random" in text
    assert "seed 42" in text
    assert f"step 7/{sim.config.max_steps}" in text
    assert "cans 2/5" in text
    assert "searching 2" in text
    assert "carrying 1" in text


def test_hud_shows_pause_and_finish():
    sim = _small_sim()
    playback = Playback()
    assert "PAUSED" not in "\n".join(hud_lines(sim, "random", 0, playback))
    playback.toggle_pause()
    assert "PAUSED" in "\n".join(hud_lines(sim, "random", 0, playback))
    sim.step_count = sim.config.max_steps
    assert "FINISHED" in "\n".join(hud_lines(sim, "random", 0, playback))


def test_hud_shows_pheromone_status():
    sim = _small_sim()
    playback = Playback()
    assert "pheromone n/a" in "\n".join(hud_lines(sim, "random", 0, playback))
    sim.pheromone = np.zeros((4, 6))
    assert "pheromone on" in "\n".join(hud_lines(sim, "random", 0, playback))
    playback.show_pheromone = False
    assert "pheromone off" in "\n".join(hud_lines(sim, "random", 0, playback))
