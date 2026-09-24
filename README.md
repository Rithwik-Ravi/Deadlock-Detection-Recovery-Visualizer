# Deadlock Detection & Recovery - Resource Allocation Graph Visualizer

**Course Project — Operating Systems (Academic Milestone: Phase 1)**  
A modular, academically rigorous Python implementation of the **Multi-Instance Resource Deadlock Detection Algorithm** (Silberschatz, Galvin, and Gagne — *Operating System Concepts*).

---

## 📌 Project Overview

Deadlocks represent a critical failure state in multi-programmed operating systems where a set of concurrent processes are permanently blocked because each process holds resources and waits for others held by processes in the same set.

This project implements an end-to-end framework to:
1. Mathematically represent resource allocation states using vector and matrix representations ($Allocation$, $Request$, $Available$).
2. Detect whether the system is in deadlock using the multi-instance deadlock detection algorithm.
3. Trace every evaluation step deterministically (tracking the evolution of the $Work$ vector and $Finish$ array).
4. Provide structured, JSON-serializable payloads for seamless integration with upcoming graphical visualizers and recovery engines.

---

## 🚀 Project Roadmap

- [x] **Phase 1: Core Deadlock Detection Engine** *(Current Milestone)*
  - Mathematical state representation ($Allocation$, $Request$, $Available$).
  - Full multi-instance deadlock detection algorithm.
  - Comprehensive input validation & edge-case handling.
  - Granular step-by-step execution tracing.
  - Predefined demo scenarios (Safe, Deadlocked, Borderline Cascade, Circular Wait, Zero-Allocation).
  - Clean CLI runner with viva mode, interactive custom matrix entry, and JSON payload export.
  - Full automated unit test suite.

> [!NOTE]
> **Phase 2 & Phase 3 Status:**
> - **Phase 2: Add GUI and graph visualization** — *Not added yet, but will be soon.*
>   - Will feature a dynamic Resource Allocation Graph (RAG) visualizer highlighting deadlock cycles, process state transitions, and step-by-step playback.
> - **Phase 3: Add recovery strategies and compare costs** — *Not added yet, but will be soon.*
>   - Will feature automated process termination (abort all vs abort one-by-one) and resource preemption strategies with rollback cost metrics.

---

## 🔬 Theoretical Foundation

### Multi-Instance Resource Deadlock Detection Algorithm

Unlike systems with single instances of each resource type (which can be solved simply by cycle detection in a directed graph using DFS), systems with **multiple instances** of resource types require vector-matrix algebraic verification.

#### Input Data Structures:
- **$n$**: Number of processes ($P_0, P_1, \dots, P_{n-1}$)
- **$m$**: Number of resource types ($R_0, R_1, \dots, R_{m-1}$)
- **$Available[m]$**: Vector of length $m$. If $Available[j] = k$, there are $k$ instances of resource type $R_j$ currently available.
- **$Allocation[n \times m]$**: 2D matrix. If $Allocation[i][j] = k$, process $P_i$ currently holds $k$ instances of resource type $R_j$.
- **$Request[n \times m]$**: 2D matrix. If $Request[i][j] = k$, process $P_i$ is currently requesting $k$ more instances of resource type $R_j$.

#### Working Data Structures:
- **$Work[m]$**: Vector of length $m$, tracking available resources as hypothetical completions occur.
- **$Finish[n]$**: Boolean vector of length $n$, tracking whether process $P_i$ can finish.

#### Algorithm Steps:
1. **Initialization**:
   - $Work = Available$
   - For $i = 0, 1, \dots, n-1$:
     $$\text{If } Allocation[i] \neq \mathbf{0}, \text{ then } Finish[i] = \text{False}; \quad \text{otherwise, } Finish[i] = \text{True}$$
     *(Processes with zero allocation cannot contribute to a circular wait and are initialized as finished).*
2. **Candidate Search**:
   - Find an index $i$ such that:
     $$\text{both: } Finish[i] == \text{False} \quad \text{and} \quad Request[i] \le Work$$
     *(Where $Request[i] \le Work \iff \forall j \in [0, m-1], Request[i][j] \le Work[j]$).*
   - If no such $i$ exists, jump to **Step 4**.
3. **Resource Reclaim**:
   - Process $P_i$ is assumed to run to completion and release its resources:
     $$Work = Work + Allocation[i]$$
     $$Finish[i] = \text{True}$$
   - Record step trace and repeat from **Step 2**.
4. **Deadlock Determination**:
   - If $Finish[i] == \text{False}$ for any $i$ ($0 \le i < n$), the system is in **deadlock**.
   - Furthermore, any process $P_i$ where $Finish[i] == \text{False}$ is **deadlocked**.
   - If all $Finish[i] == \text{True}$, the system is **deadlock-free (safe)**.

---

## 📂 Project Architecture

```
OS Project/
├── deadlock_core.py      # Core DeadlockSystem class, validation, and detection logic
├── demo_scenarios.py     # Curated demo scenarios (Safe, Deadlocked, Borderline, etc.)
├── main.py               # Interactive CLI runner, viva stepper, and JSON exporter
├── test_deadlock.py      # Automated unit test suite (10 test cases)
├── requirements.txt      # Dependency specification (Standard library only for Phase 1)
└── README.md             # Comprehensive project documentation
```

### Module Responsibilities:

1. **`deadlock_core.py`**:
   - `DeadlockSystem`: Core class managing state, validation, detection, and trace printing.
   - `AlgorithmStep`: Dataclass capturing point-in-time snapshots of candidates, request vectors, work before/after, releases, and finish vector states.
   - `DetectionReport`: Complete structured summary with `.to_dict()` and `.to_json()` methods for GUI consumption.

2. **`demo_scenarios.py`**:
   - Pre-packaged benchmark scenarios with detailed viva notes and expected mathematical outcomes.

3. **`main.py`**:
   - Interactive terminal UI with colorized tables, step-by-step viva mode, live custom matrix input, and CLI arguments.

4. **`test_deadlock.py`**:
   - Complete automated test suite testing safe execution, circular waits, borderline cascades, edge conditions, invalid dimensions, and negative values.

---

## 🧪 Demonstration Scenarios (Viva Ready)

### 1. Safe Scenario (`safe`)
* **Context**: Standard Silberschatz benchmark with 5 processes ($P_0 \dots P_4$) and 3 resources ($A, B, C$).
* **Initial State**: $Available = [0, 0, 0]$.
* **Execution Flow**:
  - $P_0$ and $P_2$ have $Request = [0, 0, 0]$.
  - $P_0$ executes first $\implies Work$ becomes $[0, 1, 0]$.
  - $P_2$ executes next $\implies Work$ becomes $[3, 1, 3]$.
  - Under deterministic scan, $P_1$ ($Request = [2, 0, 2] \le [3, 1, 3]$) executes $\implies Work$ becomes $[5, 1, 3]$.
  - $P_3$ executes $\implies Work$ becomes $[7, 2, 4]$.
  - $P_4$ executes $\implies Work$ becomes $[7, 2, 6]$.
* **Outcome**: Deadlock-free. Safe sequence: $P_0 \to P_2 \to P_1 \to P_3 \to P_4$.

### 2. Deadlocked Scenario (`deadlocked`)
* **Context**: Identical to Scenario 1, except Process $P_2$ requests 1 additional instance of resource $C$ ($Request = [0, 0, 1]$).
* **Execution Flow**:
  - $P_0$ finishes and releases $[0, 1, 0] \implies Work = [0, 1, 0]$.
  - Remaining processes:
    - $P_1$ needs $2A, 2C$ (blocked)
    - $P_2$ needs $1C$ (blocked)
    - $P_3$ needs $1A$ (blocked)
    - $P_4$ needs $2C$ (blocked)
  - No further process can be satisfied.
* **Outcome**: **DEADLOCK DETECTED!** Deadlocked processes: $\{P_1, P_2, P_3, P_4\}$.

### 3. Borderline / Cascade Scenario (`borderline`)
* **Context**: 3 processes ($P_0, P_1, P_2$), 2 resources ($R_1, R_2$), minimal $Available = [0, 1]$.
* **Execution Flow**:
  - $P_0$ and $P_1$ are initially blocked.
  - Exactly one process ($P_2$, needing $[0, 1]$) can execute.
  - $P_2$ completes and releases $[1, 0] \implies Work = [1, 1]$.
  - This unlocks $P_0$ (needing $[1, 0]$), which releases $[1, 1] \implies Work = [2, 2]$.
  - This unlocks $P_1$ (needing $[2, 1]$).
* **Outcome**: Deadlock-free cascade: $P_2 \to P_0 \to P_1$.

### 4. Circular Wait (`circular`)
* **Context**: 2 processes, 2 resources. $P_0$ holds $R_0$ and requests $R_1$. $P_1$ holds $R_1$ and requests $R_0$. $Available = [0, 0]$.
* **Outcome**: Immediate deadlock with 0 processes able to finish. Deadlocked: $\{P_0, P_1\}$.

### 5. Zero-Allocation Edge Case (`zero_alloc`)
* **Context**: Process $P_0$ holds 0 resources.
* **Outcome**: Demonstrates Step 1b boundary condition handling where $Finish[P_0]$ is initialized to $\text{True}$ so non-resource-holding processes do not falsely trigger deadlock.

---

## 💻 How to Run

### Requirements
- **Python 3.8+**
- **Zero external dependencies** (uses only standard library `dataclasses`, `typing`, `copy`, `json`, `argparse`, `unittest`).

### Command-Line Usage

```bash
# 1. Open the Interactive CLI Menu
python main.py

# 2. Run all demo scenarios and print validation scorecard
python main.py --all

# 3. Run a specific scenario by identifier
python main.py --scenario safe
python main.py --scenario deadlocked
python main.py --scenario borderline
python main.py --scenario circular
python main.py --scenario zero_alloc

# 4. Interactive step-by-step mode (press Enter to advance each iteration)
python main.py --scenario borderline --step-by-step

# 5. Export JSON report payload (for Phase 2 GUI integration)
python main.py --scenario safe --json

# 6. Enter custom matrices interactively during viva
python main.py --custom
```

### Running the Automated Test Suite

```bash
python -m unittest test_deadlock.py -v
```

All 10 test cases validate matrix shapes, exception throwing on negative values, sequence determination, and JSON roundtrips.

---

## 📊 Sample Terminal Output

### Safe Case Trace Preview (`python main.py --scenario safe`)

```
----------------------------------------------------
Current Available Resources (Work)
----------------------------------------------------

A : 0
B : 0
C : 0

----------------------------------------------------

Checking Process P0...

Request:
A : 0
B : 0
C : 0

Current Work:
A : 0
B : 0
C : 0

Comparison:
A : 0 <= 0 ✓
B : 0 <= 0 ✓
C : 0 <= 0 ✓

Result:
✓ P0 CAN FINISH

----------------------------------------------------
P0 HAS FINISHED

Resources currently held by P0:
A : 0
B : 1
C : 0

Releasing resources...

Old Work:
A : 0
B : 0
C : 0

+

Released:
A : 0
B : 1
C : 0

=

New Work:
A : 0
B : 1
C : 0

P0 has released all of its resources back to the system.
----------------------------------------------------

Processes:
P0 ✓ Finished
P1 ⏳ Waiting
P2 ⏳ Waiting
P3 ⏳ Waiting
P4 ⏳ Waiting

Current Safe Sequence:
P0

...
----------------------------------------------------
All processes have successfully finished!

SYSTEM IS DEADLOCK-FREE (SAFE).

Final Safe Sequence:
P0
↓
P2
↓
P1
↓
P3
↓
P4

(Sequence: P0 -> P2 -> P1 -> P3 -> P4)
----------------------------------------------------
```

### Deadlocked Case Trace Preview (`python main.py --scenario deadlocked`)

```
Checking Process P1...

Request:
A : 2
B : 0
C : 2

Current Work:
A : 0
B : 1
C : 0

Comparison:
A : 2 <= 0 ✗
B : 0 <= 1 ✓
C : 2 <= 0 ✗

Result:
P1 CANNOT EXECUTE

Reason:
Resources A, C are insufficient.

----------------------------------------------------
No runnable process found.

Checking remaining processes...

P1 waiting for:
A = 2
Current A = 0
C = 2
Current C = 0

P2 waiting for:
C = 1
Current C = 0

P3 waiting for:
A = 1
Current A = 0

P4 waiting for:
C = 2
Current C = 0

Since no remaining request can be satisfied, the algorithm terminates.

DEADLOCK DETECTED.

Deadlocked Processes:
P1
P2
P3
P4
----------------------------------------------------
```

---

## 🔌 Phase 2 GUI Integration Interface

The `DeadlockSystem.detect_deadlock()` method returns a `DetectionReport` dataclass with a `.to_dict()` and `.to_json()` method. This payload provides everything needed for UI rendering:

```json
{
  "is_deadlocked": false,
  "safe_sequence": ["P0", "P2", "P1", "P3", "P4"],
  "deadlocked_processes": [],
  "initial_work": [0, 0, 0],
  "final_work": [7, 2, 6],
  "initial_finish": {"P0": false, "P1": false, "P2": false, "P3": false, "P4": false},
  "final_finish": {"P0": true, "P1": true, "P2": true, "P3": true, "P4": true},
  "steps": [
    {
      "step_number": 1,
      "process": "P0",
      "process_index": 0,
      "request": [0, 0, 0],
      "work_before": [0, 0, 0],
      "can_satisfy": true,
      "allocation_released": [0, 1, 0],
      "work_after": [0, 1, 0],
      "finish_snapshot": {"P0": true, "P1": false, "P2": false, "P3": false, "P4": false},
      "explanation": "Step 1: Process 'P0' has Request [0, 0, 0] <= Work [0, 0, 0]. Satisfied! Runs to completion and releases Allocation [0, 1, 0]. New Work = [0, 1, 0]."
    }
  ],
  "total_processes": 5,
  "total_resources": 3,
  "process_names": ["P0", "P1", "P2", "P3", "P4"],
  "resource_names": ["A", "B", "C"],
  "summary": "SYSTEM IS DEADLOCK-FREE (SAFE). All processes can run to completion."
}
```

This decoupled design guarantees that the visualizer in Phase 2 can consume this data structure directly without needing to touch or re-implement any algorithm logic.
