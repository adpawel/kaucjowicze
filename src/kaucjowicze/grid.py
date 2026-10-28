"""2D grid environment: obstacles (dormitories), bases (collection points) and cans.

Positions are (x, y) tuples; arrays are indexed as [y, x].
"""

import numpy as np

Position = tuple[int, int]


class Grid:
    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.obstacles = np.zeros((height, width), dtype=bool)
        self.cans = np.zeros((height, width), dtype=np.int32)
        self.bases: list[Position] = []

    def in_bounds(self, pos: Position) -> bool:
        x, y = pos
        return 0 <= x < self.width and 0 <= y < self.height

    def is_free(self, pos: Position) -> bool:
        """True if the cell is inside the map and not an obstacle."""
        return self.in_bounds(pos) and not self.obstacles[pos[1], pos[0]]

    def add_obstacle(self, x: int, y: int, w: int, h: int) -> None:
        """Mark a rectangle (clipped to the map) as an obstacle."""
        x0, x1 = max(x, 0), min(x + w, self.width)
        y0, y1 = max(y, 0), min(y + h, self.height)
        if x0 < x1 and y0 < y1:
            self.obstacles[y0:y1, x0:x1] = True

    def add_base(self, pos: Position) -> None:
        if not self.is_free(pos):
            raise ValueError(f"Base must be placed on a free cell, got {pos}")
        self.bases.append(pos)

    def is_base(self, pos: Position) -> bool:
        return pos in self.bases

    def add_can(self, pos: Position, count: int = 1) -> None:
        if not self.is_free(pos):
            raise ValueError(f"Cans must be placed on a free cell, got {pos}")
        self.cans[pos[1], pos[0]] += count

    def take_can(self, pos: Position) -> bool:
        """Remove one can from the cell. Returns False if there was none or pos is off the map."""
        if not self.in_bounds(pos):
            return False
        x, y = pos
        if self.cans[y, x] == 0:
            return False
        self.cans[y, x] -= 1
        return True

    def free_cells(self) -> np.ndarray:
        """Array of shape (n, 2) with (x, y) of every free cell."""
        ys, xs = np.nonzero(~self.obstacles)
        return np.column_stack((xs, ys))

    @property
    def total_cans(self) -> int:
        return int(self.cans.sum())

    def render_ascii(self) -> str:
        """Text view: '#' obstacle, 'B' base, digit/'+' cans, '.' empty."""
        rows = []
        for y in range(self.height):
            row = []
            for x in range(self.width):
                if self.obstacles[y, x]:
                    row.append("#")
                elif (x, y) in self.bases:
                    row.append("B")
                elif self.cans[y, x] > 9:
                    row.append("+")
                elif self.cans[y, x] > 0:
                    row.append(str(self.cans[y, x]))
                else:
                    row.append(".")
            rows.append("".join(row))
        return "\n".join(rows)
