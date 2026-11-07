# Kaucjowicze

A simulation of agents collecting deposit-return cans on the AGH Student Campus map using Ant Colony Optimization (ACO). Agents bring cans back to a collection point and leave pheromone trails that lead others to areas with many cans. We compare this with a random-walk baseline.

## Setup

Requires Python 3.10 or newer.

```bash
git clone https://github.com/adpawel/kaucjowicze.git
cd kaucjowicze

python -m venv .venv
.venv\Scripts\Activate.ps1      # Windows (PowerShell)
source .venv/bin/activate       # Linux / macOS

python -m pip install --upgrade pip
pip install -e ".[dev,gui,analysis]"
```

Upgrading pip is required, because older versions cannot install the project in editable mode. The `gui` extra is needed only for the window and `analysis` only for figures.

## Run a simulation

```bash
python -m kaucjowicze --seed 0                                      # random walk
python -m kaucjowicze --algorithm aco --seed 0                      # ACO, shared reward
python -m kaucjowicze --algorithm aco --reward individual --seed 0  # individual reward
```

Add `--map campus` to run on the AGH Student Campus instead of the test map, `--gui` to open a window or `--show-map` to print the map before the run. Default parameters are in `src/kaucjowicze/config.py`.

Window controls:

| Key | Action |
|---|---|
| Space | pause / resume |
| `+` / `-` | faster / slower |
| `R` | restart with the same seed |
| `P` | show / hide the pheromone |
| `B` | switch between the aerial photo and the plain map (campus only) |
| `Esc` | quit |

## Run experiments

```bash
python -m kaucjowicze.experiments --seeds 30 --output results
python -m kaucjowicze.plots --input results --output results/figures
```

The first command runs every variant on the same seeds and writes `runs.csv`, `timeline.csv` and `agents.csv`, replacing earlier files. It also accepts `--map`, `--first-seed` and `--max-steps`. The second one writes the figures and `summary.md` with means, confidence intervals and p-values. `results/` is not tracked by git.

## Campus map

The campus map is `src/kaucjowicze/data/ms_agh_map.png`, with one pixel per 3 m cell: white is walkable, black is an obstacle, grey is a dormitory (an obstacle near which can clusters appear) and blue is the collection point. It can be edited by hand, and running the simulation reports a stray color or an enclosed area.

`python tools/build_campus_map.py` generates it from `data/ms_agh_osm.json` and overwrites manual edits. Add `--fetch` to download fresh data and `--preview FILE` to write a picture for checking (needs the `analysis` extra).

`src/kaucjowicze/data/ms_agh_photo.jpg` is the window background, cropped to the map by `python tools/build_campus_map.py --photo`. The simulation does not use it.

Map data © OpenStreetMap contributors, available under the [Open Database License](https://www.openstreetmap.org/copyright). Aerial photo: Główny Urząd Geodezji i Kartografii, [geoportal.gov.pl](https://www.geoportal.gov.pl/pl/dane/ortofotomapa-orto/).

## Tests and linters

```bash
pytest
ruff check .
ruff format --check .
```

CI runs the same checks on every pull request and push to `master`.

## Documentation

- [`PLAN.md`](PLAN.md): project plan
- [`MILESTONES.md`](MILESTONES.md): assumptions and milestones
- [`ALGORITHM.md`](ALGORITHM.md): formulas, decisions and results
- [`NAGRODY.md`](NAGRODY.md): open problems with rewards and proposed trail variants
