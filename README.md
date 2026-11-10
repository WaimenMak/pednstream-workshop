# Where do people go? A PedNStream workshop on OD weights

In this workshop you use [PedNStream](https://github.com/WaimenMak/PedNStream), a pedestrian
network flow simulator based on the Link Transmission Model. You play with **origin–destination (OD)
weights** in a small station network and see how *who wants to go where* decides *where and when*
crowds build up.

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

## Option 1: Google Colab (recommended, nothing to install, no coding needed)
Click a badge, sign in with a Google account, and press ▶ on the first cell ("Run me first").
After that, every exercise is a form with sliders: change the values, then press ▶.

| Part | |
|---|---|
| 1 · Guided exercises | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/WaimenMak/pednstream-workshop/blob/main/colab/01_od_weights_guided_colab.ipynb) |
| 2 · Playground | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/WaimenMak/pednstream-workshop/blob/main/colab/02_playground_colab.ipynb) |
| 3 · Challenge | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/WaimenMak/pednstream-workshop/blob/main/colab/03_challenge_colab.ipynb) |

Each Colab notebook is self-contained, so it also works if you upload it to Colab
(**File → Upload notebook**) or open it from Google Drive.

> Facilitators: the `colab/` notebooks are generated. After editing `workshop_tools.py` or the
> network, run `python tools/build_colab.py`.

## Option 2: Your own laptop (Python ≥ 3.11)
```bash
git clone <this-repo-url> pednstream-workshop
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
jupyter lab
```

## The notebooks
| # | Notebook | What you do | Time |
|---|---|---|---|
| 1 | `01_od_weights_guided.ipynb` | Four guided exercises: predict, run, explain | ~50 min |
| 2 | `02_playground.ipynb` | Sliders for OD weights, demand, route choice and width | ~20 min |
| 3 | `03_challenge.ipynb` | Be the station manager: beat the leaderboard | ~30 min |

## Cheat-sheet
```python
from workshop_tools import run, compare, compare_maps, switch

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

The network itself lives in `networks/station_square/sim_params.yaml`. Every PedNStream parameter is
in there if you want to go further.
