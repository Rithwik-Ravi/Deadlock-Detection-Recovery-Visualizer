/**
 * Recovery View & Comparison Controller for Deadlock Suite.
 *
 * Implements:
 * - Strategy chooser (radio list with plain descriptions, DLR as Proposed method).
 * - Per-process attributes table (priority, progress, work units, rollback fraction, restartable)
 *   with inline validation.
 * - Transport bar for recovery actions (Step through actions, highlights in Plan, Suspended & Aborted marks on RAG).
 * - Plan (numbered list with current action highlighted).
 * - Ledger table (creditor, resource, units, owed by, status with text + mark).
 * - Shapley Blame (horizontal bars sorted descending).
 * - Comparison small multiples (lost work, processes aborted, recovery steps, total cost, fairness),
 *   values on bars, best bar underlined, DLR in pen-blue, others in gray.
 * - Aggregate 200 random systems table.
 */

export class RecoveryViewController {
  constructor(recoveryRagVisualizer, getSystemDataCallback, getLastReportCallback = null) {
    this.rag = recoveryRagVisualizer;
    this.getSystemData = getSystemDataCallback;
    this.getLastReport = getLastReportCallback;

    this.selectedStrategy = "dlr";
    this.attributes = [];
    this.lastRecoveryReport = null;
    this.currentActionIndex = -1;
    this.isPlaying = false;
    this.playbackTimer = null;

    // DOM Elements
    this.strategyRadios = document.querySelectorAll('input[name="strategy"]');
    this.btnRunRecovery = document.getElementById("btn-run-recovery");
    this.btnRunCompare = document.getElementById("btn-run-compare");
    this.btnRunBenchmark = document.getElementById("btn-run-random-benchmark");
    this.btnResetAttrs = document.getElementById("btn-reset-attrs");

    this.attrsTbody = document.getElementById("attrs-tbody");
    this.attrsError = document.getElementById("attrs-error");
    this.recoveryError = document.getElementById("recovery-error");
    this.planList = document.getElementById("plan-list");
    this.ledgerTbody = document.getElementById("ledger-tbody");
    this.blameContainer = document.getElementById("blame-chart-container");
    this.comparisonCharts = document.getElementById("comparison-charts");
    this.comparisonStatus = document.getElementById("comparison-status");
    this.benchmarkBox = document.getElementById("benchmark-results-box");
    this.benchmarkTbody = document.getElementById("benchmark-tbody");

    this.recTransport = document.getElementById("rec-transport");

    this.initEventListeners();
    this.buildTransportBar();
  }

  initEventListeners() {
    this.strategyRadios.forEach((radio) => {
      radio.addEventListener("change", (e) => {
        if (e.target.checked) {
          this.selectedStrategy = e.target.value;
        }
      });
    });

    if (this.btnRunRecovery) {
      this.btnRunRecovery.addEventListener("click", () => this.runRecovery());
    }
    if (this.btnRunCompare) {
      this.btnRunCompare.addEventListener("click", () => this.runComparison());
    }
    if (this.btnRunBenchmark) {
      this.btnRunBenchmark.addEventListener("click", () => this.runRandomBenchmark());
    }
    if (this.btnResetAttrs) {
      this.btnResetAttrs.addEventListener("click", () => this.resetAttributesToDefault());
    }
  }

  buildTransportBar() {
    if (!this.recTransport) return;

    this.recTransport.innerHTML = `
      <div class="transport-buttons" role="group" aria-label="Recovery playback">
        <button type="button" class="icon-btn" id="rec-btn-first" aria-label="First action" title="First action">
          <svg class="icon"><use href="#i-first"/></svg>
        </button>
        <button type="button" class="icon-btn" id="rec-btn-prev" aria-label="Previous action" title="Previous action">
          <svg class="icon"><use href="#i-prev"/></svg>
        </button>
        <button type="button" class="icon-btn" id="rec-btn-toggle" aria-label="Play actions" title="Play / Pause">
          <svg class="icon" id="rec-icon-toggle"><use href="#i-play"/></svg>
        </button>
        <button type="button" class="icon-btn" id="rec-btn-next" aria-label="Next action" title="Next action">
          <svg class="icon"><use href="#i-next"/></svg>
        </button>
        <button type="button" class="icon-btn" id="rec-btn-last" aria-label="Last action" title="Last action">
          <svg class="icon"><use href="#i-last"/></svg>
        </button>
      </div>

      <div class="scrubber">
        <input type="range" class="scrubber-range" id="rec-scrubber" min="0" max="0" value="0" aria-label="Action scrubber">
        <div class="scrubber-label" id="rec-scrubber-label" style="left: 0%;">Initial</div>
      </div>
    `;

    this.recBtnFirst = this.recTransport.querySelector("#rec-btn-first");
    this.recBtnPrev = this.recTransport.querySelector("#rec-btn-prev");
    this.recBtnToggle = this.recTransport.querySelector("#rec-btn-toggle");
    this.recBtnNext = this.recTransport.querySelector("#rec-btn-next");
    this.recBtnLast = this.recTransport.querySelector("#rec-btn-last");
    this.recScrubber = this.recTransport.querySelector("#rec-scrubber");
    this.recScrubberLabel = this.recTransport.querySelector("#rec-scrubber-label");
    this.recIconToggle = this.recTransport.querySelector("#rec-icon-toggle use");

    this.recBtnFirst.addEventListener("click", () => this.goToAction(-1));
    this.recBtnPrev.addEventListener("click", () => this.stepAction(-1));
    this.recBtnToggle.addEventListener("click", () => this.toggleActionPlay());
    this.recBtnNext.addEventListener("click", () => this.stepAction(1));
    this.recBtnLast.addEventListener("click", () => {
      const actions = this.lastRecoveryReport?.actions || [];
      this.goToAction(actions.length - 1);
    });

    this.recScrubber.addEventListener("input", (e) => {
      this.goToAction(parseInt(e.target.value, 10) - 1);
    });
  }

  syncWithSystem(systemData) {
    this.systemData = systemData;
    const n = systemData.allocation.length;

    if (this.attributes.length !== n) {
      this.resetAttributesToDefault();
    } else {
      this.renderAttributesTable();
    }

    const report = this.getLastReport ? this.getLastReport() : null;
    this.rag.render(systemData, report);
    this.rag.fitToView();
  }

  resetAttributesToDefault() {
    if (!this.systemData) return;
    const n = this.systemData.allocation.length;
    this.attributes = [];
    for (let i = 0; i < n; i++) {
      this.attributes.push({
        priority: 5 + (i % 5),
        progress: Math.min(0.9, 0.3 + (i % 5) * 0.15),
        work_units: 50 + (i % 4) * 25,
        rollback_fraction: 0.5,
        restartable: true,
        times_victimized: 0,
      });
    }
    this.renderAttributesTable();
  }

  renderAttributesTable() {
    if (!this.attrsTbody) return;
    this.attrsTbody.innerHTML = "";
    const names = this.systemData?.process_names || [];

    this.attributes.forEach((attr, idx) => {
      const pName = names[idx] || `P${idx}`;
      const tr = document.createElement("tr");

      tr.innerHTML = `
        <th scope="row">${pName}</th>
        <td>
          <input type="number" min="1" max="10" class="cell-input attr-priority" data-idx="${idx}" value="${attr.priority}">
        </td>
        <td>
          <input type="number" min="0.0" max="1.0" step="0.1" class="cell-input attr-progress" data-idx="${idx}" value="${attr.progress}">
        </td>
        <td>
          <input type="number" min="10" max="500" step="10" class="cell-input attr-work" data-idx="${idx}" value="${attr.work_units}">
        </td>
        <td>
          <input type="number" min="0.0" max="1.0" step="0.1" class="cell-input attr-rollback" data-idx="${idx}" value="${attr.rollback_fraction}">
        </td>
        <td style="text-align: center;">
          <input type="checkbox" class="attr-check attr-restartable" data-idx="${idx}" ${attr.restartable ? "checked" : ""}>
        </td>
      `;

      this.attrsTbody.appendChild(tr);
    });

    this.attachAttrValidation();
  }

  attachAttrValidation() {
    const validate = () => {
      let hasError = false;
      let errorMsg = "";

      this.attrsTbody.querySelectorAll(".cell-input").forEach((inp) => {
        const val = parseFloat(inp.value);
        let invalid = false;

        if (inp.classList.contains("attr-priority")) {
          if (isNaN(val) || val < 1 || val > 10) {
            invalid = true;
            errorMsg = "Priority must be an integer between 1 and 10.";
          }
        } else if (inp.classList.contains("attr-progress") || inp.classList.contains("attr-rollback")) {
          if (isNaN(val) || val < 0.0 || val > 1.0) {
            invalid = true;
            errorMsg = "Progress and rollback fractions must be between 0.0 and 1.0.";
          }
        } else if (inp.classList.contains("attr-work")) {
          if (isNaN(val) || val < 1) {
            invalid = true;
            errorMsg = "Work units must be at least 1.";
          }
        }

        inp.classList.toggle("cell-input-invalid", invalid);
        if (invalid) hasError = true;
      });

      if (this.attrsError) {
        if (hasError) {
          this.attrsError.textContent = errorMsg;
          this.attrsError.hidden = false;
          if (this.btnRunRecovery) this.btnRunRecovery.disabled = true;
        } else {
          this.attrsError.hidden = true;
          if (this.btnRunRecovery) this.btnRunRecovery.disabled = false;
        }
      }
    };

    this.attrsTbody.querySelectorAll(".attr-priority").forEach((inp) => {
      inp.addEventListener("input", (e) => {
        const i = parseInt(e.target.dataset.idx, 10);
        this.attributes[i].priority = parseInt(e.target.value, 10) || 5;
        validate();
      });
    });

    this.attrsTbody.querySelectorAll(".attr-progress").forEach((inp) => {
      inp.addEventListener("input", (e) => {
        const i = parseInt(e.target.dataset.idx, 10);
        this.attributes[i].progress = parseFloat(e.target.value) || 0.5;
        validate();
      });
    });

    this.attrsTbody.querySelectorAll(".attr-work").forEach((inp) => {
      inp.addEventListener("input", (e) => {
        const i = parseInt(e.target.dataset.idx, 10);
        this.attributes[i].work_units = parseInt(e.target.value, 10) || 100;
        validate();
      });
    });

    this.attrsTbody.querySelectorAll(".attr-rollback").forEach((inp) => {
      inp.addEventListener("input", (e) => {
        const i = parseInt(e.target.dataset.idx, 10);
        this.attributes[i].rollback_fraction = parseFloat(e.target.value) || 0.5;
        validate();
      });
    });

    this.attrsTbody.querySelectorAll(".attr-restartable").forEach((inp) => {
      inp.addEventListener("change", (e) => {
        const i = parseInt(e.target.dataset.idx, 10);
        this.attributes[i].restartable = e.target.checked;
        validate();
      });
    });
  }

  async runRecovery() {
    const sys = this.getSystemData();
    const payload = {
      available: sys.available,
      allocation: sys.allocation,
      request: sys.request,
      process_names: sys.process_names,
      resource_names: sys.resource_names,
      strategy: this.selectedStrategy,
      attributes: this.attributes,
    };

    if (this.recoveryError) this.recoveryError.hidden = true;

    try {
      this.btnRunRecovery.disabled = true;
      this.btnRunRecovery.textContent = "Running…";

      const res = await fetch("/api/recover", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const err = await res.json();
        if (this.recoveryError) {
          this.recoveryError.textContent = `Recovery error: ${err.detail || "Server error"}`;
          this.recoveryError.hidden = false;
        }
        return;
      }

      const report = await res.json();
      this.lastRecoveryReport = report;

      this.renderPlan(report.actions || []);
      this.renderLedgerTable(report.ledger_entries || []);
      this.renderBlameChart(report.blame_scores || {});

      // Setup recovery action playback
      const actions = report.actions || [];
      if (this.recScrubber) {
        this.recScrubber.max = actions.length;
        this.recScrubber.value = 0;
      }
      this.goToAction(0);
    } catch (e) {
      console.error(e);
      if (this.recoveryError) {
        this.recoveryError.textContent = `Network error running recovery: ${e.message}`;
        this.recoveryError.hidden = false;
      }
    } finally {
      this.btnRunRecovery.disabled = false;
      this.btnRunRecovery.textContent = "Run recovery";
    }
  }

  renderPlan(actions) {
    if (!this.planList) return;
    this.planList.innerHTML = "";

    if (actions.length === 0) {
      this.planList.innerHTML = `<li class="empty">No recovery actions needed.</li>`;
      return;
    }

    actions.forEach((act, idx) => {
      const li = document.createElement("li");
      li.className = "plan-item";
      li.id = `plan-item-${idx}`;

      let verb = act.action_type.toLowerCase();
      if (act.action_type === "SUSPEND") verb = "Suspend";
      else if (act.action_type === "LEND") verb = "Lend";
      else if (act.action_type === "ABORT") verb = "Abort";
      else if (act.action_type === "PREEMPT") verb = "Preempt";
      else if (act.action_type === "RESUME") verb = "Resume";
      else if (act.action_type === "FINISH") verb = "Finish";

      li.innerHTML = `<span class="plan-verb">${verb}</span>: ${act.explanation}`;
      li.style.cursor = "pointer";
      li.addEventListener("click", () => this.goToAction(idx));

      this.planList.appendChild(li);
    });
  }

  toggleActionPlay() {
    if (this.isPlaying) {
      this.pauseActionPlay();
    } else {
      this.startActionPlay();
    }
  }

  startActionPlay() {
    const actions = this.lastRecoveryReport?.actions || [];
    if (actions.length === 0) return;

    if (this.currentActionIndex >= actions.length - 1) {
      this.currentActionIndex = -1;
    }

    this.isPlaying = true;
    if (this.recIconToggle) this.recIconToggle.setAttribute("href", "#i-pause");

    this.playbackTimer = setInterval(() => {
      if (this.currentActionIndex < actions.length - 1) {
        this.stepAction(1);
      } else {
        this.pauseActionPlay();
      }
    }, 800);
  }

  pauseActionPlay() {
    this.isPlaying = false;
    clearInterval(this.playbackTimer);
    this.playbackTimer = null;
    if (this.recIconToggle) this.recIconToggle.setAttribute("href", "#i-play");
  }

  stepAction(delta) {
    const actions = this.lastRecoveryReport?.actions || [];
    const target = this.currentActionIndex + delta;
    if (target >= -1 && target < actions.length) {
      this.goToAction(target);
    }
  }

  goToAction(index) {
    const actions = this.lastRecoveryReport?.actions || [];
    this.currentActionIndex = index;

    if (this.recScrubber) {
      this.recScrubber.value = index + 1;
    }
    if (this.recScrubberLabel) {
      const pct = actions.length > 0 ? ((index + 1) / actions.length) * 100 : 0;
      this.recScrubberLabel.style.left = `${pct}%`;
      this.recScrubberLabel.textContent = index === -1 ? "Initial" : `Action ${index + 1} of ${actions.length}`;
    }

    // Highlight current plan item
    for (let k = 0; k < actions.length; k++) {
      const item = document.getElementById(`plan-item-${k}`);
      if (item) {
        const isCurrent = k === index;
        const isDone = k < index;
        item.classList.toggle("hl", isCurrent);
        item.classList.toggle("plan-item-done", isDone && !isCurrent);
        if (isCurrent) item.scrollIntoView({ block: "nearest", behavior: "smooth" });
      }
    }

    // Determine process states at this action
    const n = this.systemData.allocation.length;
    let procStates = {};
    for (let i = 0; i < n; i++) procStates[i] = "running";

    let snapshot = this.systemData;

    for (let k = 0; k <= index; k++) {
      const act = actions[k];
      if (act.action_type === "ABORT" && act.process_idx !== null) {
        procStates[act.process_idx] = "aborted";
      } else if (act.action_type === "SUSPEND" && act.process_idx !== null) {
        procStates[act.process_idx] = "suspended";
      } else if (act.action_type === "RESUME" && act.process_idx !== null) {
        procStates[act.process_idx] = "running";
      } else if (act.action_type === "FINISH" && act.process_idx !== null) {
        procStates[act.process_idx] = "finished";
      }
      if (act.snapshot) {
        snapshot = act.snapshot;
      }
    }

    this.rag.render(snapshot, null, procStates, [], this.lastRecoveryReport?.ledger_entries);
  }

  renderLedgerTable(entries) {
    if (!this.ledgerTbody) return;
    this.ledgerTbody.innerHTML = "";

    if (entries.length === 0) {
      this.ledgerTbody.innerHTML = `<tr><td colspan="5" class="empty">No units lent yet.</td></tr>`;
      return;
    }

    entries.forEach((iou) => {
      const tr = document.createElement("tr");

      const debtors = (iou.debtor_set && iou.debtor_set.length > 0)
        ? iou.debtor_set.join(", ")
        : "System pool";

      const isRepaid = iou.repaid;
      const statusMarkup = isRepaid
        ? `<svg class="status-mark status-repaid"><use href="#i-first"/></svg> repaid`
        : `<svg class="status-mark status-open"><circle cx="4" cy="4" r="3"/></svg> open`;

      tr.innerHTML = `
        <th scope="row">${iou.creditor_name}</th>
        <td>${iou.resource_name}</td>
        <td class="num mono">${iou.units}</td>
        <td>${debtors}</td>
        <td>${statusMarkup}</td>
      `;

      this.ledgerTbody.appendChild(tr);
    });
  }

  renderBlameChart(blameScores) {
    if (!this.blameContainer) return;
    this.blameContainer.innerHTML = "";

    const entries = Object.entries(blameScores);
    if (entries.length === 0) {
      this.blameContainer.innerHTML = `<p class="empty">No deadlocked processes to assign blame.</p>`;
      return;
    }

    // Sort descending by value
    entries.sort((a, b) => b[1] - a[1]);

    const maxScore = Math.max(...entries.map(([_, v]) => v), 0.001);

    entries.forEach(([pName, score]) => {
      const pct = Math.min(100, Math.max(2, (score / maxScore) * 100));

      const label = document.createElement("div");
      label.className = "bar-label";
      label.textContent = pName;

      const track = document.createElement("div");
      track.className = "bar-track";
      track.innerHTML = `
        <div class="bar" style="width: ${pct}%;"></div>
        <span class="bar-value">${score.toFixed(3)}</span>
      `;

      this.blameContainer.appendChild(label);
      this.blameContainer.appendChild(track);
    });
  }

  async runComparison() {
    const sys = this.getSystemData();
    const payload = {
      available: sys.available,
      allocation: sys.allocation,
      request: sys.request,
      process_names: sys.process_names,
      resource_names: sys.resource_names,
      attributes: this.attributes,
    };

    try {
      this.btnRunCompare.disabled = true;
      this.btnRunCompare.textContent = "Comparing…";

      const res = await fetch("/api/compare", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        if (this.comparisonStatus) {
          this.comparisonStatus.textContent = "Comparison failed on server.";
          this.comparisonStatus.classList.add("prose-error");
        }
        return;
      }

      const data = await res.json();
      if (!data.deadlocked) {
        if (this.comparisonStatus) {
          this.comparisonStatus.textContent = "System is safe. No deadlock recovery required.";
          this.comparisonStatus.classList.remove("prose-error");
        }
        if (this.comparisonCharts) this.comparisonCharts.innerHTML = "";
        return;
      }

      if (this.comparisonStatus) {
        this.comparisonStatus.textContent = "Four recovery strategies evaluated. Best performer underlined per metric.";
        this.comparisonStatus.classList.remove("prose-error");
      }

      this.renderSmallMultiples(data.strategies, data.winners);

      if (data.blame && data.blame.blame_scores) {
        this.renderBlameChart(data.blame.blame_scores);
      }
    } catch (e) {
      console.error(e);
      if (this.comparisonStatus) {
        this.comparisonStatus.textContent = `Network error: ${e.message}`;
        this.comparisonStatus.classList.add("prose-error");
      }
    } finally {
      this.btnRunCompare.disabled = false;
      this.btnRunCompare.textContent = "Compare all strategies";
    }
  }

  renderSmallMultiples(strategies, winners) {
    if (!this.comparisonCharts) return;
    this.comparisonCharts.innerHTML = "";

    const stratOrder = ["abort_all", "abort_one_by_one", "preemption", "dlr"];
    const stratLabels = {
      abort_all: "Abort all",
      abort_one_by_one: "Abort one by one",
      preemption: "Preempt & rollback",
      dlr: "Debt-Ledger Recovery",
    };

    const metricsConfig = [
      { key: "total_lost_work", title: "Lost work", note: "lower is better", decimals: 1 },
      { key: "processes_aborted", title: "Processes aborted", note: "lower is better", decimals: 0 },
      { key: "actions_count", title: "Recovery steps", note: "lower is better", decimals: 0, fromActions: true },
      { key: "composite_cost", title: "Total cost", note: "lower is better", decimals: 2 },
      { key: "fairness_score", title: "Fairness", note: "higher is better", decimals: 3 },
    ];

    metricsConfig.forEach((cfg) => {
      const panel = document.createElement("div");
      panel.className = "chart-panel";

      const title = document.createElement("h3");
      title.className = "chart-title";
      title.innerHTML = `${cfg.title} <span class="chart-note">(${cfg.note})</span>`;
      panel.appendChild(title);

      const chartGrid = document.createElement("div");
      chartGrid.className = "chart";

      // Collect values to compute max for scaling
      const values = stratOrder.map((key) => {
        const strat = strategies[key];
        if (!strat) return 0;
        if (cfg.fromActions) return strat.actions_count || 0;
        return strat.metrics ? strat.metrics[cfg.key] || 0 : 0;
      });

      const maxVal = Math.max(...values, 0.0001);
      const winnerKey = winners[cfg.key];

      stratOrder.forEach((key, idx) => {
        const val = values[idx];
        const isDlr = key === "dlr";
        const isBest = winnerKey ? winnerKey === key : false;

        const pct = Math.min(100, Math.max(3, (val / maxVal) * 100));

        const label = document.createElement("div");
        label.className = "chart-label";
        label.textContent = stratLabels[key];

        const barTrack = document.createElement("div");
        barTrack.className = "bar-track";

        const bar = document.createElement("div");
        bar.className = `chart-bar ${isDlr ? "chart-bar-dlr" : ""} ${isBest ? "chart-best" : ""}`;
        bar.style.width = `${pct}%`;

        const valText = document.createElement("span");
        valText.className = `bar-value ${isBest ? "chart-value-best" : ""}`;
        valText.textContent = cfg.decimals === 0 ? Math.round(val) : val.toFixed(cfg.decimals);

        barTrack.appendChild(bar);
        barTrack.appendChild(valText);

        chartGrid.appendChild(label);
        chartGrid.appendChild(barTrack);
      });

      panel.appendChild(chartGrid);
      this.comparisonCharts.appendChild(panel);
    });
  }

  async runRandomBenchmark() {
    if (!this.benchmarkBox) return;
    this.benchmarkBox.hidden = false;
    this.benchmarkTbody.innerHTML = `<tr><td colspan="5" class="empty">Running Monte Carlo benchmark across 200 random deadlocked systems…</td></tr>`;

    try {
      this.btnRunBenchmark.disabled = true;
      const res = await fetch("/api/benchmark-random?count=200", { method: "POST" });
      if (!res.ok) {
        this.benchmarkTbody.innerHTML = `<tr><td colspan="5" class="prose-error">Benchmark failed on server.</td></tr>`;
        return;
      }

      const data = await res.json();
      const avg = data.averages;
      this.benchmarkTbody.innerHTML = "";

      const names = {
        abort_all: "Abort all",
        abort_one_by_one: "Abort one by one",
        preemption: "Preempt & rollback",
        dlr: "Debt-Ledger Recovery",
      };

      const keys = ["abort_all", "abort_one_by_one", "preemption", "dlr"];

      // Determine best averages for underlining
      const bestLostWork = Math.min(...keys.map((k) => avg[k]?.avg_lost_work ?? 9999));
      const bestAborted = Math.min(...keys.map((k) => avg[k]?.avg_aborted ?? 9999));
      const bestCost = Math.min(...keys.map((k) => avg[k]?.avg_composite_cost ?? 9999));
      const bestFairness = Math.max(...keys.map((k) => avg[k]?.avg_fairness_score ?? 0));

      keys.forEach((k) => {
        const item = avg[k];
        if (!item) return;

        const tr = document.createElement("tr");
        const isDlr = k === "dlr";

        tr.innerHTML = `
          <th scope="row">${names[k]} ${isDlr ? `<span class="soft">(proposed)</span>` : ""}</th>
          <td class="num mono ${item.avg_lost_work === bestLostWork ? "chart-value-best" : ""}">${item.avg_lost_work.toFixed(2)}</td>
          <td class="num mono ${item.avg_aborted === bestAborted ? "chart-value-best" : ""}">${item.avg_aborted.toFixed(2)}</td>
          <td class="num mono ${item.avg_composite_cost === bestCost ? "chart-value-best" : ""}">${item.avg_composite_cost.toFixed(2)}</td>
          <td class="num mono ${item.avg_fairness_score === bestFairness ? "chart-value-best" : ""}">${item.avg_fairness_score.toFixed(4)}</td>
        `;

        this.benchmarkTbody.appendChild(tr);
      });
    } catch (e) {
      console.error(e);
      this.benchmarkTbody.innerHTML = `<tr><td colspan="5" class="prose-error">Network error during benchmark: ${e.message}</td></tr>`;
    } finally {
      this.btnRunBenchmark.disabled = false;
    }
  }
}
