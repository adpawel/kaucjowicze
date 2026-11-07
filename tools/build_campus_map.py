"""Build the campus obstacle mask from an OpenStreetMap extract.

The result is a PNG with one pixel per grid cell: white is walkable, black is an obstacle, grey
is a dormitory (also an obstacle) and blue is the collection point. The simulation reads only this
PNG, so it can be corrected by hand.

Map data (c) OpenStreetMap contributors, ODbL.

Aerial photo (c) Główny Urząd Geodezji i Kartografii (geoportal.gov.pl).

    python tools/build_campus_map.py --fetch --preview preview.png
    python tools/build_campus_map.py --photo
"""

import argparse
import json
import math
import urllib.parse
import urllib.request
from collections import Counter, deque
from collections.abc import Iterable
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from kaucjowicze.maps import (
    BASE_COLOR,
    CAMPUS_MASK,
    CAMPUS_PHOTO,
    DORMITORY_COLOR,
    FREE_COLOR,
    OBSTACLE_COLOR,
)

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OSM = ROOT / "data" / "ms_agh_osm.json"

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OVERPASS_BBOX = "50.0660,19.9010,50.0710,19.9095"
OVERPASS_QUERY = (
    f"[out:json][timeout:90];(way[building]({OVERPASS_BBOX});way[barrier]({OVERPASS_BBOX});"
    f"node[barrier]({OVERPASS_BBOX});way[highway]({OVERPASS_BBOX}););out geom tags;"
)

NOT_OBSTACLE_BUILDINGS = {"roof", "bridge"}  # people walk under these
OBSTACLE_BARRIERS = {"fence", "hedge", "wall", "retaining_wall"}
OPENING_NODES = {"gate", "lift_gate", "swing_gate", "wicket_gate"}
CLOSED_ACCESS = {"private", "no"}
FOOT_ALLOWED = {"yes", "designated", "permissive"}
NOT_WALKABLE_HIGHWAYS = {"construction"}
PASSAGE_TUNNELS = {"building_passage", "yes"}
BASE_STREET = "Autostrada MS AGH"

ORTHOPHOTO_URL = "https://mapy.geoportal.gov.pl/wss/service/PZGIK/ORTO/WMS/HighResolution"
ORTHOPHOTO_SOURCE_PIXEL_M = 0.2  # requested from the service; the frame is rotated afterwards
PHOTO_PIXELS_PER_CELL = 10
PHOTO_QUALITY = 85
METRES_PER_DEGREE = 111320.0

COVERAGE_THRESHOLD = 0.5  # a cell is a building if at least this share of it is covered
SUPERSAMPLE = 4
OPENING_RADIUS = 1  # cells of a path cleared on each side of its crossing with a barrier


@dataclass(frozen=True)
class Frame:
    """Rectangle aligned with the campus streets, measured in metres from an anchor point.

    The u axis runs along the dormitory fronts (east-south-east) and the v axis across them
    (south-south-west), so map rows and columns follow the walls.
    """

    anchor_lat: float = 50.068556  # the Smok Student statue, on the eastern edge
    anchor_lon: float = 19.90809
    angle_deg: float = 13.0  # measured from dormitory walls
    u_min: float = -300.0
    v_min: float = -78.0
    width_m: float = 300.0
    height_m: float = 273.0
    cell_m: float = 3.0

    @property
    def width(self) -> int:
        return round(self.width_m / self.cell_m)

    @property
    def height(self) -> int:
        return round(self.height_m / self.cell_m)

    def to_cell(self, lat: float, lon: float) -> tuple[float, float]:
        """Continuous (x, y) grid coordinates of a geographic point."""
        east = (lon - self.anchor_lon) * self._metres_per_lon
        north = (lat - self.anchor_lat) * METRES_PER_DEGREE
        angle = math.radians(self.angle_deg)
        u = east * math.cos(angle) - north * math.sin(angle)
        v = -east * math.sin(angle) - north * math.cos(angle)
        return (u - self.u_min) / self.cell_m, (v - self.v_min) / self.cell_m

    def to_geo(self, x: float, y: float) -> tuple[float, float]:
        """Geographic (lat, lon) of continuous grid coordinates, the inverse of `to_cell`."""
        u = x * self.cell_m + self.u_min
        v = y * self.cell_m + self.v_min
        angle = math.radians(self.angle_deg)
        east = u * math.cos(angle) - v * math.sin(angle)
        north = -u * math.sin(angle) - v * math.cos(angle)
        return (
            self.anchor_lat + north / METRES_PER_DEGREE,
            self.anchor_lon + east / self._metres_per_lon,
        )

    @property
    def _metres_per_lon(self) -> float:
        return METRES_PER_DEGREE * math.cos(math.radians(self.anchor_lat))

    def contains(self, point: tuple[float, float], margin: float = 0.0) -> bool:
        x, y = point
        return -margin <= x < self.width + margin and -margin <= y < self.height + margin


Point = tuple[float, float]


def line_cells(a: Point, b: Point) -> list[tuple[int, int]]:
    """Cells crossed by a segment, without diagonal steps, so that nothing slips through it."""
    steps = max(1, math.ceil(max(abs(b[0] - a[0]), abs(b[1] - a[1])) * 8))
    cells: list[tuple[int, int]] = []
    for i in range(steps + 1):
        t = i / steps
        cell = (math.floor(a[0] + (b[0] - a[0]) * t), math.floor(a[1] + (b[1] - a[1]) * t))
        if cells and cell == cells[-1]:
            continue
        if cells and cell[0] != cells[-1][0] and cell[1] != cells[-1][1]:
            cells.append((cell[0], cells[-1][1]))
        cells.append(cell)
    return cells


def set_cells(mask: np.ndarray, cells: Iterable[tuple[int, int]], value: bool) -> None:
    height, width = mask.shape
    for x, y in cells:
        if 0 <= x < width and 0 <= y < height:
            mask[y, x] = value


def segment_crossing(a: Point, b: Point, c: Point, d: Point) -> Point | None:
    """Point where segments ab and cd cross, if they do."""
    r = (b[0] - a[0], b[1] - a[1])
    s = (d[0] - c[0], d[1] - c[1])
    denominator = r[0] * s[1] - r[1] * s[0]
    if denominator == 0:
        return None
    t = ((c[0] - a[0]) * s[1] - (c[1] - a[1]) * s[0]) / denominator
    u = ((c[0] - a[0]) * r[1] - (c[1] - a[1]) * r[0]) / denominator
    if 0 <= t <= 1 and 0 <= u <= 1:
        return a[0] + t * r[0], a[1] + t * r[1]
    return None


def fill_polygons(polygons: Iterable[list[Point]], width: int, height: int) -> np.ndarray:
    """Cells of which at least `COVERAGE_THRESHOLD` is covered by one of the polygons."""
    image = Image.new("1", (width * SUPERSAMPLE, height * SUPERSAMPLE), 0)
    draw = ImageDraw.Draw(image)
    for polygon in polygons:
        draw.polygon([(x * SUPERSAMPLE, y * SUPERSAMPLE) for x, y in polygon], fill=1)
    fine = np.array(image, dtype=np.float32)
    coverage = fine.reshape(height, SUPERSAMPLE, width, SUPERSAMPLE).mean(axis=(1, 3))
    return coverage >= COVERAGE_THRESHOLD


def components(obstacles: np.ndarray) -> np.ndarray:
    """Label walkable areas, using the moves agents have (8 neighbours); obstacles get -1."""
    labels = np.full(obstacles.shape, -1, dtype=np.int32)
    height, width = obstacles.shape
    next_label = 0
    for start_y, start_x in zip(*np.nonzero(~obstacles), strict=True):
        if labels[start_y, start_x] >= 0:
            continue
        labels[start_y, start_x] = next_label
        queue = deque([(int(start_x), int(start_y))])
        while queue:
            x, y = queue.popleft()
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    nx, ny = x + dx, y + dy
                    if (
                        0 <= nx < width
                        and 0 <= ny < height
                        and not obstacles[ny, nx]
                        and labels[ny, nx] < 0
                    ):
                        labels[ny, nx] = next_label
                        queue.append((nx, ny))
        next_label += 1
    return labels


@dataclass
class CampusMap:
    frame: Frame
    buildings: np.ndarray
    dormitories: np.ndarray  # the buildings where people live
    barriers: np.ndarray
    cut_off: np.ndarray  # walkable on the map, but enclosed: treated as obstacles
    base: tuple[int, int]
    ways: list[tuple[dict, list[Point]]]

    @property
    def obstacles(self) -> np.ndarray:
        return self.buildings | self.barriers | self.cut_off


def build_map(elements: list[dict], frame: Frame) -> CampusMap:
    ways: list[tuple[dict, list[Point]]] = []
    nodes: list[tuple[dict, Point]] = []
    for element in elements:
        tags = element.get("tags", {})
        if element["type"] == "way" and "geometry" in element:
            points = [frame.to_cell(p["lat"], p["lon"]) for p in element["geometry"]]
            if any(frame.contains(p, margin=2) for p in points) or _spans_frame(points, frame):
                ways.append((tags, points))
        elif element["type"] == "node":
            nodes.append((tags, frame.to_cell(element["lat"], element["lon"])))

    width, height = frame.width, frame.height
    buildings = fill_polygons(
        (
            points
            for tags, points in ways
            if "building" in tags and tags["building"] not in NOT_OBSTACLE_BUILDINGS
        ),
        width,
        height,
    )

    dormitories = fill_polygons(
        (points for tags, points in ways if tags.get("building") == "dormitory"), width, height
    )

    barrier_segments: list[tuple[Point, Point]] = []
    barriers = np.zeros((height, width), dtype=bool)
    for tags, points in ways:
        if tags.get("barrier") in OBSTACLE_BARRIERS:
            for a, b in zip(points, points[1:], strict=False):
                barrier_segments.append((a, b))
                set_cells(barriers, line_cells(a, b), True)

    # A path crossing a fence or a hedge means there is a way through
    for tags, points in ways:
        if not _is_walkable_path(tags):
            continue
        for a, b in zip(points, points[1:], strict=False):
            path_cells = line_cells(a, b)
            if tags.get("tunnel") in PASSAGE_TUNNELS:
                set_cells(buildings, path_cells, False)
                set_cells(barriers, path_cells, False)
            for c, d in barrier_segments:
                crossing = segment_crossing(a, b, c, d)
                if crossing is not None:
                    set_cells(barriers, _near(path_cells, crossing), False)

    for tags, point in nodes:
        if _is_open_gate(tags):
            x, y = math.floor(point[0]), math.floor(point[1])
            set_cells(barriers, [(x, y), (x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)], False)

    obstacles = buildings | barriers
    labels = components(obstacles)
    sizes = Counter(labels[labels >= 0].tolist())
    main_label = sizes.most_common(1)[0][0]
    cut_off = (labels >= 0) & (labels != main_label)

    base = _choose_base(ways, labels == main_label, frame)
    return CampusMap(frame, buildings, dormitories & buildings, barriers, cut_off, base, ways)


def _spans_frame(points: list[Point], frame: Frame) -> bool:
    """True for long ways whose vertices all lie outside, but which pass over the frame."""
    xs, ys = zip(*points, strict=True)
    return max(xs) >= 0 and min(xs) < frame.width and max(ys) >= 0 and min(ys) < frame.height


def _is_underground(tags: dict) -> bool:
    """A way below ground does not open what is above it."""
    try:
        return int(tags.get("layer", "0")) < 0
    except ValueError:  # OSM values are free text, e.g. "-1;0"
        return False


def _is_open_gate(tags: dict) -> bool:
    if tags.get("barrier") not in OPENING_NODES:
        return False
    if tags.get("foot") in FOOT_ALLOWED:
        return True
    return tags.get("locked") != "yes" and tags.get("access") not in CLOSED_ACCESS


def _is_walkable_path(tags: dict) -> bool:
    return (
        "highway" in tags
        and tags["highway"] not in NOT_WALKABLE_HIGHWAYS
        and tags.get("foot") != "no"
        and not _is_underground(tags)
    )


def _near(cells: list[tuple[int, int]], point: Point) -> list[tuple[int, int]]:
    x, y = math.floor(point[0]), math.floor(point[1])
    return [c for c in cells if max(abs(c[0] - x), abs(c[1] - y)) <= OPENING_RADIUS]


def _choose_base(
    ways: list[tuple[dict, list[Point]]], reachable: np.ndarray, frame: Frame
) -> tuple[int, int]:
    """The reachable cell of the campus main path that is closest to the centre of the map."""
    center = (frame.width / 2, frame.height / 2)
    best: tuple[float, tuple[int, int]] | None = None
    for tags, points in ways:
        if tags.get("name") != BASE_STREET:
            continue
        for a, b in zip(points, points[1:], strict=False):
            for x, y in line_cells(a, b):
                inside = 0 <= x < frame.width and 0 <= y < frame.height
                if inside and reachable[y, x]:
                    distance = math.hypot(x + 0.5 - center[0], y + 0.5 - center[1])
                    if best is None or distance < best[0]:
                        best = (distance, (x, y))
    if best is None:
        raise ValueError(f"No reachable cell on {BASE_STREET}")
    return best[1]


def save_mask(campus: CampusMap, path: Path) -> None:
    image = np.full((*campus.obstacles.shape, 3), FREE_COLOR, dtype=np.uint8)
    image[campus.obstacles] = OBSTACLE_COLOR
    image[campus.dormitories] = DORMITORY_COLOR
    x, y = campus.base
    image[y, x] = BASE_COLOR
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(image, "RGB").save(path, optimize=True)


def check_overpass_response(data: dict) -> None:
    """Overpass reports a timeout or lack of memory with status 200 and partial elements."""
    if "remark" in data:
        raise ValueError(f"Incomplete Overpass response: {data['remark']}")
    if not data.get("elements"):
        raise ValueError("Overpass returned no elements")


def fetch_osm(path: Path) -> None:
    body = urllib.parse.urlencode({"data": OVERPASS_QUERY}).encode()
    request = urllib.request.Request(
        OVERPASS_URL, data=body, headers={"User-Agent": "kaucjowicze-student-project"}
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        data = json.load(response)
    check_overpass_response(data)  # before the file is touched, so that it stays usable
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def photo_transform(
    frame: Frame, bbox: tuple[float, float, float, float], source_size: tuple[int, int], scale: int
) -> tuple[float, float, float, float, float, float]:
    """Affine coefficients from photo pixels to pixels of a north-up image of `bbox`.

    `bbox` is (lat_min, lon_min, lat_max, lon_max). Latitude and longitude are linear in grid
    coordinates over so small an area, so three corners define the whole mapping.
    """
    lat_min, lon_min, lat_max, lon_max = bbox

    def source(x: float, y: float) -> tuple[float, float]:
        lat, lon = frame.to_geo(x / scale, y / scale)
        return (
            (lon - lon_min) / (lon_max - lon_min) * source_size[0],
            (lat_max - lat) / (lat_max - lat_min) * source_size[1],
        )

    x0, y0 = source(0, 0)
    x1, y1 = source(1, 0)
    x2, y2 = source(0, 1)
    return x1 - x0, x2 - x0, x0, y1 - y0, y2 - y0, y0


def fetch_photo(frame: Frame, path: Path, scale: int = PHOTO_PIXELS_PER_CELL) -> None:
    """Download the orthophoto around the frame, then rotate and crop it to exactly the frame."""
    corners = [frame.to_geo(x, y) for x in (0, frame.width) for y in (0, frame.height)]
    margin = 0.0002
    bbox = (
        min(lat for lat, _ in corners) - margin,
        min(lon for _, lon in corners) - margin,
        max(lat for lat, _ in corners) + margin,
        max(lon for _, lon in corners) + margin,
    )
    width_m = (bbox[3] - bbox[1]) * frame._metres_per_lon
    height_m = (bbox[2] - bbox[0]) * METRES_PER_DEGREE
    source_size = (
        round(width_m / ORTHOPHOTO_SOURCE_PIXEL_M),
        round(height_m / ORTHOPHOTO_SOURCE_PIXEL_M),
    )
    query = urllib.parse.urlencode(
        {
            "SERVICE": "WMS",
            "VERSION": "1.3.0",
            "REQUEST": "GetMap",
            "LAYERS": "Raster",
            "STYLES": "",
            "CRS": "EPSG:4326",  # WMS 1.3.0 gives its axes in the order lat, lon
            "BBOX": ",".join(f"{value:.7f}" for value in bbox),
            "WIDTH": source_size[0],
            "HEIGHT": source_size[1],
            "FORMAT": "image/jpeg",
        }
    )
    request = urllib.request.Request(
        f"{ORTHOPHOTO_URL}?{query}", headers={"User-Agent": "kaucjowicze-student-project"}
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        source = Image.open(BytesIO(response.read())).convert("RGB")
    photo = source.transform(
        (frame.width * scale, frame.height * scale),
        Image.Transform.AFFINE,
        photo_transform(frame, bbox, source.size, scale),
        Image.Resampling.BICUBIC,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    photo.save(path, quality=PHOTO_QUALITY, optimize=True)


def report(campus: CampusMap) -> None:
    from_base = _distances(campus.obstacles, campus.base)
    frame = campus.frame
    print(f"Grid: {frame.width} x {frame.height}, {frame.cell_m:g} m per cell")
    print(f"Buildings: {int(campus.buildings.sum())} cells")
    print(f"Dormitories: {int(campus.dormitories.sum())} cells")
    print(f"Barriers: {int((campus.barriers & ~campus.buildings).sum())} cells")
    print(f"Cut off: {int(campus.cut_off.sum())} cells")
    print(f"Walkable: {int((~campus.obstacles).sum())} of {campus.obstacles.size} cells")
    print(f"Base: {campus.base}, farthest cell {int(from_base.max())} steps away")


def _distances(obstacles: np.ndarray, start: tuple[int, int]) -> np.ndarray:
    height, width = obstacles.shape
    distance = np.full(obstacles.shape, -1, dtype=np.int32)
    distance[start[1], start[0]] = 0
    queue = deque([start])
    while queue:
        x, y = queue.popleft()
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                nx, ny = x + dx, y + dy
                if 0 <= nx < width and 0 <= ny < height:
                    if not obstacles[ny, nx] and distance[ny, nx] < 0:
                        distance[ny, nx] = distance[y, x] + 1
                        queue.append((nx, ny))
    return distance


def save_preview(campus: CampusMap, elements: list[dict], path: Path) -> None:
    """The mask with the source map drawn over it, for checking by eye."""
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib import pyplot as plt

    frame = campus.frame
    image = np.full((frame.height, frame.width, 3), 1.0)
    image[campus.barriers] = (0.45, 0.45, 0.45)
    image[campus.buildings] = (0.15, 0.15, 0.15)
    image[campus.cut_off] = (1.0, 0.75, 0.45)

    figure, axes = plt.subplots(figsize=(13, 11.5), dpi=110)
    axes.imshow(image, extent=(0, frame.width, frame.height, 0), interpolation="nearest")
    for tags, points in campus.ways:
        xs, ys = zip(*points, strict=True)
        if "highway" in tags and _is_walkable_path(tags):
            axes.plot(xs, ys, color="#1f77b4", linewidth=0.7, alpha=0.8)
        elif tags.get("barrier") == "hedge":
            axes.plot(xs, ys, color="#2ca02c", linewidth=0.9)
        elif tags.get("barrier") in OBSTACLE_BARRIERS:
            axes.plot(xs, ys, color="#d62728", linewidth=0.9)
        if "building" in tags and tags.get("name"):
            axes.annotate(
                tags["name"].replace("Dom Studencki ", ""),
                (sum(xs) / len(xs), sum(ys) / len(ys)),
                color="white",
                fontsize=8,
                ha="center",
                va="center",
                annotation_clip=True,
            )
    axes.plot(*(c + 0.5 for c in campus.base), marker="*", color="blue", markersize=16)
    axes.set_xlim(0, frame.width)
    axes.set_ylim(frame.height, 0)
    axes.set_xticks(range(0, frame.width + 1, 10))
    axes.set_yticks(range(0, frame.height + 1, 10))
    axes.grid(color="#999999", linewidth=0.3)
    axes.set_title(
        "dark: building, grey: barrier, orange: cut off, star: base | "
        "blue: path, green: hedge, red: fence"
    )
    figure.tight_layout()
    figure.savefig(path)
    plt.close(figure)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--osm", type=Path, default=DEFAULT_OSM, help="OSM extract (JSON)")
    parser.add_argument("--output", type=Path, default=CAMPUS_MASK, help="mask to write (PNG)")
    parser.add_argument("--fetch", action="store_true", help="download the extract first")
    parser.add_argument("--preview", type=Path, help="also write a picture for checking by eye")
    parser.add_argument("--photo", action="store_true", help="only download the aerial photo")
    args = parser.parse_args(argv)

    if args.photo:
        fetch_photo(Frame(), CAMPUS_PHOTO)
        return
    if args.fetch:
        fetch_osm(args.osm)
    elements = json.loads(args.osm.read_text(encoding="utf-8"))["elements"]
    campus = build_map(elements, Frame())
    save_mask(campus, args.output)
    report(campus)
    if args.preview:
        save_preview(campus, elements, args.preview)


if __name__ == "__main__":
    main()
