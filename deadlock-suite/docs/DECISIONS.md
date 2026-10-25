# Architectural and Design Decisions (DECISIONS.md)

**Project**: Deadlock Detection & Recovery: Resource Allocation Graph Visualizer  
**Course**: Operating Systems (BCSE303L)  
**Authors**:
- Sri Krishna (24BCE2630)
- Rithvik Ravi (24BCE2254)
- Aditya (24BCE2242)

---

### Decision 1: Scan Order & Deterministic Rescan Behavior
- **Context**: The Silberschatz et al. multi-instance detection algorithm searches for an unsatisfied process $i$ whose request can be satisfied by current Available Work ($Request[i] \le Work$).
- **Choice**: When searching, we always evaluate processes in increasing index order ($0, 1, \dots, n-1$). Whenever any process finishes and releases its allocated resources to Work, the algorithm immediately rescans from index $0$.
- **Rationale**: Monotonicity guarantees that whenever Work increases, previously unsatisfied lower-indexed processes may now be satisfiable. Rescanning from index 0 guarantees deterministic safe sequences across all platforms and test suites.

---

### Decision 2: Zero-Allocation Process Handling
- **Context**: Processes may be instantiated with zero allocated resources across all types ($Allocation[i] = [0, \dots, 0]$), yet have positive requests.
- **Choice**: `Finish[i]` is initialized to `True` during Phase 1 detection.
- **Rationale**: Silberschatz et al. explicitly define $Finish[i] = \text{true}$ if $Allocation[i] == 0$. A process holding nothing cannot cause or contribute to a circular wait by blocking other processes. However, during DLR's augmented repayment verification, lenders whose allocation was temporarily reduced to 0 are explicitly tracked in `active_procs` so that the repayment router formally validates that they can be repaid and finish.

---

### Decision 3: Cycle Detection via Tarjan's Strongly Connected Components
- **Context**: In multi-instance resource systems, wait-for graphs can contain multiple overlapping dependencies. Visual highlighting requires identifying concrete deadlock cycles.
- **Choice**: We construct the directed wait-for graph among blocked processes and apply Tarjan's SCC algorithm. For each non-trivial SCC, a DFS back-edge traversal extracts an elementary cycle.
- **Rationale**: Tarjan's algorithm runs in linear time $O(V + E)$ and isolates independent deadlocked components without exponential explosion.

---

### Decision 4: Vendored D3.js v7 Without External CDN Dependency
- **Context**: Academic evaluation environments and offline labs often restrict internet access or have firewalls blocking CDNs.
- **Choice**: D3.js v7 is fully vendored at `web/vendor/d3.v7.min.js` and served directly by the FastAPI backend.
- **Rationale**: 100% offline portability and instant load times with zero external network dependencies.

---

### Decision 5: Cross-Platform Windows CLI Unicode Compatibility
- **Context**: Default Windows console code pages (e.g. CP1252) raise `UnicodeEncodeError` when emitting Unicode characters (such as box drawing or Unicode checkmarks).
- **Choice**: In `main.py`, standard output is reconfigured to UTF-8 on startup, and terminal output uses ASCII-compatible indicators (`[OK]`, `[X]`, `---`) with rich formatting.
- **Rationale**: Prevents crashes across various command prompts, PowerShell, and IDE embedded terminals.

---

### Decision 6: DLR Lend Plan Solvers (Exact vs. Greedy)
- **Context**: Finding the minimum-cost unit lend plan over combinations of $(i, j)$ pairs is an NP-hard multidimensional knapsack-style problem.
- **Choice**: If total lendable units $\le 14$, DLR uses iterative deepening with branch-and-bound lower bounding to guarantee unit minimality. If total units $> 14$, DLR activates a greedy heuristic that maximizes $(\Delta + 0.1) / \text{cost}$, followed by a backward minimality pruning pass.
- **Rationale**: Guarantees optimal unit minimality for common benchmark sizes while scaling smoothly to large systems without stalling.
