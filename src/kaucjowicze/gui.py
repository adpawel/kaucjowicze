"""Pygame window. It only reads the simulation and is the only module importing pygame."""

from collections.abc import Callable
from enum import Enum, auto

import pygame

from kaucjowicze.grid import Grid
from kaucjowicze.simulation import Simulation
from kaucjowicze.view import (
    BACKGROUND_COLOR,
    BASE_COLOR,
    Playback,
    agent_color,
    compose_map_image,
    hud_lines,
)

CELL_SIZE = 10  # pixels per grid cell
HUD_HEIGHT = 66
HUD_LINE_HEIGHT = 20
HUD_PADDING = 4
FONT_SIZE = 22
HUD_TEXT_COLOR = (30, 30, 30)
FPS = 60
MAX_FRAME_TIME = 0.25  # seconds; a stalled frame (e.g. a dragged window) must not cause a jump

_PLUS_KEYS = (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS)
_MINUS_KEYS = (pygame.K_MINUS, pygame.K_KP_MINUS)


class Action(Enum):
    NONE = auto()
    RESTART = auto()
    QUIT = auto()


def apply_key(key: int, playback: Playback) -> Action:
    """Update viewer settings for a pressed key; return what the main loop has to do."""
    if key == pygame.K_SPACE:
        playback.toggle_pause()
    elif key in _PLUS_KEYS:
        playback.faster()
    elif key in _MINUS_KEYS:
        playback.slower()
    elif key == pygame.K_p:
        playback.toggle_pheromone()
    elif key == pygame.K_r:
        return Action.RESTART
    elif key == pygame.K_ESCAPE:
        return Action.QUIT
    return Action.NONE


def window_size(grid: Grid, cell_size: int = CELL_SIZE) -> tuple[int, int]:
    return grid.width * cell_size, grid.height * cell_size + HUD_HEIGHT


def draw(
    screen: pygame.Surface,
    font: pygame.font.Font,
    sim: Simulation,
    playback: Playback,
    variant: str,
    seed: int,
    cell_size: int = CELL_SIZE,
) -> None:
    grid = sim.grid
    map_size = (grid.width * cell_size, grid.height * cell_size)
    image = compose_map_image(grid, sim.pheromone, playback.show_pheromone)
    # surfarray indexes pixels as [x, y], the grid as [y, x]
    surface = pygame.surfarray.make_surface(image.swapaxes(0, 1))

    screen.fill(BACKGROUND_COLOR)
    screen.blit(pygame.transform.scale(surface, map_size), (0, 0))

    # A single cell is easy to miss, so the base gets a frame around it
    for x, y in grid.bases:
        frame = pygame.Rect((x - 1) * cell_size, (y - 1) * cell_size, 3 * cell_size, 3 * cell_size)
        pygame.draw.rect(screen, BASE_COLOR, frame, width=2)

    for agent in sim.agents:
        center = (
            agent.pos[0] * cell_size + cell_size // 2,
            agent.pos[1] * cell_size + cell_size // 2,
        )
        pygame.draw.circle(screen, agent_color(agent.state), center, max(cell_size // 2, 1))

    for i, line in enumerate(hud_lines(sim, variant, seed, playback)):
        text = font.render(line, True, HUD_TEXT_COLOR)
        screen.blit(text, (HUD_PADDING, map_size[1] + HUD_PADDING + i * HUD_LINE_HEIGHT))
    pygame.display.flip()


def run_gui(
    make_sim: Callable[[], Simulation],
    variant: str,
    seed: int,
    cell_size: int = CELL_SIZE,
) -> None:
    """Open the window and play the simulation until it is closed.

    `make_sim` must give an identical simulation on every call: restart relies on it.
    """
    sim = make_sim()
    playback = Playback()

    pygame.init()
    try:
        screen = pygame.display.set_mode(window_size(sim.grid, cell_size))
        pygame.display.set_caption(f"Kaucjowicze: {variant}")
        font = pygame.font.Font(None, FONT_SIZE)
        clock = pygame.time.Clock()

        while True:
            for event in pygame.event.get():
                action = Action.NONE
                if event.type == pygame.QUIT:
                    action = Action.QUIT
                elif event.type == pygame.KEYDOWN:
                    action = apply_key(event.key, playback)

                if action is Action.QUIT:
                    return
                if action is Action.RESTART:
                    sim = make_sim()

            dt = min(clock.tick(FPS) / 1000, MAX_FRAME_TIME)
            for _ in range(playback.steps_due(dt)):
                if sim.is_finished:
                    break
                sim.step()

            draw(screen, font, sim, playback, variant, seed, cell_size)
    finally:
        pygame.quit()
