import importlib.util
import math
from pathlib import Path

import numpy as np
import pytest

from kaucjowicze.maps import load_mask

_PATH = Path(__file__).parent.parent / "tools" / "build_campus_map.py"
_SPEC = importlib.util.spec_from_file_location("build_campus_map", _PATH)
tool = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(tool)

SMALL = tool.Frame(width_m=60.0, height_m=60.0)  # 20 x 20 cells


def _geo(x, y, frame=SMALL):
    """Geographic point of grid coordinates, the inverse of `Frame.to_cell`."""
    u = x * frame.cell_m + frame.u_min
    v = y * frame.cell_m + frame.v_min
    angle = math.radians(frame.angle_deg)
    east = u * math.cos(angle) - v * math.sin(angle)
    north = -u * math.sin(angle) - v * math.cos(angle)
    lat = frame.anchor_lat + north / 111320.0
    lon = frame.anchor_lon + east / (111320.0 * math.cos(math.radians(frame.anchor_lat)))
    return lat, lon


def _way(tags, *cells):
    points = [_geo(x, y) for x, y in cells]
    return {
        "type": "way",
        "tags": tags,
        "geometry": [{"lat": lat, "lon": lon} for lat, lon in points],
    }


def _base_path():
    return _way({"highway": "footway", "name": tool.BASE_STREET}, (1.5, 1.5), (3.5, 1.5))


def _fence_across():
    return _way({"barrier": "fence"}, (10.5, -1), (10.5, 21))


def _block(tags=None):
    corners = [(5, 5), (9, 5), (9, 9), (5, 9), (5, 5)]
    return _way(tags or {"building": "dormitory"}, *corners)


def test_frame_puts_the_anchor_on_the_eastern_edge():
    frame = tool.Frame()
    x, y = frame.to_cell(frame.anchor_lat, frame.anchor_lon)
    assert x == pytest.approx(frame.width)
    assert 0 < y < frame.height


def test_line_cells_has_no_diagonal_steps():
    cells = tool.line_cells((0.5, 0.5), (6.5, 4.5))
    assert cells[0] == (0, 0)
    assert cells[-1] == (6, 4)
    for a, b in zip(cells, cells[1:], strict=False):
        assert abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1


@pytest.mark.parametrize(
    ("a", "b", "c", "d", "expected"),
    [
        ((0, 0), (2, 2), (0, 2), (2, 0), (1, 1)),
        ((0, 0), (1, 0), (0, 1), (1, 1), None),
        ((0, 0), (1, 1), (2, 0), (3, 1), None),
    ],
)
def test_segment_crossing(a, b, c, d, expected):
    assert tool.segment_crossing(a, b, c, d) == expected


def test_fill_polygons_needs_half_of_a_cell():
    mask = tool.fill_polygons([[(1, 1), (3.1, 1), (3.1, 3), (1, 3)]], 5, 5)
    assert mask[1:3, 1:3].all()
    assert not mask[1:3, 3].any()


def test_components_use_the_moves_of_agents():
    obstacles = np.array([[False, True], [True, False]])  # agents may pass a corner diagonally
    assert (tool.components(obstacles)[~obstacles] == 0).all()


def test_fence_splits_the_map_and_the_smaller_side_is_cut_off():
    campus = tool.build_map([_base_path(), _fence_across()], SMALL)
    assert campus.barriers[5, 10]
    assert campus.cut_off[:, 11:].all()
    assert not campus.cut_off[:, :10].any()


def test_path_crossing_a_fence_opens_it():
    path = _way({"highway": "footway"}, (5.5, 5.5), (15.5, 5.5))
    campus = tool.build_map([_base_path(), _fence_across(), path], SMALL)
    assert not campus.barriers[5, 10]
    assert campus.barriers[10, 10]
    assert not campus.cut_off.any()


def test_gate_opens_a_fence():
    lat, lon = _geo(10.5, 8.5)
    gate = {"type": "node", "tags": {"barrier": "gate"}, "lat": lat, "lon": lon}
    campus = tool.build_map([_base_path(), _fence_across(), gate], SMALL)
    assert not campus.barriers[8, 10]
    assert not campus.cut_off.any()


def test_building_is_an_obstacle_but_a_roof_is_not():
    assert tool.build_map([_base_path(), _block()], SMALL).buildings[7, 7]
    roof = _block({"building": "roof"})
    assert not tool.build_map([_base_path(), roof], SMALL).buildings[7, 7]


def test_building_passage_stays_walkable():
    passage = _way({"highway": "footway", "tunnel": "building_passage"}, (4.5, 7.5), (9.5, 7.5))
    campus = tool.build_map([_base_path(), _block(), passage], SMALL)
    assert not campus.buildings[7, 7]
    assert campus.buildings[6, 7]


def test_mask_round_trips_through_the_loader(tmp_path):
    campus = tool.build_map([_base_path(), _block()], SMALL)
    path = tmp_path / "map.png"
    tool.save_mask(campus, path)
    grid = load_mask(path)
    assert grid.bases == [campus.base]
    assert (grid.obstacles == campus.obstacles).all()


def test_to_geo_is_the_inverse_of_to_cell():
    frame = tool.Frame()
    assert frame.to_cell(*frame.to_geo(12.5, 34.5)) == pytest.approx((12.5, 34.5))


def test_photo_transform_maps_map_corners_to_their_place_on_the_source():
    frame = tool.Frame()
    bbox = (50.066, 19.903, 50.070, 19.909)
    a, b, c, d, e, f = tool.photo_transform(frame, bbox, (1000, 800), scale=10)
    lat, lon = frame.to_geo(frame.width, frame.height)
    x = a * frame.width * 10 + b * frame.height * 10 + c
    y = d * frame.width * 10 + e * frame.height * 10 + f
    assert x == pytest.approx((lon - bbox[1]) / (bbox[3] - bbox[1]) * 1000)
    assert y == pytest.approx((bbox[2] - lat) / (bbox[2] - bbox[0]) * 800)


def test_dormitories_are_kept_apart_from_other_buildings(tmp_path):
    other = _way({"building": "yes"}, (12, 12), (15, 12), (15, 15), (12, 15), (12, 12))
    campus = tool.build_map([_base_path(), _block(), other], SMALL)
    assert campus.dormitories[7, 7]
    assert campus.buildings[13, 13] and not campus.dormitories[13, 13]
    path = tmp_path / "map.png"
    tool.save_mask(campus, path)
    grid = load_mask(path)
    assert (grid.dormitories == campus.dormitories).all()
