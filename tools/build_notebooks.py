"""Build the workshop notebooks in notebooks/ (they work in Colab and Jupyter).

The first code cell of every notebook is a normal `pip install` of the
`pednstream-workshop` package, which pulls in PedNStream itself.

Re-run after changing this file:
    python tools/build_notebooks.py
"""

from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "notebooks"

# What students install. Pin to a tag (...git@v1.0) before the workshop so that
# later pushes to main don't change what students get.
WORKSHOP_PIP = "pednstream-workshop @ git+https://github.com/WaimenMak/pednstream-workshop.git"
PEDNSTREAM_PIP = "pednstream @ git+https://github.com/WaimenMak/PedNStream.git@4a85236b3c47b17f25c2bfe8d5c0ef35651900a7"

MAP = '''```
            6  City Exit (Y)
            |
            4  Mall Junction
            |  \\
   (wide)   |    \\   (narrow diagonal)
            |      \\
   0 ───────2 ───────3 ─────────── 5  Platform (X)
  West     Plaza  ↑  Hall
  Gate (A)    NARROW  |
                      1  South Gate (B)
```'''

AMS_MAP = """
**The network is the real street map.** Every walkable street, square and footpath within about 650 m of
the line from Centraal Station to Museumplein comes straight from **OpenStreetMap**: about 350 junctions
and 650 street segments, with their real lengths. People walk one of **5 routes** (see Step 2), so only the
about 120 street segments on those routes are simulated; that keeps each run short. The numbered dots are
the main places:

| node | place | | node | place |
|---|---|---|---|---|
| **0** | **Centraal Station** (start) | | 5 | Leidseplein |
| 1 | Stationsplein | | 6 | Rembrandtplein |
| 2 | Dam (Madame Tussauds) | | 7 | Weteringcircuit |
| 3 | Spui | | 8 | Rijksmuseum |
| 4 | Muntplein | | **9** | **Museumplein** (the event) |

Grey streets are empty; coloured streets have people on them (green = free walking, red = jammed)."""

HOW_TO = """
**How to use this notebook**
* Press **▶** on the left of a grey cell (or click it and press **Shift + Enter**) to run it.
* Cells with sliders and boxes are *forms*: change the values on the right, then press ▶ again.
* You never have to edit code. If you're curious, double-click a form to see the code behind it.
* Something broken? **Runtime → Restart session**, then run the first cell again.
"""


SETUP_MD = """
## ▶ Step 1: install (run this first, ≈30 s)
This is how you install **any** Python package from GitHub. `pednstream-workshop` is a small
package with this workshop's network and plotting helpers; installing it also installs
**PedNStream** itself. If Colab restarted, run it again.
You can ignore the note *"you may need to restart the kernel"*.
"""


def setup_cell(imports: str, min_version: str = "") -> str:
    if not min_version:
        return f'''%pip install -q "{WORKSHOP_PIP}"

import matplotlib.pyplot as plt
{imports}
plt.rcParams["figure.dpi"] = 90
print("✅ Ready! Scroll down and continue.")'''
    # pip skips the install when the same version is already there, and Python keeps an
    # already-imported old copy until the session restarts, so check what got loaded.
    # The same goes for PedNStream (its version number does not change between commits),
    # so reinstall it when the installed commit is not the pinned one.
    commit = PEDNSTREAM_PIP.rsplit("@", 1)[1]
    return f'''%pip install -q "{WORKSHOP_PIP}"
import json, importlib.metadata as md
if json.loads(md.distribution("pednstream").read_text("direct_url.json") or "{{}}").get("vcs_info", {{}}).get("commit_id") != "{commit}":
    %pip install -q --force-reinstall --no-deps "{PEDNSTREAM_PIP}"

import matplotlib.pyplot as plt
import pednstream_workshop
if tuple(map(int, pednstream_workshop.__version__.split("."))) < {tuple(map(int, min_version.split(".")))}:
    raise RuntimeError("An old version of the workshop package is loaded. "
                       "Click Runtime → Restart session, then run this cell again.")
{imports}
plt.rcParams["figure.dpi"] = 90
print("✅ Ready! Scroll down and continue.")'''


def setup(imports: str, min_version: str = ""):
    """Markdown explanation plus the short, visible install cell."""
    return [md(SETUP_MD), code(setup_cell(imports, min_version))]


def md(s):
    return nbf.v4.new_markdown_cell(s.strip())


def form(src):
    c = nbf.v4.new_code_cell(src.strip())
    c.metadata["cellView"] = "form"
    return c


def code(src):
    return nbf.v4.new_code_cell(src.strip())


def write(name, cells):
    nb = nbf.v4.new_notebook()
    nb.cells = cells
    nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
    nb.metadata["colab"] = {"provenance": [], "toc_visible": True}
    nb.metadata["language_info"] = {"name": "python"}
    OUT.mkdir(exist_ok=True)
    nbf.write(nb, OUT / name)


# =============================================================================
# 01 guided
# =============================================================================
write("01_od_weights_guided.ipynb", [
    md(f"""
# Part 1 · How PedNStream works
### From one corridor to a city: walking, OD weights, and a network of your own

In about 40 minutes you will
1. see the **one rule** PedNStream uses for walking,
2. watch a **queue** grow in a single corridor,
3. find out why **who goes where** (the OD weights) matters as much as **how many** people there are,
4. run the same model on **real Amsterdam streets**,
5. **build your own network**, with your own OD weights and arrival pattern.

Work in pairs: one person clicks, the other takes notes.
{HOW_TO}
"""),
    *setup("from pednstream_workshop import (run, compare, compare_maps, make_network, arrival_plan,\n"
           "                                 plot_speed_density, AMSTERDAM)", min_version="1.12.0"),
    md("""
## 1 · PedNStream in one minute
PedNStream does not move individual dots around. It keeps track of **how many people** are on each
corridor and updates that every **time step** (here 10 seconds). That makes it fast: a whole city
centre runs in seconds.

**The network** is a set of **nodes** (gates, junctions, destinations) joined by **corridors** (links).
Every corridor has a length and a width, and people can walk it both ways.

**Every 10 seconds, four things happen:**

| | what happens | decided by | you set it with |
|---|---|---|---|
| 1 | people **arrive** at the origins (gates) | the **arrival pattern**: people per minute | `arrivals=` |
| 2 | each new person gets a **destination** and keeps it | the **OD weights** | `od=` |
| 3 | at each junction people pick their **next corridor** | **route choice**: shorter, wider and emptier routes are more attractive | `route_choice=` |
| 4 | people **walk** | how crowded the corridor is (below) | corridor `width` |

When the next corridor is full, people cannot step into it: they wait, and the queue grows
**backwards** into the corridors behind them (*spill-back*). If even the first corridor at a gate is full,
new arrivals are **turned away**.

PedNStream is built on the *Link Transmission Model* from traffic engineering, adapted to people walking
in both directions. Press ▶ to see its walking rule.
"""),
    form('''#@title ▶ The walking rule {display-mode: "form"}
corridor_width_m = 2  #@param {type:"slider", min:0.5, max:6, step:0.5}
plot_speed_density(width=corridor_width_m); plt.show()'''),
    md("""
**How to read this**
* Up to **2 people per m²** everyone walks at full speed (1.1 m/s). Above that people slow down, and at
  **6 per m²** nobody moves.
* Flow = density × speed. It is highest at 2 per m²: that is the corridor's **capacity**, and it grows
  with the width. A wider corridor passes more people per minute; a longer one does not.
* Density counts **both directions**: people walking towards you take up room too.

> **Try:** set the width to 1 m, then 3 m. How many people per minute can each one pass?

<details><summary>💡 Our answer</summary>
1 m: about <b>130</b> people per minute. 3 m: about <b>400</b>. Three times as wide passes three times as many
people. (Capacity = 2 people per m² × 1.1 m/s × width × 60 s.)
</details>

---
## 2 · First run: one corridor with a bottleneck
```
   0 ─────── 1 ─────── 2 ─────── 3 ═══════ 4 ─────── 5
Entrance          40 m each, 3 m wide      ↑          Exit
                                       bottleneck
```
For 20 minutes people arrive at the entrance, then nobody. Everyone walks to the exit. Press ▶, then change
the bottleneck width and press ▶ again.
"""),
    form('''#@title ▶ Run the corridor {display-mode: "form"}
bottleneck_width_m = 1.5  #@param {type:"slider", min:0.5, max:3, step:0.5}
people_per_minute = 200  #@param {type:"slider", min:20, max:400, step:20}

corridor = make_network(
    corridors=["0-1", "1-2", "2-3", "3-4", "4-5"],
    positions={0: (0, 0), 1: (40, 0), 2: (80, 0), 3: (120, 0), 4: (160, 0), 5: (200, 0)},  # metres
    origins=[0], destinations=[5],
    widths={"3-4": bottleneck_width_m},
    names={0: "Entrance", 5: "Exit"},
    folder="corridor", minutes=40)
rush = arrival_plan([people_per_minute, people_per_minute], block_minutes=10)   # 2 x 10 minutes, then nobody
one = run(network_dir=corridor, arrivals={0: rush})
one.dashboard("One corridor with a bottleneck", flow=True); plt.show()
display(one.kpis().to_frame("value"))'''),
    md("""
**How to read the dashboard** (you'll see it for every network)
* **Map** (left): corridors coloured by density at the busiest moment: green is free walking, yellow and
  red is crowded.
* **Density per corridor** (top right): one line per corridor. The dashed line is the 2 per m² where
  people start to slow down.
* **In and out** (bottom right): blue is people entering (your arrival pattern), red is people reaching a
  destination, the dashed line is how many people are inside.

**Discuss with your partner** (bottleneck 1.5 m, 200 people per minute)
1. Which corridor gets crowded **first**? Which one **next**?
2. About how many people per minute reach the exit while there is a queue? More or fewer than the 200 who arrive?
3. Make the bottleneck **2 m**, then **0.5 m**. What changes?

<details><summary>💡 Our answers</summary>
<b>1.</b> First the bottleneck itself, 3_4 (minute 3), then the corridor just before it, 2_3 (minute 5), then
1_2 (minute 14). The queue grows <b>backwards</b>, towards the entrance. The corridor after the bottleneck,
4_5, stays quiet.<br><br>
<b>2.</b> About <b>150</b> per minute, fewer than the 200 who arrive, so the queue keeps growing until the arrivals
stop at minute 20. It is even fewer than the ≈200 a 1.5 m corridor can pass at best: the bottleneck is packed
(about 3 people per m²), and a packed corridor moves slowly. That is the right-hand side of the flow curve.<br><br>
<b>3.</b> 2 m: no queue. A 2 m corridor passes up to ≈260 people per minute, more than the 200 who arrive.
0.5 m: the queue reaches the entrance after about 10 minutes, and about 1,100 of the 4,000 people are
turned away.
</details>
"""),
    form('''#@title 🎬 Animate the corridor (optional, ≈15 s) {display-mode: "form"}
display(one.animate(every=3))'''),
    md(f"""
---
## 3 · Who goes where? Meet *Station Square*
{MAP}
* **Two entrances**: West Gate **A** enters at the Plaza, South Gate **B** enters at the Hall.
* **Two destinations**: the **Platform X** and the **City Exit Y**.
* Corridor **2_3** (Plaza–Hall) is narrow: only **2 m** wide.
* A rush of people arrives at both gates, peaking around minute 17. The rush is **the same in every run**.
* Where there are two routes, people choose by **distance**, **crowding** and **width**.
"""),
    md("""
## 4 · What is an OD weight?
An **OD weight** says how strongly the people entering at a gate (the *origin*) are drawn to each
*destination*. Weights are **relative**: `3` and `1` mean "three times as many head to the Platform as
to the City Exit". The arrival pattern sets how *many* people enter; the weights only decide where they head.

The cell below opens **only Gate A**. Press ▶, then move the sliders and press ▶ again.
"""),
    form('''#@title ▶ Try OD weights for Gate A {display-mode: "form"}
weight_A_to_Platform = 3  #@param {type:"slider", min:0, max:10, step:1}
weight_A_to_CityExit = 1  #@param {type:"slider", min:0, max:10, step:1}
only_A = run(od={"0_5": weight_A_to_Platform, "0_6": weight_A_to_CityExit}, origins=[0])

od = only_A.network.od_tracker.od_table()        # PedNStream follows every person from gate to destination
to_x, to_y = od[(0, 5)]["entered"], od[(0, 6)]["entered"]
share = to_x / max(to_x + to_y, 1e-9)
print(f"Gate A sent {share:.0%} to Platform X ({to_x:.0f} people) "
      f"and {1 - share:.0%} to City Exit Y ({to_y:.0f} people)")'''),
    md("""
> **Try:** 1 & 1, then 10 & 10, then 1 & 0. What share goes to the Platform each time?
>
> Every person who enters gets a destination drawn from the weights and keeps it all the way.
> **The weights decide where people go; the simulation decides which route they take and when they arrive.**

<details><summary>💡 Our answer</summary>
1 & 1: <b>50%</b>. 10 & 10: also <b>50%</b>, because only the ratio counts, not the size. 1 & 0: <b>100%</b>, nobody
goes to the City Exit. (3 & 1 gives 75%.) The number of people entering is the same every time: the weights
only split them.
</details>

---
## 5 · Same totals, different mix ⭐
Now both gates are open. Three ways to divide the travellers, and in all three **half of all travellers
go to each destination**. Only *who* goes where differs:

| scenario | Gate A goes to | Gate B goes to |
|---|---|---|
| **baseline** | half X, half Y | half X, half Y |
| **crossing** | Platform X (east) | City Exit Y (north) |
| **parallel** | City Exit Y (north) | Platform X (east) |

Guess first with your partner: will the three behave the same? Then press ▶.
"""),
    form('''#@title ▶ Run the three scenarios {display-mode: "form"}
base = run()
crossing = run(od={"0_5": 1, "0_6": 0, "1_5": 0, "1_6": 1})
parallel = run(od={"0_5": 0, "0_6": 1, "1_5": 1, "1_6": 0})
runs = {"baseline": base, "crossing": crossing, "parallel": parallel}
compare_maps(runs); plt.show()
display(compare(runs))'''),
    md("""
**How to read this**
* **Map**: corridor colour = density at that scenario's busiest moment.
* **time spent inside (person-hours)**: the main "how bad was it" number. **Lower is better.**
* **turned away**: people who could not even enter because the first corridor was full.

**Discuss with your partner**
1. Which scenario takes the most time (person-hours)?
2. Look at corridor 2_3 (Plaza–Hall) on the three maps. Why is it busy in one scenario and almost empty in another?

<details><summary>💡 Our answers</summary>
<b>1.</b> <b>Crossing</b>: about 650 person-hours, against about 435 for baseline and 340 for parallel. The same number
of people reach each destination in all three.<br><br>
<b>2.</b> In crossing, Gate A's walkers go east to the Platform and part of Gate B's walkers go west to the City
Exit, so they meet <b>head-on</b> in the narrow 2 m corridor 2_3 (up to 3.5 people per m²). People walking
towards you count towards the density too, so everyone slows down. In parallel, Gate A heads north and Gate B
heads east: nobody needs 2_3 (0.1 per m²) and the two streams never meet.<br>
So "50% go to the Platform" is not enough to predict the crowding: you need to know <i>who</i> goes where.
</details>

---
## 6 · Same model, a real city
PedNStream does not care how big the network is. This is the network of Part 3: real streets from
**OpenStreetMap** between Amsterdam **Centraal Station** and **Museumplein**, about 120 street segments.
People leave the station at a steady rate for an hour and walk to Museumplein, choosing between 5 routes.
The run takes about 5 seconds.
"""),
    form('''#@title ▶ Run Amsterdam {display-mode: "form"}
people_per_minute_from_the_station = 300  #@param {type:"slider", min:60, max:900, step:60}
ams = run(network_dir=AMSTERDAM, arrivals={0: arrival_plan([people_per_minute_from_the_station] * 6)})
ams.dashboard("Centraal Station → Museumplein", flow=True); plt.show()
display(ams.kpis().to_frame("value"))'''),
    md("""
> **Try:** 300 people per minute, then 600. Does the red line (arriving at Museumplein) get as high as the
> blue (leaving the station)?

<details><summary>💡 Our answer</summary>
300: yes. The first people arrive after about <b>44 minutes</b> (the walk on empty streets), and from then on 300
per minute arrive, as many as leave. 600: no. Arrivals level off at about <b>400</b> per minute: the streets near
Muntplein (Oude Turfmarkt) jam, and when the 2 hours are over about 8,000 people are still on their way.
You'll plan this event yourself in <b>Part 3</b>.
</details>

---
## 7 · Build your own network ⭐
Now you are the modeller. A network needs just a few things:
1. **Nodes**, numbered `0, 1, 2, …` with an **x, y position in metres**. A corridor's length is the
   distance between its two nodes.
2. **Corridors** between pairs of nodes, e.g. `"1-2"`. They are 3 m wide unless you say otherwise.
3. **Origins** (where people enter) and **destinations** (where they want to go).
4. **OD weights** per origin–destination pair, as in sections 4 and 5. Pairs you leave out get weight 0.
5. An **arrival pattern** per origin: people per minute, one value per block of minutes.
   `[120, 240, 120, 0]` with 5-minute blocks = 120/min for 5 minutes, 240/min for 5 minutes, and so on.

The example is a small museum. People enter at the **Entrance** and leave by **Exit East** or **Exit
North**; between them two routes run through the narrow Hall–Square corridor or past the Gallery:
```
                       6 Exit North
                       |
        3 ──────────── 4
     Gallery           |  Garden
        |              |
 0 ──── 1 ════════════ 2 ──── 5
Entrance Hall   (2 m)  Square  Exit East
```
In Colab, type in the boxes on the right (keep the brackets and quotes). In Jupyter, edit the values in the code.
"""),
    form('''#@title 🛠️ **Your network**: edit the values, then press ▶ {display-mode: "form"}
#@markdown ### 1 · Nodes: numbers 0, 1, 2, … with x, y in metres, and (optional) names
positions = {0: (0, 0), 1: (60, 0), 2: (140, 0), 3: (60, 70), 4: (140, 70), 5: (200, 0), 6: (140, 130)}  #@param {type:"raw"}
names = {0: "Entrance", 1: "Hall", 2: "Square", 3: "Gallery", 4: "Garden", 5: "Exit East", 6: "Exit North"}  #@param {type:"raw"}
#@markdown ### 2 · Corridors (two-way), and the ones that are not 3 m wide
corridors = ["0-1", "1-2", "1-3", "3-4", "2-4", "2-5", "4-6"]  #@param {type:"raw"}
widths = {"1-2": 2}  #@param {type:"raw"}
#@markdown ### 3 · Where people enter, and where they want to go
origins = [0]  #@param {type:"raw"}
destinations = [5, 6]  #@param {type:"raw"}
#@markdown ### 4 · OD weights, as "origin_destination": weight (pairs you leave out get 0)
od_weights = {"0_5": 2, "0_6": 1}  #@param {type:"raw"}
#@markdown ### 5 · Arrival pattern: people per minute at each origin, one value per block
arrivals_per_minute = {0: [120, 240, 120, 0]}  #@param {type:"raw"}
block_minutes = 5  #@param {type:"slider", min:1, max:15, step:1}
simulate_minutes = 40  #@param {type:"slider", min:10, max:120, step:5}

folder = make_network(corridors, positions, origins, destinations, widths=widths, names=names,
                      folder="my_network", minutes=simulate_minutes)
od = {f"{o}_{d}": od_weights.get(f"{o}_{d}", 0) for o in origins for d in destinations}
for o in origins:
    if o not in arrivals_per_minute:
        raise ValueError(f"Origin {o} has no arrival pattern: add it to arrivals_per_minute")
    if not any(od[f"{o}_{d}"] for d in destinations):
        raise ValueError(f"Origin {o}: give at least one OD weight above 0, e.g. '{o}_{destinations[0]}': 1")
arrivals = {o: arrival_plan(plan, block_minutes) for o, plan in arrivals_per_minute.items()}
mine = run(network_dir=folder, od=od, arrivals=arrivals)
mine.dashboard("My network", flow=True); plt.show()
display(mine.kpis().to_frame("value"))
print("Which routes people chose (share per OD pair, at the junction where the routes split):")
display(mine.route_split())'''),
    md("""
**Ideas to try**
1. **Same people, different timing.** Try arrivals `{0: [480, 0, 0, 0]}`, then `{0: [120, 120, 120, 120]}`.
   Both bring 2,400 people. Which one is better?
2. **Make a route narrow.** Set `widths = {"1-2": 2, "1-3": 1}`. Which route do people take now?
3. **A second entrance.** Add a Side Gate north of the Gallery:
   * `positions`: add `7: (60, 130)`, and `names`: add `7: "Side Gate"`
   * `corridors`: add `"3-7"`, and set `origins = [0, 7]`
   * `arrivals_per_minute`: add `7: [120, 240, 120, 0]`

   Then compare `od_weights = {"0_6": 1, "7_5": 1}` with `{"0_5": 1, "7_6": 1}`. Which one is worse, and why?
4. **Your own place.** Sketch a station, a stadium or your campus on paper, number the junctions,
   guess their positions in metres, and type it in. Start with one origin and one destination.

<details><summary>💡 Our answers</summary>
<b>1.</b> The burst <code>[480, 0, 0, 0]</code> <i>looks</i> better (131 person-hours against 161), but look at
<i>turned away</i>: about 700 of the 2,400 people could not even get in, so their time is not counted. Spread out,
nobody is turned away. Always check <i>turned away</i> next to the time.<br><br>
<b>2.</b> Almost everyone switches to the Hall–Square corridor 1_2: from 66% to 97% of the people going to Exit East,
and from 27% to 84% of those going to Exit North. Corridor 1_2 climbs from 1.0 to almost 2 people per m², right at
the edge of slowing down. So the crowd moves to the other route; with more people, 1_2 would jam.<br><br>
<b>3.</b> <code>{"0_6": 1, "7_5": 1}</code> is worse: about 330 person-hours against 280. Entrance → Exit North walks
north and east, Side Gate → Exit East walks east and south, so the two streams meet <b>head-on</b> in corridors
1_3 and 2_4 and share 3_4. With <code>{"0_5": 1, "7_6": 1}</code> they hardly meet. Same idea as section 5: who goes
where decides where it gets crowded.
</details>
"""),
    form('''#@title 🎬 Animate your network (optional, ≈15 s) {display-mode: "form"}
display(mine.animate(every=3))'''),
    md("""
### Your network is a real PedNStream network
`make_network` wrote a folder `my_network/` with a `sim_params.yaml`, the file PedNStream reads. Everything
you set above is in it, plus defaults you can change (walking speed, densities, route-choice settings).
In **Part 4** you'll write such a file yourself and run PedNStream directly.
"""),
    form('''#@title ▶ Show my sim_params.yaml {display-mode: "form"}
print(open("my_network/sim_params.yaml").read())'''),
    md("""
---
## Take-away
* PedNStream tracks how many people are on each corridor. Every 10 s people **arrive** (arrival pattern),
  get a **destination** (OD weights), pick a **route** (distance, width, crowding) and **walk** at a speed
  set by the density.
* A corridor can pass only so many people per minute. Above that a **queue** forms and grows **backwards**.
* An OD weight sets **where** people want to go, not **how many** there are. Two OD patterns with the same
  totals can behave very differently: when routes **overlap** and walkers meet **head-on**, corridors jam.
* The same model runs a single corridor, a station and a city centre, and any network you can sketch.

➡ Next: **Part 2 · Playground**: change the OD weights, the demand, how much people avoid crowds and
the width of corridor 2_3 yourself. Then **Part 3 · Challenge**.
"""),
])

# =============================================================================
# 02 playground
# =============================================================================
write("02_playground.ipynb", [
    md(f"""
# Part 2 · Playground
Change any value in the form, press ▶, and compare. Each run simulates 50 minutes in under a second.
{MAP}
{HOW_TO}
"""),
    *setup("from pednstream_workshop import run, compare, compare_maps, playground", min_version="1.7.0"),
    form('''#@title 🎛️ **Playground**: set the values, then press ▶ {display-mode: "form"}
#@markdown ### OD weights (relative, per gate)
A_to_Platform_X = 1  #@param {type:"slider", min:0, max:5, step:0.5}
A_to_City_Exit_Y = 1  #@param {type:"slider", min:0, max:5, step:0.5}
B_to_Platform_X = 1  #@param {type:"slider", min:0, max:5, step:0.5}
B_to_City_Exit_Y = 1  #@param {type:"slider", min:0, max:5, step:0.5}
#@markdown ### Demand: people per 10 s at the peak of the rush
gate_A_peak = 40  #@param {type:"slider", min:0, max:80, step:5}
gate_B_peak = 40  #@param {type:"slider", min:0, max:80, step:5}
#@markdown ### Behaviour and infrastructure
beta_crowd_avoidance = 2  #@param {type:"slider", min:0, max:10, step:0.5}
width_of_corridor_2_3_m = 2  #@param {type:"slider", min:1, max:6, step:0.5}
#@markdown ### Keep this run to compare with the next ones?
save_as = ""  #@param {type:"string"}

def _share(a, b):
    return f"{a / (a + b):.0%} to X / {b / (a + b):.0%} to Y" if a + b else "both 0, so 50% / 50%"
print("Weights ask for   Gate A:", _share(A_to_Platform_X, A_to_City_Exit_Y), "   |   Gate B:", _share(B_to_Platform_X, B_to_City_Exit_Y))

res = run(
    od={"0_5": A_to_Platform_X, "0_6": A_to_City_Exit_Y, "1_5": B_to_Platform_X, "1_6": B_to_City_Exit_Y},
    demand={0: {"peak_lambda": gate_A_peak}, 1: {"peak_lambda": gate_B_peak}},
    route_choice={"beta": beta_crowd_avoidance},
    links={"2_3": {"width": width_of_corridor_2_3_m}},
)
_k = res.kpis(); _x, _y = _k["reached Platform X"], _k["reached City Exit Y"]
print(f"Simulation delivered: {_x / (_x + _y):.0%} of all arrivals at X / {_y / (_x + _y):.0%} at Y")
res.dashboard(); plt.show()
if "saved" not in globals():
    saved = {}
if save_as:
    saved[save_as] = res
display(compare({**saved, "this run": res}))'''),
    md("""
**Things to try**
* Find the **smallest change** to one OD weight that makes corridor 2_3 congested.
* Keep the weights at 50/50 overall, and find the **best** and **worst** way to divide them over the two gates. Is the delivered split still 50/50?
* Turn the Gate B peak up. When are people turned away? Does it depend on where they want to go?
* Set β to 0 and then 10. Which OD patterns are sensitive to route choice?
* Widen corridor 2_3. Does the worst corridor simply *move* somewhere else?

Use **save_as** to keep a run (e.g. `my best`) so it stays in the comparison table.

**Write down** your most surprising finding and the settings that produced it. You'll share it with the group.
"""),
    md("""
### Optional: live sliders
The cell below gives sliders that re-run the simulation **immediately** when you move them (no ▶ needed).
"""),
    form('''#@title ▶ Live sliders (optional) {display-mode: "form"}
playground()'''),
    form('''#@title 🎬 Animate the last playground run (optional, ≈20 s) {display-mode: "form"}
display(res.animate(every=4))'''),
])

# =============================================================================
# 03 challenge
# =============================================================================
write("03_challenge.ipynb", [
    md(f"""
# Part 3 · Challenge: event day from Centraal Station to Museumplein
{AMS_MAP}
A big open-air event starts on **Museumplein** and the trains bring thousands of visitors into
**Amsterdam Centraal**. Stewards on the platforms decide **how many people per minute** are let out of
the station towards the event. That is your first lever: **you design the arrival pattern** for the first hour.
Your second lever: stewards on **Stationsplein** can **close routes**, block by block.

The obvious way out is **Damrak**, past Madame Tussauds on the Dam: a *very* wide street (20 m),
so it looks like it can take anyone. But south of the Dam the crowd has to fit into much narrower
streets: **Rokin**, then **Vijzelstraat** towards the Museum Quarter. Other routes exist (Kalverstraat and
Leidsestraat, Nieuwezijds Voorburgwal and the canals), but they are longer. People choose their own
route (shorter, wider and emptier streets are more attractive), just like in Part 1, among **5 routes**.
All 5 start at Stationsplein, so stewards there can send people away from a route by closing its entrance.

### Rules
* You set the number of people per minute leaving the station for six 10-minute blocks (minute 0 to 60).
* For each of the 5 routes you decide, per 10-minute block, whether it is **open** or **closed**. Closing a
  route shuts the gate at its first street (in PedNStream: gate width 0), so nobody new can walk in; people
  already on it keep walking, and people in the station pick another open route. After minute 60 the last
  setting stays. At least one route must be open in every block.
* The simulation runs for **2 hours**. The shortest walk is about **3.3 km**, ≈ 41 minutes on empty streets;
  because people spread over several routes, the average trip on empty streets is about **50 minutes**.
* **Score = people who reach Museumplein − hours that people spend on the streets (person-hours).**
  Every visitor you deliver earns 1 point; every hour someone spends walking or waiting costs 1 point.
  So a visitor whose trip takes longer than an hour costs more than they bring in. With a 50-minute walk
  there is not much room for queueing! **Higher is better.**
* Post your best score on the leaderboard.
{HOW_TO}
"""),
    *setup("from pednstream_workshop import run, AMSTERDAM, arrival_plan, route_plan, show_routes", min_version="1.11.0"),
    md("""
## ▶ Step 2: load the Amsterdam tools and look at the 5 routes
Routes that share a street run side by side on this map. The route numbers are the ones you open and close below.
Keep the colours in mind: on your results, each of the most crowded streets is drawn in the colour of
**its route** and named with it ("Rokin · route 1"); grey means several routes share that street.
So you can see straight away which route a jam is on.
"""),
    code('''import pandas as pd
from pednstream_workshop import AMSTERDAM, arrival_plan, route_plan, routes, show_routes
show_routes(AMSTERDAM); plt.show()
display(routes(AMSTERDAM).drop(columns=["OD", "nodes"]))'''),
    form('''#@title 🎟️ **Your arrival plan**: set the values, then press ▶ {display-mode: "form"}
team_name = "my team"  #@param {type:"string"}
#@markdown People per minute let out of Centraal Station, for each 10-minute block of the first hour
minutes_00_10 = 300  #@param {type:"slider", min:0, max:900, step:30}
minutes_10_20 = 300  #@param {type:"slider", min:0, max:900, step:30}
minutes_20_30 = 300  #@param {type:"slider", min:0, max:900, step:30}
minutes_30_40 = 300  #@param {type:"slider", min:0, max:900, step:30}
minutes_40_50 = 300  #@param {type:"slider", min:0, max:900, step:30}
minutes_50_60 = 300  #@param {type:"slider", min:0, max:900, step:30}
#@markdown **Routes open per 10-minute block**: six digits, one per block (1 = open, 0 = closed).
#@markdown E.g. "000111" = closed in minutes 0-30, open from minute 30.
route_1_Damrak = "111111"  #@param {type:"string"}
route_2_Kalverstraat = "111111"  #@param {type:"string"}
route_3_Nieuwezijds_Voorburgwal = "111111"  #@param {type:"string"}
route_4_Oudezijds_Achterburgwal = "111111"  #@param {type:"string"}
route_5_Singel = "111111"  #@param {type:"string"}

plan = [minutes_00_10, minutes_10_20, minutes_20_30, minutes_30_40, minutes_40_50, minutes_50_60]
route_codes = [route_1_Damrak, route_2_Kalverstraat, route_3_Nieuwezijds_Voorburgwal,
               route_4_Oudezijds_Achterburgwal, route_5_Singel]
for i, code_ in enumerate(route_codes, start=1):
    if len(code_.replace(" ", "")) != 6 or set(code_.replace(" ", "")) - {"0", "1"}:
        raise ValueError(f"Route {i}: use six digits of 0 and 1, e.g. '111111' (you typed {code_!r})")
res = run(network_dir=AMSTERDAM, arrivals={0: arrival_plan(plan)}, open_routes=route_plan(*route_codes))
last_plan = res   # remembered for the animation below
k = res.kpis()
sent, arrived = k["total demand (people)"], k["reached Museumplein"]
hours = float(k["time spent inside (person-hours)"])
score = arrived - hours

if "plans" not in globals():
    plans = []
plans.append({"team": team_name, **{f"{10 * i}-{10 * i + 10}'": p for i, p in enumerate(plan)},
              "routes 1-5": " ".join(route_codes), "sent": sent, "arrived": arrived,
              "person-hours": round(hours), "score": round(score)})

print(f"🚆 Sent {sent:,} people   🎨 {arrived:,} reached Museumplein   ⏱ {hours:,.0f} person-hours on the streets")
print(f"   average trip: {60 * hours / max(sent, 1):.0f} min (empty streets: about 50 min)")
print(f"\\n   SCORE = {score:,.0f}\\n")
print(f"📋 Leaderboard line:  {team_name} | plan {plan} | routes {' '.join(route_codes)} | score {score:.0f}")
res.dashboard(f"{team_name}: {plan} people/min", flow=True); plt.show()
print("Your plans so far (best first):")
display(pd.DataFrame(plans).sort_values("score", ascending=False).reset_index(drop=True))'''),
    md("""
### 🎬 Watch your plan play out
Run your plan above first, then this cell. It replays the **last plan you ran**: the map shows how crowded
each street is, minute by minute, and the black line on the right shows where you are in time.
Press ▶ under the animation; use − / + to slow down or speed up. (Takes about a minute to draw.)
"""),
    form('''#@title 🎬 Animate your last plan {display-mode: "form"}
#@markdown Show one frame every ... simulated minutes (smaller = smoother but slower to draw)
minutes_per_frame = 2  #@param {type:"slider", min:0.5, max:5, step:0.5}
if "last_plan" not in globals():
    print("⚠️ Run your arrival plan (the 🎟️ cell above) first.")
else:
    display(last_plan.animate(every=max(1, round(minutes_per_frame * 6)), flow=True))'''),
    md("""
### Stuck? Hints (open one at a time)
<details><summary>Hint 1</summary>Look at the <i>In and out</i> plot. Does the red line (arrivals per minute)
follow your blue blocks, about 50 minutes later? When does it stop following them?</details>
<details><summary>Hint 2</summary>When too many people arrive at once, they wait somewhere. Where? Watch the
animation: which street fills up first, and where does the queue go next? Is it the wide Damrak?</details>
<details><summary>Hint 3</summary>Someone who leaves at minute 55 needs about 50 minutes on empty streets.
Do they make it before the end (minute 120)? What if they have to queue?</details>
<details><summary>Hint 4</summary>Your blocks don't have to be equal. A bigger group is fine as long as
the queue it causes clears quickly. Is there a moment in the hour when nobody comes after them?</details>
<details><summary>Hint 5</summary>Look at the route map: which routes end up in the same narrow street? Almost
everyone picks the route past the wide Damrak. What happens further on if fewer people start that way?</details>

---
### For coders (optional): let the computer search
A simple search in two steps. First try a few constant arrival rates, each with all routes open and with
one route closed for the whole hour. Then take the best and move each block up or down by 60, keeping any
change that improves the score. Each run takes about 4 s, so this takes **≈2 minutes**.
Can you beat it by hand, for example by closing routes only in some blocks? Can you write a better search?
"""),
    code('''def amsterdam_score(plan, open_routes=None):
    k = run(network_dir=AMSTERDAM, arrivals={0: arrival_plan(plan)}, open_routes=open_routes).kpis()
    return k["reached Museumplein"] - float(k["time spent inside (person-hours)"])

options = {"all open": [True] * 5}
for r in range(5):
    options[f"route {r + 1} closed"] = [i != r for i in range(5)]

trials = {(rate, name): amsterdam_score([rate] * 6, open_) for rate in [360, 480, 600] for name, open_ in options.items()}
(rate, name), best_score = max(trials.items(), key=lambda kv: kv[1])
best, open_routes = [rate] * 6, options[name]
print(f"step 1: {rate}/min with {name}, score {best_score:,.0f}")

for i in range(6):
    for change in (-60, 60):
        trial = best.copy()
        trial[i] = min(900, max(0, trial[i] + change))
        s = amsterdam_score(trial, open_routes)
        if s > best_score + 1:
            best, best_score = trial, s
print(f"step 2: plan {best} with {name}, score {best_score:,.0f}")'''),
    md("""
### Reflection
1. Describe your arrival plan in words a steward on the platform would understand.
2. Why does it work? Name the street that decides how many people per minute can reach Museumplein.
3. Damrak is 20 m wide. Did that help or hurt? What does a very wide street do to *where* people choose to walk?
4. Most people walk Damrak, Rokin and Vijzelstraat even when Vijzelstraat is packed and Kalverstraat is quiet.
   In PedNStream people choose at each junction from the distance and how wide and empty the *next* street is;
   they can't see a jam 2 km ahead. Would real visitors (with phones, or stewards) behave the same way?
5. Which routes did you close, and when? Closing a route takes a choice away from people. Why can that make
   the trip faster for everyone? Would you close the same routes in real life?
"""),
])

# =============================================================================
# 04 research
# =============================================================================
write("04_pednstream_in_your_research.ipynb", [
    md("""
# Part 4 · Using PedNStream in your own research

In Parts 1–3 a helper package hid PedNStream behind sliders. Here we use **PedNStream directly**,
the way you would in your own project: install it, describe a network in a YAML file, run it,
and analyse the results with normal Python tools (numpy, pandas, matplotlib).

You'll learn to:
1. install PedNStream in any project,
2. describe your **own network** in `sim_params.yaml`,
3. run a simulation and read out densities and flows,
4. change parameters from code, including your own demand pattern,
5. run a **parameter sweep**, the bread and butter of a research study,
6. save results and start from the workshop network.

This notebook has normal code cells. Read them, run them, and change them!
"""),
    md("""
## 1 · Install PedNStream
In your own project this one line is all you need. It installs PedNStream from GitHub, pinned to an
exact commit so your results stay reproducible. The extra packages are ones PedNStream uses but does
not yet install by itself. (You can ignore the note *"you may need to restart the kernel"*.)
"""),
    code(f'''%pip install -q "{PEDNSTREAM_PIP}" pyyaml pandas tqdm

import os, json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
plt.rcParams["figure.dpi"] = 90
os.makedirs("my_network", exist_ok=True)   # folder for the network we write next'''),
    md("""
## 2 · Describe a network
A PedNStream network is a **folder** with a `sim_params.yaml` file (and optionally `node_positions.json`
for plotting). Here's a small T-junction: people enter at node 0 and walk to node 2 (east) or node 3 (north).
The north corridor 1–3 is narrow.

```
            3  North exit
            |   (narrow, 1 m)
   0 ────── 1 ────── 2  East exit
 entrance
```

`%%writefile` saves the cell's text to a file. In a real project you would just edit the file.
"""),
    code('''%%writefile my_network/sim_params.yaml
network:
  adjacency_matrix: [        # 1 = a corridor between row-node and column-node
    [0, 1, 0, 0],            # node 0 - node 1
    [1, 0, 1, 1],            # node 1 - nodes 0, 2, 3
    [0, 1, 0, 0],            # node 2 - node 1
    [0, 1, 0, 0],            # node 3 - node 1
  ]
  origin_nodes: [0]
  destination_nodes: [2, 3]

simulation:
  seed: 1
  simulation_steps: 200      # 200 x 10 s = 33 min
  unit_time: 10              # seconds per step
  od_tracking: true          # each person keeps their destination all the way
  path_finder: {k_paths: 1}

default_link:                # every corridor gets these unless overridden
  length: 60                 # m
  width: 3                   # m
  free_flow_speed: 1.2       # m/s
  k_critical: 2              # ped/m2
  k_jam: 6                   # ped/m2

links:
  "1_3": {width: 1}          # the narrow north corridor

demand:
  origin_0: {pattern: "constant", base_lambda: 50}   # 50 people per step

od_flows:                    # relative OD weights, as in Parts 1-3
  "0_2": 1
  "0_3": 1'''),
    code('''positions = {"0": [0, 0], "1": [60, 0], "2": [120, 0], "3": [60, 60]}   # x, y in metres
with open("my_network/node_positions.json", "w") as f:
    json.dump(positions, f)
print(os.listdir("my_network"))'''),
    md("""
## 3 · Run it
Three steps: **load** the folder, **step** through time, **read** the results.
`network_loading(t)` advances the simulation by one time step.
"""),
    code('''from pednstream.utils.network_env_generator import NetworkEnvGenerator

gen = NetworkEnvGenerator()
net = gen.create_network("my_network", verbose=False)   # load the folder
T = gen.config["params"]["simulation_steps"]

for t in range(1, T):                                   # run the simulation
    net.network_loading(t)

print("Corridors (directed):", list(net.links))'''),
    md("""
## 4 · Read the results
Each directed corridor `(u, v)` is a `Link` object with numpy arrays over time:
`density`, `speed`, `inflow`, `outflow`, `num_pedestrians`, `cumulative_inflow`, `cumulative_outflow`, …
Put them in a pandas DataFrame and you can analyse them any way you like.
"""),
    code('''minutes = np.arange(T) * 10 / 60
density = pd.DataFrame({f"{u}→{v}": link.density[:T] for (u, v), link in net.links.items()
                        if link.density.max() > 0}, index=minutes)
density.index.name = "minute"

density.plot(figsize=(9, 3.5), ylabel="density (ped/m²)", title="Density per corridor")
plt.axhline(2, ls="--", c="grey"); plt.show()
density.describe().round(2)'''),
    md("""
## 5 · Change parameters from code
You don't need a new YAML file for every experiment. `create_network` accepts overrides:

| argument | changes | example |
|---|---|---|
| `od_flows` | OD weights | `{(0, 2): 1, (0, 3): 3}` |
| `link_params_overrides` | corridor properties | `{"1_3": {"width": 2}}` |
| `demand_params_overrides` | demand per origin | `{"origin_0": {"base_lambda": 80}}` |
| `custom_demand_functions` | your own demand pattern | see below |

A **custom demand pattern** is just a function that returns the number of arrivals per time step.
Its name becomes the `pattern` you refer to:
"""),
    code('''def evening_rush(origin_id, params):
    """10 people per step, with a rush of 70 between minutes 8 and 17."""
    t = np.arange(params["simulation_steps"] + 1)
    return np.where((t > 50) & (t < 100), 70, 10)

def simulate(**overrides):
    """Build a fresh network with the given overrides and run it to the end."""
    gen = NetworkEnvGenerator()
    net = gen.create_network("my_network", verbose=False, **overrides)
    for t in range(1, gen.config["params"]["simulation_steps"]):
        net.network_loading(t)
    return net

rush = simulate(custom_demand_functions=[evening_rush],
                demand_params_overrides={"origin_0": {"pattern": "evening_rush"}},
                od_flows={(0, 2): 1, (0, 3): 3})          # drawn 3:1 to the narrow north exit

plt.figure(figsize=(9, 3))
plt.plot(minutes, rush.nodes[0].demand[:T], label="arrivals at entrance", c="grey")
for (u, v) in [(0, 1), (1, 2), (1, 3)]:
    plt.plot(minutes, rush.links[(u, v)].num_pedestrians[:T], label=f"people on {u}→{v}")
plt.xlabel("minute"); plt.ylabel("people"); plt.legend(); plt.title("Evening rush, weights 3:1 for the north exit"); plt.show()'''),
    md("""
## 6 · A parameter sweep
Research questions are usually *"how does output Y change with input X?"*. Loop over X, collect Y
in a table, and plot it. Here: **how wide must the north corridor be** for a given share of people
going north?
"""),
    code('''rows = []
for share_north in [0.25, 0.5, 0.75]:
    for width in [0.5, 1, 1.5, 2, 3]:
        n = simulate(od_flows={(0, 2): 1 - share_north, (0, 3): share_north},
                     link_params_overrides={"1_3": {"width": width}})
        rows.append({
            "share north": share_north,
            "width 1_3 (m)": width,
            "peak density on 0→1": n.links[(0, 1)].density.max(),
            "peak density on 1→3": n.links[(1, 3)].density.max(),
            "person-hours inside": sum(l.num_pedestrians[:T].sum() for l in n.links.values()) * 10 / 3600,
        })
sweep = pd.DataFrame(rows)

for share, grp in sweep.groupby("share north"):
    plt.plot(grp["width 1_3 (m)"], grp["person-hours inside"], marker="o", label=f"{share:.0%} go north")
plt.xlabel("width of north corridor (m)"); plt.ylabel("person-hours inside"); plt.legend()
plt.title("How wide is wide enough?"); plt.show()
sweep.round(2)'''),
    md("""
**Try it:** add a third loop over `demand_params_overrides={"origin_0": {"base_lambda": ...}}`.
At what demand does even a 3 m corridor jam?

## 7 · Save results, or start from the workshop network
`OutputHandler` writes a run to JSON files, so you can analyse it later or share it:
"""),
    code('''from pednstream.utils.output_handler import OutputHandler

OutputHandler(base_dir="outputs", simulation_dir="evening_rush").save_network_state(rush)
print(os.listdir("outputs/evening_rush"))

saved = OutputHandler.load_simulation("outputs/evening_rush")
print("saved corridors:", list(saved["link_data"])[:4], "…")'''),
    md("""
PedNStream's own `NetworkVisualizer` can draw any saved run at any time step (and animate it with
`animate_network`):
"""),
    code('''import warnings
from pednstream.utils.visualizer import NetworkVisualizer
warnings.filterwarnings("ignore", category=RuntimeWarning)   # harmless arrow-drawing warning

vis = NetworkVisualizer(simulation_dir="outputs/evening_rush", pos=positions)
vis.visualize_network_state(time_step=90, edge_property="density");'''),
    md("""
The **Station Square** network from Parts 1–3 is also just a folder. Copy it and make it your own:
"""),
    code(f'''%pip install -q "{WORKSHOP_PIP}"
import shutil
from pednstream_workshop import DEFAULT_NETWORK

shutil.copytree(DEFAULT_NETWORK, "my_station", dirs_exist_ok=True)
print(open("my_station/sim_params.yaml").read()[:1200], "…")'''),
    md("""
## Where to go next
* **PedNStream on GitHub:** https://github.com/WaimenMak/PedNStream. Its `examples/` folder has bigger
  networks (a long corridor, a 9-node grid, Delft and Melbourne city centres).
* **Your own network:** draw it, number the nodes, write the adjacency matrix, and start with one
  origin and one destination before adding more.
* **Reproducibility:** pin the PedNStream version (as in the install cell), fix `seed`, and keep your
  `sim_params.yaml` under version control.
* Using PedNStream in a paper? Cite it: see `CITATION.cff` in the PedNStream repository.
"""),
])

print("Notebooks written to", OUT)
