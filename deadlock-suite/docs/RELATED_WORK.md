# Related Work & Theoretical Positioning of Debt-Ledger Recovery (DLR)

**Project**: Deadlock Detection & Recovery: Resource Allocation Graph Visualizer  
**Course**: Operating Systems (BCSE303L)  
**Authors**:
- Sri Krishna (24BCE2630)
- Rithvik Ravi (24BCE2254)
- Aditya (24BCE2242)

---

## 1. Statement of Novelty

> [!NOTE]
> **Novelty Disclaimer**:  
> The Debt-Ledger Recovery (DLR) algorithm implemented in this suite is a **proposed method**, novel to the best of our knowledge based on an extensive literature and patent search covering operating systems, distributed deadlock handling, and automated manufacturing systems.

Classical operating system recovery paradigms treat deadlock resolution as a destructive operation: either processes must be terminated (killing all accumulated work) or resources must be forcibly confiscated and the holder rolled back to a checkpoint (losing partial work). DLR introduces a cooperative resource-lending paradigm where deadlocked processes temporarily lend specific resource units to the system pool while suspended in place, guaranteed to be repaid via a formally verified repayment router.

---

## 2. Comparison with Prior Literature and Patents

### 2.1 Cost and Priority-Based Victim Selection (Silberschatz et al., WFG Patents)
- **Prior Work**: Standard textbooks (Silberschatz, Galvin & Gagne, *Operating System Concepts*; Tanenbaum, *Modern Operating Systems*) and industrial database patents (e.g., US Patents on transaction rollback in wait-for graphs) resolve deadlocks by selecting a single "victim" process using heuristic formulas based on process priority, runtime so far, remaining time, and held resources.
- **Contrast with DLR**:
  - Victim selection is all-or-nothing: the entire process is aborted and its entire allocation released.
  - DLR operates at **unit granularity**: if lending 1 unit of Resource A from $P_1$ suffices to allow $P_0$ to complete, only 1 unit is lent. $P_1$ is not aborted, its other allocations remain untouched, and zero progress is lost.

### 2.2 Consistent Checkpointing and Recovery Lines (Wang et al., 1995)
- **Prior Work**: Wang, Chung, and Kuo studied recovery lines in message-passing distributed systems, addressing the "domino effect" where rolling back one process forces dependent processes to cascade backwards to achieve a consistent global state.
- **Contrast with DLR**:
  - Checkpoint-rollback incurs severe I/O overhead to periodically snapshot memory and register state, and rolling back still loses all work performed since the last checkpoint.
  - DLR requires **no checkpoints and zero rollback**: lender processes are suspended in memory (execution paused, threads descheduled), maintaining their heap and register contexts completely intact.

### 2.3 "Guaranteed Deadlock Recovery" (Wang, Merritt, Romanovsky, 1998)
- **Prior Work**: Wang, Merritt, and Romanovsky proposed transactional mechanisms to guarantee deadlock recovery in fault-tolerant systems using nested atomic actions and forward error recovery.
- **Contrast with DLR**:
  - Their approach relies on transactional undo logs and compensations, which are domain-specific and computationally expensive for general-purpose OS kernels.
  - DLR relies strictly on the mathematical properties of the Silberschatz multi-instance detection algorithm, repurposing the detection engine to formally prove repayment feasibility without requiring transactional logging.

### 2.4 Cooperative Suspension with Timers (IJCA 2012 Style)
- **Prior Work**: Several heuristic works propose cooperative yielding where a blocked process voluntarily yields resources and sleeps on a timer, hoping contention subsides.
- **Contrast with DLR**:
  - Timer-based yielding provides **no formal safety guarantee**; if the timer expires before contention clears, the process wakes up and can re-enter deadlock or cause live-lock.
  - DLR replaces heuristic timers with a **deterministic Repayment Router**: repayment order is mathematically verified *a priori*, and resumption is event-driven based on actual resource release by completed predecessors.

### 2.5 Petri-Net Transition-Based Recovery for Automated Manufacturing (Processes, 2025)
- **Prior Work**: Recent works in automated manufacturing systems (e.g., *Processes* 2025; IEEE Transactions on Automation Science and Engineering) employ S3PR Petri nets to design siphon-based deadlock controllers.
- **Contrast with DLR**:
  - Petri net controllers require calculating minimal siphons and elementary traps, which is computationally prohibitive for general OS process models with dynamically changing allocations.
  - DLR operates directly on the standard Available, Allocation, and Request matrices already maintained by modern OS kernels.

---

## 3. Four Core Differentiators of DLR

1. **Unit-Granular Minimal Lend Plan**:
   Rather than sacrificing entire processes, DLR computes an optimal matrix $L[i][j]$ denoting the exact number of units to borrow. In exact mode, iterative deepening with branch-and-bound guarantees that no proper sub-plan can break the deadlock.

2. **Formally Verified Repayment Safety**:
   Before taking any action, DLR runs the detection engine on the ledger-augmented state:
   $$\text{Allocation}' = \text{Allocation} - L, \quad \text{Request}' = \text{Request} + L, \quad \text{Available}' = \text{Available} + \sum_i L[i]$$
   If and only if detection reports zero deadlocks, the plan is approved. The resulting safe sequence defines the deterministic repayment route.

3. **Explicit Irrecoverability Classification**:
   Unlike classical strategies that blindly abort processes, DLR checks if processes are **over-subscribed**:
   $$\exists j : \text{Allocation}[i][j] + \text{Request}[i][j] > \text{Total}[j]$$
   Aborts are performed exclusively when a process demands more units than physically exist in the system (`FALLBACK_ABORT`).

4. **Game-Theoretic Burden Assignment (Shapley Blame Index)**:
   DLR formulates deadlocks as cooperative games and computes the Shapley value $\phi_i$ of each process's marginal contribution to deadlock formation. Processes with highest blame receive normalized discounts, ensuring that the entities most responsible for causing the deadlock bear the primary lending burden.

---

## 4. Limitations and Real-World Constraints

1. **Process Suspendability**:
   DLR assumes lender processes can be descheduled without violating real-time deadlines or timing out on network connections.
2. **Resource Monotonicity**:
   DLR assumes resources are reusable and non-depletable.
3. **Computational Complexity in Exact Mode**:
   Finding the exact minimal lend plan across multi-instance distributions is NP-hard. Exact mode is capped at $\le 14$ lendable units; larger systems rely on the greedy heuristic with pruning.
4. **Parametric Cost Model**:
   Composite cost and fairness evaluations are parametric models ($w_{loss}, w_{susp}, \epsilon$), not direct physical measurements.
