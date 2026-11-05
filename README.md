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

- `--algorithm random`: movement policy (currently only the random-walk baseline),
- `--show-map`: print the map before the run (`#` obstacle, `B` base, digits = number of cans, `+` more than 9, `.` empty).

Default parameters (number of agents, bag capacity, vision radius, step limit, ...) are defined in `SimulationConfig` in `src/kaucjowicze/config.py`.

### 5. Run tests and linters

```bash
pytest
ruff check .
ruff format --check .
```

The same checks run in CI on every pull request and push to `master`.
