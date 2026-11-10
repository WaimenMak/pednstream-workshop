# Where do people go? A PedNStream workshop on OD weights

In this workshop you use [PedNStream](https://github.com/WaimenMak/PedNStream), a pedestrian
network flow simulator based on the Link Transmission Model. You play with **origin–destination (OD)
weights** in a small station network and see how *who wants to go where* decides *where and when*
crowds build up. In the last part you use PedNStream directly, as you would in your own research.

```
            6  City Exit (Y)
            |
            4  Mall Junction
            |  \
   (wide)   |    \   (narrow diagonal)
            |      \
   0 ───────2 ───────3 ─────────── 5  Platform (X)
  West     Plaza  ↑  Hall
  Gate (A)    NARROW  |
                      1  South Gate (B)
```

## The notebooks: click to open in Google Colab
Nothing to install. Sign in with a Google account, run the first cell, and follow the notebook.

| Part | What you do | Time | |
|---|---|---|---|
| 1 · Guided exercises | Predict, run, explain: four exercises with sliders | ~50 min | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/WaimenMak/pednstream-workshop/blob/main/notebooks/01_od_weights_guided.ipynb) |
| 2 · Playground | Free exploration: OD weights, demand, route choice, width | ~20 min | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/WaimenMak/pednstream-workshop/blob/main/notebooks/02_playground.ipynb) |
| 3 · Challenge | Be the station manager and beat the leaderboard | ~30 min | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/WaimenMak/pednstream-workshop/blob/main/notebooks/03_challenge.ipynb) |
| 4 · Your own research | Use PedNStream directly: your own network, overrides, a parameter sweep | ~30 min | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/WaimenMak/pednstream-workshop/blob/main/notebooks/04_pednstream_in_your_research.ipynb) |

Parts 1–3 need no coding: every exercise is a form with sliders. Part 4 is for those who want to see
the code.

## How the install works
Each notebook starts with one line, the same way you install any Python package:

```python
%pip install -q "pednstream-workshop @ git+https://github.com/WaimenMak/pednstream-workshop.git"
```

This repository *is* a small Python package (`src/pednstream_workshop/`) with the Station Square
network and the plotting helpers. Installing it also installs **PedNStream** (pinned in
`pyproject.toml`). For your own project you only need PedNStream itself (see Part 4):

```python
%pip install "pednstream @ git+https://github.com/WaimenMak/PedNStream.git"
```

## Running locally instead (Python ≥ 3.11)
```bash
git clone https://github.com/WaimenMak/pednstream-workshop.git
```
```bash
cd pednstream-workshop
```
```bash
python -m venv .venv
```
```bash
source .venv/bin/activate        # Windows: .venv\Scripts\activate
```
```bash
pip install -r requirements.txt
```
```bash
python check_setup.py            # should end with "All good"
```
```bash
jupyter lab notebooks/
```

## Cheat-sheet for the helper package
```python
from pednstream_workshop import run, compare, compare_maps, switch

res = run(od={"0_5": 3, "0_6": 1, "1_5": 1, "1_6": 1})   # A sends 75% to X, B sends 50%
res.dashboard()          # map + density over time + arrivals
res.kpis()               # headline numbers
res.link_table()         # per corridor
res.route_split()        # how each OD pair splits over its routes

run(od={"0_5": switch(1, 6, at_step=150)})               # weight changes at minute 25
run(demand={0: {"peak_lambda": 60}})                     # busier Gate A
run(route_choice={"beta": 0})                            # people ignore crowding
run(links={"2_3": {"width": 4}})                         # widen the narrow corridor
compare({"name 1": res1, "name 2": res2})                # KPI table side by side
```

**OD keys** are `"origin_destination"`: origins `0` (West Gate A) and `1` (South Gate B),
destinations `5` (Platform X) and `6` (City Exit Y). The weights are **relative per origin**:
`{"0_5": 3, "0_6": 1}` means 75% of Gate A's people want the Platform.

## Repository layout
```
src/pednstream_workshop/      the helper package (run, compare, plots, playground)
  networks/station_square/    the network: sim_params.yaml + node_positions.json
notebooks/                    the four workshop notebooks (Colab and Jupyter)
tools/build_notebooks.py      regenerates notebooks/ (facilitators only)
check_setup.py                local install check
```
