# Kaucjowicze

Kaucjowicze is a simulation of agents collecting deposit-return cans across the AGH Student Campus (Miasteczko Studenckie AGH) using Ant Colony Optimization (ACO). Agents carry cans back to a collection point and leave pheromone trails that lead others to areas with many cans, and we compare this approach against a random-walk baseline. 

The project is written in Python with NumPy, uses Pygame for visualization and pandas for analyzing results stored in CSV files.

## How to run

Requires Python 3.10 or newer.

### 1. Clone the repository

```bash
git clone https://github.com/adpawel/kaucjowicze.git
cd kaucjowicze
```

### 2. Create and activate a virtual environment

Windows (PowerShell):

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Linux / macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install the project with development tools

```bash
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

Upgrading pip is required: older versions (e.g. 21.x) cannot install the project in editable mode.

### 4. Run the simulation

```bash
python -m kaucjowicze --seed 0
```

This builds the test map, scatters cans and runs a headless simulation: agents start at the base, search for cans, return when their bag is full (or when they have not seen a new can for a while) and go out again. The run ends when all cans are delivered or after the step limit. A summary is printed at the end (steps, collected cans, trips, path length, cans per agent).

Options:

- `--algorithm random|aco`: movement policy, the random-walk baseline (default) or ACO,
- `--reward shared|individual`: reward of ACO agents, shared by default (not available for the random walk),
- `--show-map`: print the map before the run (`#` obstacle, `B` base, digits = number of cans, `+` more than 9, `.` empty).

With `--algorithm aco` an agent walking home leaves a trail on its way, as strong as the number of cans it saw left at the source, so an exhausted source leaves none. Trails evaporate every step. A searching agent follows trails leading away from the base, making a random move instead with probability epsilon. Where there is no trail it explores exactly like the random walk.

The reward decides how agents behave:

- `shared`: all delivered cans are split equally. Agents lay and follow trails as described above, and ignore a trail heading into an area with more searching agents than cans.
- `individual`: each agent keeps what it delivered. Agents leave no trails, so there is no pheromone. Each one remembers its richest source and returns there by the shortest path until the source is exhausted, regardless of the others.

The summary also prints the reward per agent for these variants.

Default parameters (number of agents, bag capacity, vision radius, pheromone, step limit, ...) are defined in `SimulationConfig` in `src/kaucjowicze/config.py`.

### Visualization

The window needs Pygame, which is an optional dependency:

```bash
pip install -e ".[dev,gui]"
python -m kaucjowicze --algorithm aco --reward shared --seed 0 --gui
```

The map shows obstacles (gray), the base (black, framed), cans (yellow to dark red as their number grows), pheromone (green, shared reward only) and agents (blue when searching, magenta when carrying). Without `--seed` a random seed is drawn and shown in the status bar, so a restart still gives the same map.

| Key | Action |
|---|---|
| Space | pause / resume |
| `+` / `-` | faster / slower (1 to 500 steps per second) |
| `R` | restart with the same seed |
| `P` | show / hide the pheromone heat map (`n/a` for the random walk and the individual reward) |
| `Esc` | quit |

### Experiments

Run every variant (random walk, ACO with the shared reward, agents with the individual reward) on the same seeds, so all variants get the same maps:

```bash
python -m kaucjowicze.experiments --seeds 30 --output results
```

This takes a few minutes and writes three CSV files, replacing earlier ones: `runs.csv` (one row per run), `timeline.csv` (one row per step) and `agents.csv` (one row per agent). A threshold not reached within the step limit (`t_50`, `t_90`, `t_100`) is left empty. Options: `--first-seed`, `--max-steps`.

Figures and tables need the optional analysis dependencies:

```bash
pip install -e ".[dev,analysis]"
python -m kaucjowicze.plots --input results --output results/figures
```

This writes the collection curves (`p1_collection_curve.png`, `p2_collection_curve.png`), the distribution of cans per agent (`p2_cans_per_agent.png`) and `summary.md` with means, 95% confidence intervals and Mann-Whitney p-values. The `results/` directory is not tracked by git.

### 5. Run tests and linters

```bash
pytest
ruff check .
ruff format --check .
```

The same checks run in CI on every pull request and push to `master`.
