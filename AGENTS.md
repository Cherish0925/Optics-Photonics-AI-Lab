# Working on this repository

For agents and people who change the repository. To use the environment, start at [README.md](README.md) or [llms.txt](llms.txt); source rules for catalogue entries are in [CONTRIBUTING.md](CONTRIBUTING.md), open work in [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

## Map

| Path | Holds |
| --- | --- |
| `src/optics_photonics/` | The connector, standard library only. `catalogue` search · `environments` recipes and bindings · `routes`, `native`, `languages` installed software · `jobs`, `execution`, `worker` runs · `studies`, `optimization`, `sampling` · `data`, `arrays`, `pictures` · `materials` · `mcp`, `cli` |
| `src/optics_photonics/programs/TOOL/NAME.*` | Packaged programs, one file each |
| `data/` | Catalogue in English and Chinese, connections (recipes and routes), domains, vocabulary of search |
| `skills/` | Two Skills and their references; the MCP server serves the same files as guides |
| `tests/`, `scripts/`, `clients/typescript/`, `native/executor/` | Cases, generators and platform runs, TypeScript client, Rust process executor |
| `docs/` pages and catalogues, `llms*.txt`, `data/resources.*`, `data/manifest.json`, `connect/agentic-research-os/` | Generated. Change the source and regenerate |

## Commands

```sh
python -m unittest discover -s tests              # OPTICS_SCIENCE_TESTS=1 adds the cases that run scientific libraries
python scripts/build.py                           # after data/, programs or the route table change
python scripts/package_marketplace.py             # after src/ or skills/ change
python scripts/check_recipes.py --programs TOOL   # install a recipe and run its packaged programs
```

Generated files are committed; the workflows compare them with a fresh build.

## Adding

- **A packaged program.** A docstring with a one-line title, then the physics, the conventions and what the result is compared with. A `PROGRAM` dictionary: every input with its default and meaning, `results`, `checks`. `p = parameters(PROGRAM, INPUTS)`; arrays through `data.save` with units and axes; `RESULT` with `checks` against a conservation law, an analytic limit or a second solver. Run it in the tool's own environment before committing, and list it in `skills/optical-computation/references/programs.md` and the two README tables. A program in another language declares the same in its leading comment (`languages.declaration`).
- **A catalogue entry.** The same `id` in both catalogue files, a record in `data/connections.json` with a pinned recipe or its routes, and a primary source for every claim.
- **A domain.** `data/domains.*.json`, the list in `data/schema.json`, `skills/optical-research/references/ID.md` and its line in the research Skill.
- **An MCP tool or argument.** `TOOLS` and `invoke` in `mcp.py`, the command in `cli.py`, the TypeScript client, and the guide that explains it. The descriptions of all tools sit in every session: keep each as short as it can be.

## Conventions

- The connector imports no third-party package and runs on Python 3.10+ on Windows, macOS and Linux. Scientific libraries are imported only by programs and by code that runs in a tool's environment.
- Text an agent reads (tool descriptions, guides, results, errors) is short, uses the names of the code, and says what to do next; an error names the accepted values.
- Units belong to names (`wavelength_um`); sign and time conventions are stated where a phase matters.
- A document claims what has run. Say whether something ran on the real software, on a stand-in, or not yet.
- English and Chinese documents change together.
- One topic per commit, subject in the imperative.
