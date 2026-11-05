"""What the window shows and how fast it plays, without any dependency on pygame.

Everything here only reads the simulation, so it runs and is tested without a display.
"""

from dataclasses import dataclass

import numpy as np

from kaucjowicze.agent import AgentState
from kaucjowicze.grid import Grid
from kaucjowicze.simulation import Simulation

Color = tuple[int, int, int]

BACKGROUND_COLOR: Color = (245, 245, 240)
OBSTACLE_COLOR: Color = (95, 95, 105)
BASE_COLOR: Color = (20, 20, 20)
CAN_FEW_COLOR: Color = (250, 200, 100)
CAN_MANY_COLOR: Color = (165, 30, 30)
PHEROMONE_COLOR: Color = (95, 200, 120)

CAN_SATURATION = 10  # from this many cans in a cell the color stops changing

SPEEDS = (1, 2, 5, 10, 20, 50, 100, 200, 500)  # simulation steps per second
DEFAULT_SPEED = 20

_AGENT_COLORS: dict[AgentState, Color] = {
    AgentState.SEARCHING: (30, 90, 220),
    AgentState.CARRYING: (200, 30, 180),
}


def agent_color(state: AgentState) -> Color:
    return _AGENT_COLORS[state]


def _can_colors(counts: np.ndarray) -> np.ndarray:
    """RGB for positive can counts, from CAN_FEW_COLOR to CAN_MANY_COLOR."""
    level = (np.minimum(counts, CAN_SATURATION) - 1) / (CAN_SATURATION - 1)
    few, many = np.array(CAN_FEW_COLOR), np.array(CAN_MANY_COLOR)
    return few + (many - few) * level[..., np.newaxis]


def can_color(count: int) -> Color:
    rgb = _can_colors(np.array(count)).astype(np.uint8)
    return tuple(int(channel) for channel in rgb)


def compose_map_image(
    grid: Grid, pheromone: np.ndarray | None = None, show_pheromone: bool = False
) -> np.ndarray:
    """RGB image of shape (height, width, 3), one pixel per cell.

    Layers from the bottom: background, pheromone, obstacles, cans, bases.
    """
    image = np.empty((grid.height, grid.width, 3), dtype=np.uint8)
    image[:] = BACKGROUND_COLOR

    if show_pheromone and pheromone is not None and pheromone.max() > 0:
        strength = (pheromone / pheromone.max())[..., np.newaxis]
        background, heat = np.array(BACKGROUND_COLOR), np.array(PHEROMONE_COLOR)
        image[:] = background + (heat - background) * strength

    image[grid.obstacles] = OBSTACLE_COLOR
    has_cans = grid.cans > 0
    image[has_cans] = _can_colors(grid.cans[has_cans])
    for x, y in grid.bases:
        image[y, x] = BASE_COLOR
    return image


@dataclass
class Playback:
    """Viewer settings: they survive a restart and never affect the simulation itself."""

    paused: bool = False
    speed_index: int = SPEEDS.index(DEFAULT_SPEED)
    show_pheromone: bool = True
    _backlog: float = 0.0  # fraction of a step carried over to the next frame

    @property
    def speed(self) -> int:
        return SPEEDS[self.speed_index]

    def toggle_pause(self) -> None:
        self.paused = not self.paused

    def toggle_pheromone(self) -> None:
        self.show_pheromone = not self.show_pheromone

    def faster(self) -> None:
        self.speed_index = min(self.speed_index + 1, len(SPEEDS) - 1)

    def slower(self) -> None:
        self.speed_index = max(self.speed_index - 1, 0)

    def steps_due(self, dt: float) -> int:
        """Number of simulation steps to run after `dt` seconds of real time."""
        if self.paused:
            return 0
        self._backlog += dt * self.speed
        steps = int(self._backlog)
        self._backlog -= steps
        return steps


def _format_hud(
    variant: str,
    seed: int,
    progress: str,
    agents: str,
    speed: int,
    pheromone: str,
    flag: str | None,
) -> list[str]:
    status = f"speed {speed} steps/s | pheromone {pheromone}"
    if flag is not None:
        status += f" | {flag}"
    return [
        f"{variant} | seed {seed} | {progress} | {agents}",
        status,
        "space: pause | +/-: speed | R: restart | P: pheromone | Esc: quit",
    ]


def hud_lines(sim: Simulation, variant: str, seed: int, playback: Playback) -> list[str]:
    """Text of the status bar, one string per line."""
    carrying = sum(agent.state is AgentState.CARRYING for agent in sim.agents)
    searching = len(sim.agents) - carrying

    if sim.pheromone is None:
        pheromone = "n/a"
    else:
        pheromone = "on" if playback.show_pheromone else "off"

    flag = None
    if sim.is_finished:
        flag = "FINISHED"
    elif playback.paused:
        flag = "PAUSED"

    return _format_hud(
        variant,
        seed,
        f"step {sim.step_count}/{sim.config.max_steps} | cans {sim.collected}/{sim.initial_cans}",
        f"searching {searching} | carrying {carrying}",
        playback.speed,
        pheromone,
        flag,
    )


def longest_hud_lines(sim: Simulation, variant: str, seed: int) -> list[str]:
    """The status bar with the most digits it can reach in this run, to size the window."""
    n_agents = len(sim.agents)
    return _format_hud(
        variant,
        seed,
        f"step {sim.config.max_steps}/{sim.config.max_steps} "
        f"| cans {sim.initial_cans}/{sim.initial_cans}",
        f"searching {n_agents} | carrying {n_agents}",
        max(SPEEDS),
        "n/a",
        "FINISHED",
    )
