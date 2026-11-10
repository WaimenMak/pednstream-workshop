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
PEDNSTREAM_PIP = "pednstream @ git+https://github.com/WaimenMak/PedNStream.git@65c2ff76767227983364e46eac519adf4c055087"

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


def setup_cell(imports: str) -> str:
    return f'''%pip install -q "{WORKSHOP_PIP}"

import matplotlib.pyplot as plt
{imports}
plt.rcParams["figure.dpi"] = 90
print("✅ Ready! Scroll down and continue.")'''


def setup(imports: str):
    """Markdown explanation plus the short, visible install cell."""
    return [md(SETUP_MD), code(setup_cell(imports))]


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


def predict_form(title, question):
    return form(f'''#@title ✋ **Predict first**: {title} {{ display-mode: "form" }}
#@markdown {question}
my_prediction = ""  #@param {{type:"string"}}
print("Saved your prediction:", my_prediction or "(empty, please type one above and run again)")''')


SCENARIOS = '''{
    "baseline (everyone 50/50)":        {"0_5": 1, "0_6": 1, "1_5": 1, "1_6": 1},
    "all to Platform X":                {"0_5": 1, "0_6": 0, "1_5": 1, "1_6": 0},
    "all to City Exit Y":               {"0_5": 0, "0_6": 1, "1_5": 0, "1_6": 1},
    "crossing (A to X, B to Y)":        {"0_5": 1, "0_6": 0, "1_5": 0, "1_6": 1},
    "parallel (A to Y, B to X)":        {"0_5": 0, "0_6": 1, "1_5": 1, "1_6": 0},
}'''

# =============================================================================
# 01 guided
# =============================================================================
write("01_od_weights_guided.ipynb", [
    md(f"""
# Part 1 · Where do people want to go?
### OD weights and how pedestrian flows spread through a network

You'll change **who wants to go where** in a small station and watch *where* and *when* crowds form.
Work in pairs: one person clicks, the other writes down predictions. Swap every exercise.

{HOW_TO}
"""),
    *setup("from pednstream_workshop import run, compare, compare_maps, switch"),
    md(f"""
## 0 · Meet *Station Square*
{MAP}
* **Two entrances** (green squares): West Gate **A** enters at the Plaza, South Gate **B** enters at the Hall.
* **Two destinations** (red diamonds): the **Platform X** and the **City Exit Y**.
* Corridor **2_3** (Plaza–Hall) is only **2 m** wide.
* A rush of people arrives at both gates, peaking around minute 17. The rush is **the same in every run**.
"""),
    form('''#@title What is an OD weight? Try it {display-mode: "form"}
#@markdown OD weights are **relative**. Set two weights for Gate A and see what share of Gate A's people goes where.
weight_A_to_Platform = 3  #@param {type:"slider", min:0, max:10, step:1}
weight_A_to_CityExit = 1  #@param {type:"slider", min:0, max:10, step:1}
total = weight_A_to_Platform + weight_A_to_CityExit
if total == 0:
    print("Both weights are 0. PedNStream then has no preference and falls back to 50% / 50%.")
else:
    pX = weight_A_to_Platform / total
    print(f"Of everyone entering at Gate A:  {pX:.0%} → Platform X,   {1 - pX:.0%} → City Exit Y")
    print("How MANY people enter is set by the gate's demand; the weights only split them.")
    plt.figure(figsize=(6, 1.2)); plt.barh([0], [pX], color="#1565c0"); plt.barh([0], [1 - pX], left=[pX], color="#ef6c00")
    plt.xlim(0, 1); plt.yticks([]); plt.title("Gate A: Platform X (blue) / City Exit Y (orange)"); plt.show()'''),
    md("""
> **Quick check:** weights 10 & 10 versus 1 & 1. Same result or different? Try it above.
"""),
    form('''#@title ▶ Run the baseline (all weights equal) {display-mode: "form"}
base = run()
base.dashboard("Baseline: every gate sends 50% to X and 50% to Y"); plt.show()
display(base.kpis().to_frame("baseline"))'''),
    md("""
**How to read this**
* **Map**: corridor colour = density (people per m²) at the busiest moment. Above **2** (dashed line) a corridor is *congested* and people slow down sharply.
* **Density per corridor**: when and where crowds build up and clear.
* **Arrivals**: people reaching each destination over time. *Turned away* = people who couldn't even enter because the first corridor was full.
* **time spent inside (person-hours)**: our main "how bad was it" number. **Lower is better.**

---
## Exercise 1 · Everyone to one destination
A train is delayed, and **everyone** heads to the Platform X. Or a concert is on in town and **everyone** heads to the City Exit Y.
"""),
    predict_form("Exercise 1", "Which corridor will be worst in each case? Which case is worse overall?"),
    form('''#@title ▶ Run Exercise 1 {display-mode: "form"}
all_x = run(od={"0_5": 1, "0_6": 0, "1_5": 1, "1_6": 0})
all_y = run(od={"0_5": 0, "0_6": 1, "1_5": 0, "1_6": 1})
display(compare({"baseline": base, "all to X": all_x, "all to Y": all_y}))
compare_maps({"baseline": base, "all to X": all_x, "all to Y": all_y}); plt.show()
print("How 'all to X' travellers split over their routes:")
display(all_x.route_split())'''),
    md("""
**Discuss**
1. In *all to X*, people are turned away at **Gate B**. Why B and not A? *(Hint: count B's routes to X in the table.)*
2. The narrow corridor 2_3 is *not* the worst. Where did the crowd go instead, and why?

---
## Exercise 2 · Same totals, different mix ⭐
Both scenarios send **exactly half** of all travellers to X and half to Y. Only *who* goes where differs:

| scenario | Gate A goes to | Gate B goes to |
|---|---|---|
| **crossing** | Platform X (east) | City Exit Y (north) |
| **parallel** | City Exit Y (north) | Platform X (east) |
"""),
    predict_form("Exercise 2", "Will the two scenarios give (almost) the same result? If not, which is worse, and where?"),
    form('''#@title ▶ Run Exercise 2 {display-mode: "form"}
crossing = run(od={"0_5": 1, "0_6": 0, "1_5": 0, "1_6": 1})
parallel = run(od={"0_5": 0, "0_6": 1, "1_5": 1, "1_6": 0})
display(compare({"baseline": base, "crossing": crossing, "parallel": parallel}))
compare_maps({"crossing": crossing, "parallel": parallel}); plt.show()
print("Crossing scenario, corridor by corridor:")
display(crossing.link_table())'''),
    md("""
**Discuss**
1. Destination totals are identical, yet one scenario costs much more. Explain why in one sentence, using *route overlap* or *counter-flow*.
2. Knowing only "50% go to the Platform", could you have predicted the congestion?

---
## Exercise 3 · Destinations that change over time
A train is announced, and from that moment people become much more likely to head to the Platform.
"""),
    predict_form("Exercise 3", "People already walking to the City Exit when the announcement comes: do they keep going or turn around? Does the timing of the announcement matter?"),
    form('''#@title ▶ Run Exercise 3 {display-mode: "form"}
announcement_minute = 25  #@param {type:"slider", min:0, max:49, step:1}
times_more_likely_to_go_to_Platform = 6  #@param {type:"slider", min:1, max:10, step:1}
step = int(announcement_minute * 6)       # 1 step = 10 s
k = times_more_likely_to_go_to_Platform
announce = run(od={"0_5": switch(1, k, at_step=step), "0_6": 1,
                   "1_5": switch(1, k, at_step=step), "1_6": 1})
ax = announce.plot_links(["0_2", "2_3", "3_5", "2_4", "4_6"], title=f"Announcement at minute {announcement_minute}")
ax.axvline(announcement_minute, color="k", lw=2, alpha=0.4); plt.show()
display(compare({"baseline": base, f"announced at min {announcement_minute}": announce}))'''),
    md("""
**Discuss**
1. Look at the vertical line. Do the corridors react with a delay, or all at once?
2. PedNStream applies the **current** OD weights at every junction, so people already inside "re-decide" at their next junction.
   Is that realistic for a loudspeaker announcement? For a departure board visible only at the entrance?
3. Try the announcement at minute **17** (the peak) and at minute **35**. Does *timing* matter as much as *size*?

---
## Exercise 4 · Do people dodge the jam?
People choose between two routes using **distance**, **crowding** and **width**.
**β (beta)** is how strongly people avoid crowds: 0 = they ignore crowding, 10 = they avoid it strongly.
"""),
    predict_form("Exercise 4", "For the bad crossing pattern, will people avoiding crowds (high β) fix the problem? Will a wider corridor?"),
    form(f'''#@title ▶ Run Exercise 4 {{display-mode: "form"}}
scenario = "crossing (A to X, B to Y)"  #@param ["baseline (everyone 50/50)", "all to Platform X", "all to City Exit Y", "crossing (A to X, B to Y)", "parallel (A to Y, B to X)"]
beta_crowd_avoidance = 8  #@param {{type:"slider", min:0, max:10, step:0.5}}
width_of_corridor_2_3_m = 2  #@param {{type:"slider", min:1, max:6, step:0.5}}
od = {SCENARIOS}[scenario]
default = run(od=od)
changed = run(od=od, route_choice={{"beta": beta_crowd_avoidance}}, links={{"2_3": {{"width": width_of_corridor_2_3_m}}}})
label = f"β={{beta_crowd_avoidance}}, 2_3 = {{width_of_corridor_2_3_m}} m"
display(compare({{"default (β=2, 2_3 = 2 m)": default, label: changed}}))
compare_maps({{"default": default, label: changed}}); plt.show()'''),
    md("""
**Discuss**
1. Raising β changes the *peak density* more than the *total time*. Why can't smart walkers fix a bad OD pattern on their own?
2. Which helps more here: better behaviour (β), a wider corridor, or a different OD mix (Exercise 2)?

---
## Wrap-up: complete these three sentences with your partner
1. An OD weight controls …
2. Two OD patterns with the same destination totals can behave differently because …
3. When OD weights change over time, the network …

➡ Next: **Part 2 · Playground**, then **Part 3 · Challenge**.
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
    *setup("from pednstream_workshop import run, compare, compare_maps, playground"),
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
    return f"{a / (a + b):.0%} to X / {b / (a + b):.0%} to Y" if a + b else "both 0, so PedNStream falls back to 50% / 50%"
print("Gate A:", _share(A_to_Platform_X, A_to_City_Exit_Y), "   |   Gate B:", _share(B_to_Platform_X, B_to_City_Exit_Y))

res = run(
    od={"0_5": A_to_Platform_X, "0_6": A_to_City_Exit_Y, "1_5": B_to_Platform_X, "1_6": B_to_City_Exit_Y},
    demand={0: {"peak_lambda": gate_A_peak}, 1: {"peak_lambda": gate_B_peak}},
    route_choice={"beta": beta_crowd_avoidance},
    links={"2_3": {"width": width_of_corridor_2_3_m}},
)
res.dashboard(); plt.show()
if "saved" not in globals():
    saved = {}
if save_as:
    saved[save_as] = res
display(compare({**saved, "this run": res}))'''),
    md("""
**Things to try**
* Find the **smallest change** to one OD weight that makes corridor 2_3 congested.
* Keep the overall split at 50/50, and find the **best** and **worst** way to divide it over the two gates.
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
# Part 3 · Challenge: you are the station manager
{MAP}
With signs, staff and app messages you can steer **which destination people from each gate head for**
(think *"Platform entrance via the South Gate"*). In model terms: **you choose the OD weights.**

### Rules
* Gate demand is fixed.
* The train company requires that **at least 60%** of all travellers are sent to the **Platform X**.
  Both gates are equally busy, so the **average** of your two shares must be **≥ 0.60**.
* **Score = time spent inside (person-hours) + 0.25 h for every person turned away. Lower is better.**
* Post your best valid score on the leaderboard.
{HOW_TO}
"""),
    *setup("from pednstream_workshop import run, compare, compare_maps"),
    form('''#@title 🏆 **Your strategy**: set the values, then press ▶ {display-mode: "form"}
team_name = "my team"  #@param {type:"string"}
share_of_Gate_A_sent_to_Platform = 0.6  #@param {type:"slider", min:0, max:1, step:0.05}
share_of_Gate_B_sent_to_Platform = 0.6  #@param {type:"slider", min:0, max:1, step:0.05}
#@markdown **Bonus round only**: widen one corridor by 2 m (leave at "none" for the main round)
upgrade = "none"  #@param ["none", "0_2", "1_3", "2_3", "2_4", "3_4", "3_5", "4_6"]

a, b = share_of_Gate_A_sent_to_Platform, share_of_Gate_B_sent_to_Platform
links = {}
if upgrade != "none":
    base_width = run().link(upgrade).width
    links = {upgrade: {"width": base_width + 2}}
res = run(od={"0_5": a, "0_6": 1 - a, "1_5": b, "1_6": 1 - b}, links=links)
k = res.kpis()
score = k["time spent inside (person-hours)"] + 0.25 * k["turned away at gates"]
valid = (a + b) / 2 >= 0.6 - 1e-9

if "attempts" not in globals():
    attempts = []
attempts.append({"team": team_name, "A→X": a, "B→X": b, "upgrade": upgrade,
                 "overall to X": f"{(a + b) / 2:.0%}", "valid": "✅" if valid else "❌", "score": round(float(score), 1)})

print(("✅ Valid strategy" if valid else "❌ BREAKS the 60% rule: this score does not count") +
      f"  (overall {(a + b) / 2:.0%} sent to the Platform)")
print(f"\\n   SCORE = {score:.1f}     (time inside {k['time spent inside (person-hours)']:.1f} h, turned away {k['turned away at gates']})\\n")
if valid:
    print(f"📋 Leaderboard line:  {team_name} | A→X {a:.2f} | B→X {b:.2f} | upgrade {upgrade} | score {score:.1f}")
res.dashboard(f"{team_name}: A→X {a:.0%}, B→X {b:.0%}"); plt.show()
import pandas as pd
print("Your attempts so far (best first):")
display(pd.DataFrame(attempts).sort_values(["valid", "score"], ascending=[False, True]).reset_index(drop=True))'''),
    md("""
### Stuck? Hints (open one at a time)
<details><summary>Hint 1</summary>Look at the map of your strategy: which corridors are red, and which OD groups walk through them?</details>
<details><summary>Hint 2</summary>Gate B has only <b>one</b> route to the Platform, and it shares nothing with Gate A's routes.</details>
<details><summary>Hint 3</summary>Remember Exercise 2: the crossing pattern was expensive, the parallel one was cheap.</details>

---
### For coders (optional): search systematically
Instead of guessing, scan every combination and draw a heat-map of the score. Edit and run the cell below.
"""),
    code('''import numpy as np
shares = np.round(np.arange(0, 1.01, 0.1), 1)
scores = np.full((len(shares), len(shares)), np.nan)
for i, a in enumerate(shares):
    for j, b in enumerate(shares):
        if (a + b) / 2 < 0.6 - 1e-9:
            continue                       # breaks the 60% rule
        k = run(od={"0_5": a, "0_6": 1 - a, "1_5": b, "1_6": 1 - b}).kpis()
        scores[i, j] = k["time spent inside (person-hours)"] + 0.25 * k["turned away at gates"]

plt.imshow(scores, origin="lower", cmap="viridis_r")
plt.xticks(range(len(shares)), shares); plt.yticks(range(len(shares)), shares)
plt.xlabel("share of Gate B to Platform"); plt.ylabel("share of Gate A to Platform")
plt.colorbar(label="score (lower is better)"); plt.title("Challenge score"); plt.show()
i, j = np.unravel_index(np.nanargmin(scores), scores.shape)
print(f"Best on this grid: A→X {shares[i]}, B→X {shares[j]}, score {scores[i, j]:.1f}")'''),
    md("""
### Reflection
1. Describe your winning strategy in words a station manager would understand.
2. Why does it work? Name specific corridors.
3. In the bonus round, did one wider corridor help more or less than a smart OD strategy?
4. Name one thing the model leaves out that could make your strategy fail in real life.
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
                od_flows={(0, 2): 1, (0, 3): 3})          # 75% want the narrow north exit

plt.figure(figsize=(9, 3))
plt.plot(minutes, rush.nodes[0].demand[:T], label="arrivals at entrance", c="grey")
for (u, v) in [(0, 1), (1, 2), (1, 3)]:
    plt.plot(minutes, rush.links[(u, v)].num_pedestrians[:T], label=f"people on {u}→{v}")
plt.xlabel("minute"); plt.ylabel("people"); plt.legend(); plt.title("Evening rush, 75% to the north exit"); plt.show()'''),
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
