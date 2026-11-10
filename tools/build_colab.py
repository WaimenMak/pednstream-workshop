"""Build the self-contained Google Colab notebooks in colab/.

Each notebook's first (hidden) cell installs PedNStream and writes
workshop_tools.py + the network files, so a notebook works on its own:
open it from GitHub, Drive, or by uploading it. No clone needed.

Re-run after editing workshop_tools.py or the network:
    python tools/build_colab.py
"""

from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "colab"

# Pin the exact PedNStream version the workshop was tested with.
PEDNSTREAM_REF = "d7ecbda107eca41feb3844985bb22e736b06dbe2"
PEDNSTREAM_PIP = f"git+https://github.com/WaimenMak/PedNStream.git@{PEDNSTREAM_REF}"

EMBEDDED = {
    "workshop_tools.py": (ROOT / "workshop_tools.py").read_text(),
    "networks/station_square/sim_params.yaml": (ROOT / "networks/station_square/sim_params.yaml").read_text(),
    "networks/station_square/node_positions.json": (ROOT / "networks/station_square/node_positions.json").read_text(),
}

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


def setup_cell(imports: str) -> str:
    return f'''#@title ▶ **Run me first**: set up the workshop (≈30 s) {{ display-mode: "form" }}
#@markdown Installs PedNStream and the workshop files. Run it again if Colab restarted.
import importlib, os, subprocess, sys

_FILES = {EMBEDDED!r}

for _path, _text in _FILES.items():
    os.makedirs(os.path.dirname(_path) or ".", exist_ok=True)
    with open(_path, "w") as _f:
        _f.write(_text)

try:
    import pednstream  # noqa: F401
except ImportError:
    print("Installing PedNStream …")
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "{PEDNSTREAM_PIP}"], check=True)
    importlib.invalidate_caches()

if "workshop_tools" in sys.modules:
    importlib.reload(sys.modules["workshop_tools"])

import matplotlib.pyplot as plt
plt.rcParams["figure.dpi"] = 90
{imports}
_ok = run()
print("✅ Ready! Scroll down and continue.")'''


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
write("01_od_weights_guided_colab.ipynb", [
    md(f"""
# Part 1 · Where do people want to go?
### OD weights and how pedestrian flows spread through a network

You'll change **who wants to go where** in a small station and watch *where* and *when* crowds form.
Work in pairs: one person clicks, the other writes down predictions. Swap every exercise.

{HOW_TO}
"""),
    form(setup_cell("from workshop_tools import run, compare, compare_maps, switch")),
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
write("02_playground_colab.ipynb", [
    md(f"""
# Part 2 · Playground
Change any value in the form, press ▶, and compare. Each run simulates 50 minutes in under a second.
{MAP}
{HOW_TO}
"""),
    form(setup_cell("from workshop_tools import run, compare, compare_maps, playground")),
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
write("03_challenge_colab.ipynb", [
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
    form(setup_cell("from workshop_tools import run, compare, compare_maps")),
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

print("Colab notebooks written to", OUT)
