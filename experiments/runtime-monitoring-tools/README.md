# Runtime Monitoring with NuRV & RTAMT

A compact toolkit to **monitor temporal properties** of a tool‑tip trajectory and surgical context signals. The monitoring engines are implemented in **high‑performance C** for speed; a small amount of **Python** is used only as the front‑end glue for starting monitors, streaming traces, and printing concise timing/verdict summaries.

---

## Data: `data/tool_tip_simulation_augmented.csv`

A single CSV trace drives all experiments. Each row is one discrete time step with **six columns**:

```
x, y, z, inCameraView, suturing, gauze
<int>,<int>,<int>,     <0|1>,        <0|1>,    <0|1>
```

- `x, y, z` — integer tool‑tip coordinates.
- `inCameraView` — `1` when the tool is inside the camera view; `0` otherwise.
- `suturing` — `1` when suturing is ongoing; else `0`.
- `gauze` — `1` when gauze is present/visible; else `0`.

Every driver reads all six columns (even if a particular property only uses a subset).

---

## What’s an `.smv` model?

NuRV consumes **SMV** models to declare the monitored variables and the **LTL** property to check. Typical structure:

```smv
MODULE main
VAR
  <signals declared here>  -- booleans or bounded integers
LTLSPEC
  <temporal formula>       -- future or past LTL, depending on the model
```

Monitors are built from these specs and evaluated on the CSV trace either **online** (live heartbeats) or **offline** (batch verification over a converted XML trace).

---

## Models (NuRV/models)

Common files you will find (names may vary slightly depending on your branch):

- **Camera view**
  - `instruments_future.smv` — `G(inCameraView)` (future‑time)
  - `instruments_past.smv`   — `H(inCameraView)` (past‑time)

- **Not‑stopping for 100 steps** (uses `x,y,z`)
  - `not_stopping_future.smv` — future‑time variant
  - `not_stopping_past.smv`   — past‑time variant

- **Suturing × Gauze rules**
  - `instruments_suture_once_future.smv` — `G( ¬( gauze U ( suturing ∧ gauze ) ) )`
  - `instruments_suture_once_past.smv`   — `H( ¬( suturing ∧ ( gauze S gauze ) ) )`
  - `suture_once_past.smv`               — older past‑time variant

> **Convention:** `_future.smv` uses future LTL (`G, F, X, U, R`). `_past.smv` uses past LTL (`H, Y, O, S, Z`).

---

## Drivers

All drivers print:
- **Wall‑clock runtime** of the monitoring phase,
- **Max per‑step latency** (worst processing time between two consecutive steps) with the corresponding step index,
- **First violation** (step & time) or a ✓‑message when satisfied.

### A) Online (NuRV heartbeat) — `NuRV/monitor_*_nurv_online.py`

- `monitor_one_tool_nurv_online.py` — camera view (`inCameraView`), future‑time model.  
- `monitor_not_stopping_nurv_online.py` — 100‑step non‑stop (uses `x,y,z`).  
- `monitor_suturing_gauze_nurv_online.py` — suturing × gauze formula.

**How to run (two terminals):**

**Terminal A (root privileges for the ORBit2 name server):**
```bash
sudo orbit-name-server-2
cd NuRV
sudo ./NuRV_orbit -int models/<model>.smv
# In the NuRV prompt:
NuRV > go
NuRV > build_monitor -n 0
NuRV > monitor_server -N IOR:...
```

**Terminal B (Python environment):**
```bash
cd NuRV
python monitor_one_tool_nurv_online.py \
  -ORBInitRef NameService=IOR:<paste‑IOR‑from‑Terminal‑A> \
  ../data/tool_tip_simulation_augmented.csv
```

Swap the Python script and the SMV model to target other properties:
- Non‑stop: `monitor_not_stopping_nurv_online.py` + `models/not_stopping_future.smv`
- Suturing×Gauze: `monitor_suturing_gauze_nurv_online.py` + `models/instruments_suture_once_future.smv`

### B) Offline (NuRV batch) — `NuRV/monitor_*_nurv_local_*.py`

These front‑ends convert CSV → NuRV XML trace, create a transient `offline.cmd`, invoke the **`NuRV`** batch binary once, and parse verdict lines.

**Future‑time example:**
```bash
cd NuRV
python monitor_one_tool_nurv_local_future.py \
  models/instruments_future.smv \
  ../data/tool_tip_simulation_augmented.csv
```

**Past‑time example (ptLTL):**
```bash
cd NuRV
python monitor_one_tool_nurv_local_past.py \
  models/instruments_past.smv \
  ../data/tool_tip_simulation_augmented.csv
```

**Suturing × gauze (past):**
```bash
cd NuRV
python monitor_suturing_gauze_nurv_past.py \
  models/instruments_suture_once_past.smv \
  ../data/tool_tip_simulation_augmented.csv
```

> Batch runs rely on the `NuRV` binary in `NuRV/`. If your executable names differ, adjust `NURV_CMD` at the top of each driver.

### C) RTAMT — `RTAMT/monitor_*_rtamt.py`

- `monitor_not_stopping_rtamt.py` — non‑stop (ptSTL).  
- `monitor_one_tool_rtamt.py` — camera view temporal rule.  
- `monitor_suturing_gauze_rtamt.py` — suturing × gauze property.

**Run:**

```bash
cd RTAMT
python monitor_not_stopping_rtamt.py ../data/tool_tip_simulation_augmented.csv
python monitor_one_tool_rtamt.py      ../data/tool_tip_simulation_augmented.csv
python monitor_suturing_gauze_rtamt.py ../data/tool_tip_simulation_augmented.csv
```

---

## Output format

All drivers produce at least:
```
Max per‑step time: <milliseconds> ms at step <k>
▶ Wall‑clock runtime: <seconds> s
✔ No violation found.
```
or, on violation:
```
✘ Violation at step <k> (wall‑clock time = <seconds> s)
```

---

## Tips & troubleshooting

- **Choose the right back‑end:** use `_future.smv` with standard `verify_property`; use `_past.smv` with `-r` for ptLTL (past‑time) verification.
- **CSV integrity:** ensure all six columns are present per row; non‑numeric `x,y,z` rows are skipped by the XML converter.
- **Timing:** online drivers start timing at the first `heartbeat()`; offline drivers measure the NuRV batch run plus verdict streaming; both track **worst per‑step latency**.
- **IOR:** the CORBA IOR string from `monitor_server` must be passed verbatim to the online Python clients.
- **Bounded integers:** when declaring integer variables in SMV, prefer bounded domains to avoid BDD blow‑ups.

---

## License

See `LICENSE` (if present). Otherwise, treat this repository as internal research code.
