"""Pygame window. It only reads the simulation and is the only module importing pygame."""

from collections.abc import Callable
from enum import Enum, auto

import pygame

from kaucjowicze.grid import Grid
from kaucjowicze.maps import map_photo
from kaucjowicze.simulation import Simulation
from kaucjowicze.view import (
    BASE_COLOR,
    Playback,
    agent_color,
    compose_map_image,
    compose_photo_overlay,
    hud_lines,
    longest_hud_lines,
)

CELL_SIZE = 10  # pixels per grid cell
HUD_HEIGHT = 66
HUD_LINE_HEIGHT = 20
HUD_PADDING = 4
FONT_SIZE = 22
SCREEN_MARGIN = 80  # room for the title bar and the taskbar
HUD_TEXT_COLOR = (30, 30, 30)
WINDOW_COLOR = (225, 225, 225)  # status bar and the area next to a narrow map
PHOTO_BRIGHTNESS = 215  # of 255: a slightly darker photo lets the cans and agents stand out
OUTLINE_COLOR = (255, 255, 255)  # around the agents and the base, visible on the photo
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
    elif key == pygame.K_b:
        playback.toggle_photo()
    elif key == pygame.K_r:
        return Action.RESTART
    elif key == pygame.K_ESCAPE:
        return Action.QUIT
    return Action.NONE


def fit_cell_size(grid: Grid, screen_size: tuple[int, int]) -> int:
    """Pixels per cell for a window that fits the screen, with its status bar."""
    screen_width, screen_height = screen_size
    if screen_width <= 0 or screen_height <= 0:  # the system did not report the screen
        return CELL_SIZE
    room = screen_height - HUD_HEIGHT - SCREEN_MARGIN
    return max(1, min(CELL_SIZE, screen_width // grid.width, room // grid.height))


def load_photo(sim: Simulation, cell_size: int) -> pygame.Surface | None:
    """The photo of the map, sized to the map on the screen, if the map has one."""
    path = map_photo(sim.config)
    if path is None:
        return None
    size = (sim.grid.width * cell_size, sim.grid.height * cell_size)
    photo = pygame.transform.smoothscale(pygame.image.load(path).convert(), size)
    photo.fill((PHOTO_BRIGHTNESS,) * 3, special_flags=pygame.BLEND_RGB_MULT)
    return photo


def window_size(
    sim: Simulation,
    variant: str,
    seed: int,
    font: pygame.font.Font,
    cell_size: int = CELL_SIZE,
) -> tuple[int, int]:
    """Room for the map and for the status bar text, also on a map narrower than the text."""
    text_width = max(font.size(line)[0] for line in longest_hud_lines(sim, variant, seed))
    width = max(sim.grid.width * cell_size, text_width + 2 * HUD_PADDING)
    return width, sim.grid.height * cell_size + HUD_HEIGHT


def draw(
    screen: pygame.Surface,
    font: pygame.font.Font,
    sim: Simulation,
    playback: Playback,
    variant: str,
    seed: int,
    cell_size: int = CELL_SIZE,
    photo: pygame.Surface | None = None,
) -> None:
    grid = sim.grid
    map_size = (grid.width * cell_size, grid.height * cell_size)
    on_photo = photo is not None and playback.show_photo

    screen.fill(WINDOW_COLOR)
    if on_photo:
        overlay = compose_photo_overlay(grid, sim.pheromone, playback.show_pheromone)
        surface = pygame.image.frombuffer(overlay.tobytes(), (grid.width, grid.height), "RGBA")
        screen.blit(photo, (0, 0))
    else:
        image = compose_map_image(grid, sim.pheromone, playback.show_pheromone)
        # surfarray indexes pixels as [x, y], the grid as [y, x]
        surface = pygame.surfarray.make_surface(image.swapaxes(0, 1))
    screen.blit(pygame.transform.scale(surface, map_size), (0, 0))

    # A single cell is easy to miss, so the base gets a frame around it
    for x, y in grid.bases:
        frame = pygame.Rect((x - 1) * cell_size, (y - 1) * cell_size, 3 * cell_size, 3 * cell_size)
        if on_photo:
            pygame.draw.rect(screen, OUTLINE_COLOR, frame.inflate(4, 4), width=2)
        pygame.draw.rect(screen, BASE_COLOR, frame, width=2)

    for agent in sim.agents:
        center = (
            agent.pos[0] * cell_size + cell_size // 2,
            agent.pos[1] * cell_size + cell_size // 2,
        )
        radius = max(cell_size // 2, 1)
        if on_photo:
            pygame.draw.circle(screen, OUTLINE_COLOR, center, radius + 1)
        pygame.draw.circle(screen, agent_color(agent.state), center, radius)

    for i, line in enumerate(hud_lines(sim, variant, seed, playback)):
        text = font.render(line, True, HUD_TEXT_COLOR)
        screen.blit(text, (HUD_PADDING, map_size[1] + HUD_PADDING + i * HUD_LINE_HEIGHT))
    pygame.display.flip()


def run_gui(
    make_sim: Callable[[], Simulation],
    variant: str,
    seed: int,
    cell_size: int | None = None,
) -> None:
    """Open the window and play the simulation until it is closed.

    `make_sim` must give an identical simulation on every call: restart relies on it.
    """
    sim = make_sim()
    playback = Playback()

    pygame.init()
    try:
        font = pygame.font.Font(None, FONT_SIZE)
        info = pygame.display.Info()  # before set_mode this is the size of the screen
        cell_size = cell_size or fit_cell_size(sim.grid, (info.current_w, info.current_h))
        screen = pygame.display.set_mode(window_size(sim, variant, seed, font, cell_size))
        photo = load_photo(sim, cell_size)
        pygame.display.set_caption(f"Kaucjowicze: {variant}")
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

            draw(screen, font, sim, playback, variant, seed, cell_size, photo)
    finally:
        pygame.quit()
