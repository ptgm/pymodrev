## pymodrev: A python Model Revision tool for Boolean logical models

**pymodrev** is a Python-based reimplementation of [ModRev](https://github.com/FilipeGouveia/ModRev), a tool for automated **consistency checking** and **repair** of Boolean network models using **Answer Set Programming (ASP)**. Given a Boolean model and a set of experimental observations (steady-state or time-series), pymodrev determines whether the model explains the data. If inconsistencies are found, it identifies **minimal repair operations** to fix the model.

Built on top of the [Clingo](https://potassco.org/clingo/) ASP solver and the [`pyfunctionhood`](https://github.com/ptgm/pyfunctionhood) library, pymodrev brings modern usability and extensibility to the model revision process by offering:

* ✅ **Full parity with [ModRev](https://filipegouveia.github.io/ModRev/)'s core logic**, using the same ASP encodings
* ✅ **Modular architecture** with pluggable update policies (synchronous, asynchronous, complete, steady-state)
* ✅ **Pure Python interface**, ideal for integration with scientific workflows
* ✅ **In-memory model and observation management**, enabling multiple consistency checks without reloading
* ✅ **Command-line interface** for batch processing and reproducibility

---
### Install

You can install **pymodrev** directly from source or via PyPI.

To install from source (when you are inside the pymodrev directory):
```bash
$ pip install .
```

To install from PyPI:
```bash
$ pip install pymodrev
```

This will automatically install dependencies like `bitarray`, `pyfunctionhood`, and `clingo`.

---

### Getting Started

Boolean models can be specified using the following formats:

* `.lp` - using original [ModRev](https://filipegouveia.github.io/ModRev/) ASP encoding
* `.bnet` - using the BoolNet format (only boolean rules)
* `.ginml` / `.zginml` - using the widely used GINsim format (conserving the model layout information)

To run **pymodrev**, use the following command structure:

```bash
$ pymodrev -h
```
```bash
usage: pymodrev [-h] -m MODEL -obs OBS [UPDATER ...] -t {c,r,m}
               [--exhaustive-search] [-s {1,2,3,4}] [-f {c,j,h}] [-d]

options:
  -h, --help            show this help message and exit
  -m, --model MODEL     Input model file.
  -obs, --observations OBS [UPDATER ...]
                        List of observation files and updater pairs.
                        Each observation must be followed by its updater type. 
                        Example: -obs obs1.lp asyncupdater obs2.lp syncupdater
  -t, --task {c,r,m}    Specify the task to perform (default=r):
                           c - check for consistency
                           r - get repairs
                           m - get repaired models
  --exhaustive-search   Force exhaustive search of function repair operations (default=false).
  -s, --solutions {1,2,3,4}
                        Number/Type of solutions presented (default=3).
                        All solutions are optimal w.r.t. number of nodes needing repairs.
                        A solution may be sub-optimal w.r.t. number of repair operations.
                            1 - Show only the first ASP optimal solution, which may be 
                                sup-optimal in terms of repairs (fastest)
                            2 - Show first optimal solution found
                            3 - Show all optimal solutions
                            4 - Show all optimal solutions, including sub-optimal repairs
  -f, --format {c,j,h}  Specify output format (default=h):
                            c - compact format
                            j - json format
                            h - human-readable format
  -d, --debug           Enable debug mode.
```


---

### Observation Formats

Experimental observations can be provided in `.lp` (ASP facts), `.csv`, `.xls`, or `.xlsx` formats.

#### Excel (or CSV) Formats
The tool automatically detects steady-state vs. time-series formats based on the header structure:

- **Steady-state**: The header has one empty first field. The first column contains profile names, followed by node values.
  ```csv
  ,node1,node2,node3
  p1,0,1,0
  p2,1,1,1
  ```
- **Time-series**: The header has two empty first fields. The first column contains profile names, the second column contains time steps, followed by node values.
  ```csv
  ,,node1,node2,node3
  p1,0,0,1,1
  p1,1,1,1,0
  p1,2,*,0,0
  ```
  > [!TIP]
  > Missing values (empty fields, `*`, `N/A`, `NaN`, `-`) are automatically skipped, ensuring no inconsistent constraints are generated for those variables at those time points.

---

#### Example: check consistency

Using option `-t c`, `pymodrev` will report the minimal set of nodes that need to be repaired in order to make the model consistent with the given observations.

```bash
$ pymodrev -m examples/boolean_cell_cycle/03/model.bnet -obs examples/boolean_cell_cycle/03/steadystate.lp steadystateupdater -t c
```
```bash
This network is inconsistent!
  node(s) needing repair: "p27", "rb", "cdc20", "cycd"
  present in profile(s): "p1"
```

#### Example: get repairs

Using option `-t r`, `pymodrev` will report the minimal set of repair operations for the model to be consistent with the given observations.

```bash
$ pymodrev -m examples/boolean_cell_cycle/03/model.bnet -obs examples/boolean_cell_cycle/03/steadystate.lp steadystateupdater -t r
```
```bash
### Found solution with 4 repair operations.
	Inconsistent node p27.
		Repair #1:
			Change function of p27 to: (cyca && !cycb && cycd && !p27) || (!cycb && !cyce)
	Inconsistent node rb.
		Repair #1:
			Change function of rb to: (!cycb && cycd && !p27) || (!cycb && cycd && cyce) || (!cycb && !cyca)
	Inconsistent node cdc20.
		Repair #1:
			Flip sign of edge (cycb,cdc20) to: positive
	Inconsistent node cycd.
		Repair #1:
			Flip sign of edge (cycd,cycd) to: positive
```

#### Example: get repaired models

Using option `-t m`, `pymodrev` will apply the repairs to the model and write to disk the repaired models consistent with the given observations.

```bash
$ pymodrev -m examples/boolean_cell_cycle/03/model.bnet -obs examples/boolean_cell_cycle/03/steadystate.lp steadystateupdater -t m
```
Repaired models keep the original name followed by a number, representing the number of minimal alternative repairs.
For example, one could have:

* `model_1.bnet ... model_2.bnet`, if there were only two possible minimal repaired models.
* `model_01.bnet ... model_18.bnet`, if there were eighteen possible minimal repaired models.

---

### Contributors
* Filipe Gouveia ([https://github.com/FilipeGouveia](https://github.com/FilipeGouveia))
* Antonio Romeu ([https://github.com/antonioromeu](https://github.com/antonioromeu))
* Pedro T. Monteiro ([https://github.com/ptgm](https://github.com/ptgm))
