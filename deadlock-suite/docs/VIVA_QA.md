# Operating Systems (BCSE303L) Viva Voce Guide & Question Bank

**Course**: Operating Systems (BCSE303L)  
**Project**: Deadlock Detection & Recovery: Resource Allocation Graph Visualizer  
**Authors**:
- Sri Krishna (24BCE2630)
- Rithvik Ravi (24BCE2254)
- Aditya (24BCE2242)

---

### Q1: What is a deadlock in an operating system?
**Answer**: A deadlock is a state where a set of concurrent processes are permanently blocked because each process holds one or more resources while waiting for another resource held by another process in the same set. No process can execute, complete, or release its resources without external intervention.

---

### Q2: What are the four Coffman conditions necessary for deadlock to arise?
**Answer**:
1. **Mutual Exclusion**: At least one resource must be held in a non-shareable mode (only one process at a time).
2. **Hold and Wait**: A process must currently hold at least one resource while waiting to acquire additional resources held by others.
3. **No Preemption**: Resources cannot be forcibly confiscated; they can only be released voluntarily by the holding process upon completion.
4. **Circular Wait**: A closed chain of processes $\{P_0, P_1, \dots, P_n\}$ exists where $P_0$ waits for a resource held by $P_1$, $P_1$ waits for $P_2$, and $P_n$ waits for $P_0$.

---

### Q3: What is the fundamental difference between Deadlock Avoidance and Deadlock Detection?
**Answer**:
- **Avoidance (e.g., Banker's Algorithm)**: Conservative and proactive. Every resource request is intercepted at runtime. The OS tests whether granting the request leaves the system in a *safe state*. If not, the process is forced to wait even if resources are currently free. Requires *a priori* knowledge of maximum claims.
- **Detection**: Optimistic and reactive. Resource requests are granted immediately if available. Periodically, the OS runs a detection algorithm on the actual allocation and request state to check if deadlock has formed. Does not require maximum claims.

---

### Q4: In the Silberschatz multi-instance algorithm, why is $Finish[i]$ initialized to $True$ if $Allocation[i] == 0$?
**Answer**: A process holding zero units across all resource types cannot cause or contribute to a deadlock by blocking other processes. Even if its current request cannot be met by Available resources, it holds nothing that other processes need. Thus, it cannot be part of a deadlocked set.

---

### Q5: What is the time complexity of the Silberschatz multi-instance detection algorithm and why?
**Answer**: The time complexity is $O(m \cdot n^2)$, where $n$ is the number of processes and $m$ is the number of resource types.
In the worst case, each scan over $n$ processes checks $m$ vector components ($O(m \cdot n)$ work). If only one process finishes per scan, the algorithm rescans up to $n$ times: $n \times O(m \cdot n) = O(m \cdot n^2)$.

---

### Q6: Why must the algorithm strictly rescan from index 0 whenever a candidate process finishes?
**Answer**: Monotonicity: When process $i$ finishes, it adds its held resources to $Work$ ($Work \gets Work + Allocation[i]$). Because allocations are non-negative, available resources never decrease. A previously checked, lower-indexed process $k < i$ that was blocked might now be satisfied. Rescanning from index 0 guarantees deterministic evaluation and finds the maximal finishable set.

---

### Q7: In a multi-instance Resource Allocation Graph (RAG), is a cycle a sufficient condition for deadlock?
**Answer**: No! In a multi-instance RAG, a cycle is a *necessary* condition for deadlock, but *not* sufficient. If a cycle exists, but one of the involved resource types has free instances or has instances held by an external process outside the cycle that can finish and release units, the cycle can break dynamically without deadlock.

---

### Q8: Under what condition is a cycle in a RAG both necessary and sufficient for deadlock?
**Answer**: In a **single-instance** resource system (where every resource type has exactly 1 unit). In that case, any directed cycle is strictly equivalent to a circular wait, guaranteeing deadlock.

---

### Q9: What is a Wait-For Graph (WFG) and how is it related to a RAG?
**Answer**: A Wait-For Graph is a directed graph whose nodes are exclusively processes. A directed edge $P_i \to P_j$ exists if process $P_i$ is waiting for a resource currently held by $P_j$. A WFG is obtained from a RAG by collapsing the resource nodes and drawing direct edges from waiting processes to holding processes.

---

### Q10: How does Tarjan's Strongly Connected Components (SCC) algorithm assist in deadlock analysis?
**Answer**: Tarjan's algorithm partitions the wait-for graph into maximal strongly connected subgraphs in linear $O(V + E)$ time. Each non-trivial SCC represents an independent deadlocked cluster. Within each SCC, an elementary cycle can be extracted to give the user a concrete cycle of processes causing the deadlock.

---

### Q11: What are the tradeoffs of the Abort-All recovery strategy?
**Answer**:
- **Advantage**: Simplicity. Guaranteed to break all deadlocks in a single recovery step.
- **Disadvantage**: Maximum cost and waste. Aborts all deadlocked processes, discarding 100% of their computational work, even if aborting a single process would have freed enough resources for the others to finish.

---

### Q12: How does the Abort-One-by-One strategy select victims, and what is the aging penalty?
**Answer**: It evaluates each deadlocked process using a cost function: $\text{Cost} = \text{Priority} \times \text{Progress} \times \text{WorkUnits}$. The lowest-cost process is aborted, its resources released, and detection is re-run. To prevent the same process from being repeatedly victimized across successive episodes, an aging penalty multiplier $(1 + 0.5 \times \text{times\_victimized})$ increases its effective cost.

---

### Q13: What is starvation in deadlock recovery, and how is it mitigated?
**Answer**: Starvation occurs when the victim selection heuristic consistently selects the same low-priority or low-progress process for abortion or preemption, preventing it from ever finishing. It is mitigated by tracking `times_victimized` and capping preemption counts per process or inflating victim cost over time.

---

### Q14: How does Resource Preemption with Rollback work?
**Answer**: Instead of killing a process, the OS forcibly revokes one or more resource units from a holding process, gives them to the pool to satisfy a blocked process, and rolls the victim process back to a previous safe checkpoint. The victim loses only the progress made since that checkpoint ($Progress \gets Progress \times (1 - \text{rollback\_fraction})$).

---

### Q15: What is the "Recovery Line" and the domino effect in checkpoint rollback?
**Answer**: If processes communicate with messages or shared memory, rolling back process $P_1$ may invalidate a message received from $P_2$, forcing $P_2$ to roll back as well. This cascading dependency is called the domino effect. A consistent set of checkpoints across all interacting processes is called the Recovery Line.

---

### Q16: What is the core insight of the proposed Debt-Ledger Recovery (DLR) strategy?
**Answer**: Existing strategies either terminate processes (100% work lost) or preempt resources and roll back (partial work lost). DLR introduces **unit-granular resource lending with in-place suspension**:
1. Only the minimal number of resource units needed to break the cycle are lent.
2. Lenders are suspended in place (state frozen, zero rollback, zero progress lost).
3. Lent units are tracked in a Debt Ledger.
4. Repayment is formally proven through a precomputed safe sequence before any lending begins.

---

### Q17: What is an "over-subscribed" process in DLR, and why must it be aborted as a fallback?
**Answer**: A process $i$ is over-subscribed if for some resource $j$:
$$\text{Allocation}[i][j] + \text{Request}[i][j] > \text{Total}[j]$$
Even if every other process finished and returned all resources in the system, process $i$ could never be satisfied. Lending resources cannot resolve impossible requirements. Hence, DLR classifies such processes and aborts them under `FALLBACK_ABORT` before planning lending.

---

### Q18: What is the Ledger-Augmented State in DLR?
**Answer**: Given a lend plan $L[i][j]$:
- $\text{Allocation}' = \text{Allocation} - L$ (lenders temporarily give up held units)
- $\text{Request}' = \text{Request} + L$ (lent units are added to lender requests to guarantee repayment)
- $\text{Available}' = \text{Available} + \sum_i L[i]$ (pool receives lent units)

---

### Q19: What is the Repayment Safety Invariant in DLR?
**Answer**: A lend plan $L$ is valid **if and only if** running the Phase 1 Silberschatz detection algorithm on the ledger-augmented state yields **no deadlock**. The safe execution sequence returned by detection becomes the deterministic **Repayment Order**.

---

### Q20: How does the Repayment Router prevent new deadlocks from forming during recovery?
**Answer**: The Repayment Router employs a **grant gate**: as non-lender processes complete and release resources, freed units are reserved strictly for the next processes in the repayment order. Debt Ledger IOUs owed to suspended lenders are settled with highest priority before non-ledger requests, ensuring lenders resume and finish as guaranteed.

---

### Q21: What is the Shapley Blame Index and why is it used in DLR?
**Answer**: The Shapley Blame Index applies game-theoretic cooperative game theory to deadlocks. The deadlocked set $D$ is the coalition, and characteristic function $v(S)$ measures the number of deadlocked processes if processes in $D \setminus S$ are removed. The Shapley value $\phi_i$ measures process $i$'s average marginal contribution to the deadlock across all coalitional orders. Processes that contributed most to the deadlock receive higher blame and lower lending costs, making them the primary source of loans.

---

### Q22: What axioms does the Shapley Blame Index satisfy?
**Answer**:
1. **Efficiency**: $\sum_{i \in D} \phi_i = v(D)$ (total blame equals the total number of deadlocked processes).
2. **Symmetry**: Two processes with identical allocations and requests receive identical blame scores.
3. **Null-Player**: A process that never changes the deadlock status of any coalition receives zero blame.
4. **Additivity**: If deadlock is evaluated across independent resource pools, total blame is the sum of component blames.

---

### Q23: What are the 6 formal invariants verified in DLR (P1 through P6)?
**Answer**:
- **P1 Safety**: The ledger-augmented state is deadlock-free; all non-fallback processes finish.
- **P2 Zero Loss**: Non-fallback processes suffer zero work loss ($\text{rollback} = 0$).
- **P3 Conservation**: At every step, $\text{Available} + \sum \text{Allocation} + \text{units\_in\_transit} = \text{Total}$.
- **P4 Bounded Wait**: Suspension duration is bounded by the process's position in the repayment order.
- **P5 Minimality**: In exact mode, no proper sub-plan of $L$ is deadlock-free.
- **P6 Dominance**: DLR's total lost work is $\le$ Abort-One-by-One's lost work on all tested systems.

---

### Q24: How does DLR's unit minimality compare between Exact Mode and Greedy Mode?
**Answer**:
- **Exact Mode** ($\le 14$ lendable units): Uses iterative deepening over $k = 1, 2, \dots$ with branch-and-bound lower bounding to guarantee the mathematically minimal unit plan.
- **Greedy Mode** ($> 14$ units): Selects units with maximal finishable gain per unit cost, followed by a backward pruning pass that drops any unit whose removal maintains augmented safety.

---

### Q25: How is fairness measured in the recovery comparison dashboard?
**Answer**: Fairness is measured as:
$$\text{Fairness Score} = 1 - \text{Gini}(\text{Per-Process Costs})$$
If recovery cost is concentrated entirely on a single victim (as in Abort-One), the Gini coefficient approaches 1 (unfairness). When recovery costs are distributed minimally and proportionally to blame (as in DLR), Gini is low and fairness approaches 1.

---

### Q26: What are the practical limitations of DLR in production OS kernels?
**Answer**:
1. **Process Suspendability**: Requires that lender processes support in-place suspension without timing out on external network or hardware connections.
2. **Hardware Locking**: Not all physical resources (e.g., non-preemptible device registers) can be lent at unit granularity.
3. **Computational Overhead**: Exact branch-and-bound search is exponential in the number of lendable units, necessitating the greedy heuristic for larger systems.
