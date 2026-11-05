"""Can collector agent (kaucjowicz): state and counters; behaviour lives in the simulation."""

from dataclasses import dataclass
from enum import Enum

from kaucjowicze.grid import Position


class AgentState(Enum):
    SEARCHING = "searching"  # looking for cans and picking them up
    CARRYING = "carrying"  # walking back to a base to empty the bag


@dataclass
class Agent:
    id: int
    pos: Position
    state: AgentState = AgentState.SEARCHING
    bag: int = 0  # cans currently carried
    cans_collected: int = 0  # cans delivered to a base so far
    path_length: int = 0  # number of moves made
    trips: int = 0  # number of deliveries to a base
    steps_without_can: int = 0  # steps since the agent last saw a can
    heading: Position | None = None  # last movement direction, used by the random walk
    source_cans: int = 0  # cans seen left behind at the last pick-up; sets trail strength
    remembered_source: Position | None = None  # private memory of the richest known source
    remembered_cans: int = 0  # cans the agent last saw left at the remembered source
