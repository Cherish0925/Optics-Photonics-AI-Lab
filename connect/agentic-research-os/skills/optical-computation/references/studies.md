# Parameter studies

**Sweep.** `submit_calculation` with `sweep` computes every point of a parameter set, in parallel within the configured capacity. `sweep` maps an input to its values: a list, or `{"start", "stop", "points"}` with `"scale": "log"` for logarithmic spacing. A dotted name sets one element of a list or object input and keeps the rest from `inputs` or, for a packaged program, from its default: `thickness_nm.0`, `n.1`, `layers.0.n`. `pairing: "product"` runs every combination; `"zip"` pairs the lists element by element. Each point `point-N` records its swept values. One process computes a group of points in turn, writing each to `point-N/` of its step and to `points.jsonl` as it finishes; by default there are about four groups per CPU slot, so a program of milliseconds does not pay a process start per point while long programs still fill every slot. `chunk` sets the points per process; `chunk: 1` makes every point a step of its own.

```json
{"tool": "tmm", "action": "spectrum", "inputs": {"n": [1, 1.38, 1.52], "wavelength_nm": [550]},
 "sweep": {"thickness_nm.0": {"start": 50, "stop": 150, "points": 21}, "n.1": [1.30, 1.38, 1.46]}}
```

**Table.** `sweep_results(run_id, values=["first.1"], minimize="first.1")` returns each point's swept inputs, state and the named RESULT values, including the finished points of a group still running, (dotted paths such as `checks.energy_error`, `R.0`, `mean.R`), and the best point; equal values keep the earliest point. A failed point keeps its error. `save=true` writes `sweep.npz/.json` in the run folder: on a full product the arrays are gridded over the swept inputs (axes in alphabetical order of their names), otherwise listed by point. Read them with `read_array(run_id, "sweep.npz", member=...)`.

**Refine.** Submit another sweep with `run_id` to append points to the same run, for example a finer range around the best point. Its points continue the numbering, and `sweep_results` covers all of them; a point missing a swept input takes it from its inputs or the program default.

**Optimize.** `optimize` searches inputs inside one process, so each evaluation costs only the calculation, and a commercial solver keeps one session:

```json
{"tool": "tmm", "action": "spectrum",
 "inputs": {"n": [1, 1.38, 2.1, 1.52], "thickness_nm": [100, 100], "wavelength_nm": {"start": 450, "stop": 650, "points": 21}},
 "optimize": {"variables": {"thickness_nm.0": [0, 300], "thickness_nm.1": [0, 300]}, "minimize": "mean.R", "evaluations": 600}}
```

`variables` maps an input or element to `[low, high]` or `{"low", "high", "scale": "log", "integer": true}`; `minimize` or `maximize` names a number in RESULT. `method` is `differential-evolution` (default: a global population search followed by a Nelder–Mead polish) or `nelder-mead` (local, from the current inputs). `evaluations` bounds the work (default 100 per variable plus 100) and `seed` makes it repeatable. The step's result gives the best variables, the objective, the RESULT of the best evaluation and the number of evaluations and failures; `best/` holds the files of the best evaluation, `history.jsonl` grows with every evaluation and `history.npz` has the objective, the best value so far and each variable per evaluation. A failed evaluation is treated as infinitely bad and recorded. `sweep` and `optimize` combine: each point then runs its own optimization, for example from several starting regions or for each wavelength.

Command line: `optics-photonics submit TOOL NAME --sweep JSON --pairing zip --chunk N --run-id RUN`, `optics-photonics run TOOL NAME --optimize JSON`, `optics-photonics sweep RUN --value PATH --minimize PATH --save`.
