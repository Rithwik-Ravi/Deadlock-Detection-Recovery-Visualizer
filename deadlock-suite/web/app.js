/**
 * Main Web Application Controller for Deadlock Detection & Recovery Visualizer.
 *
 * Course: Operating Systems (BCSE303L)
 * Team: Sri Krishna (24BCE2630), Rithvik Ravi (24BCE2254), Aditya (24BCE2242)
 */

import { PlaybackController } from "./playback.js";
import { RAGVisualizer } from "./rag.js";
import { RecoveryViewController } from "./recovery_view.js";

// Global App State
const state = {
  scenarios: {},
  currentScenarioKey: "safe",
  systemData: {
    title: "Classic Silberschatz",
    available: [0, 0, 0],
    allocation: [
      [0, 1, 0],
      [2, 0, 0],
      [3, 0, 3],
      [2, 1, 1],
      [0, 0, 2],
    ],
    request: [
      [0, 0, 0],
      [2, 0, 2],
      [0, 0, 0],
      [1, 0, 0],
      [0, 0, 2],
    ],
    process_names: ["P0", "P1", "P2", "P3", "P4"],
    resource_names: ["A", "B", "C"],
  },
  lastDetectionReport: null,
};

let ragDetection = null;
let ragRecovery = null;
let playback = null;
let recoveryView = null;

// Viva Q&A Data (Curated for BCSE303L, sentence-case)
const VIVA_QA = [
  {
    q: "What is the fundamental difference between deadlock detection and deadlock avoidance?",
    a: "Avoidance (such as the Banker's algorithm) dynamically inspects every request ahead of time and grants it only if the resulting state is guaranteed safe. Detection allows requests to proceed without prior validation and periodically runs an algorithm to find if circular waits have formed.",
  },
  {
    q: "Why does the Silberschatz deadlock detection algorithm initialize Finish[i] = true if Allocation[i] == 0?",
    a: "A process holding zero units of all resource types cannot cause or contribute to a deadlock by blocking other processes. Even if its request cannot currently be satisfied, it holds no resources that others are waiting for.",
  },
  {
    q: "What is the time complexity of the Silberschatz multi-instance detection algorithm?",
    a: "O(m × n²), where n is the number of processes and m is the number of resource types. In the worst case, each scan checks up to n processes, taking O(m × n) comparisons, and rescans up to n times.",
  },
  {
    q: "Why must the detection algorithm rescan from index 0 whenever a process finishes?",
    a: "When a process finishes, it releases resources and increases Work. This newly freed capacity may now satisfy a lower-indexed process that was previously skipped. Rescanning strictly from index 0 guarantees determinism and maximal progress.",
  },
  {
    q: "Can a system with multiple instances per resource have a cycle in the RAG without being deadlocked?",
    a: "Yes. In a multi-instance Resource Allocation Graph, a cycle is a necessary condition for deadlock, but not a sufficient condition. Deadlock occurs only if no process in the cycle can ever obtain the resources it lacks.",
  },
  {
    q: "How does Debt-Ledger Recovery (DLR) achieve zero lost computational work?",
    a: "Traditional recovery kills processes (Abort loses 100% of work) or preempts and rolls them back (losing partial work). DLR suspends lender processes in place with their execution state completely frozen. When their lent units are repaid in the proven safe order, they resume from the exact same instruction without losing progress.",
  },
  {
    q: "What is an over-subscribed process in DLR and why must it be aborted as a fallback?",
    a: "A process i is over-subscribed if for some resource j, Allocation[i][j] + Request[i][j] > Total[j]. Even if all other processes completed and released every unit in existence, process i could never finish. Lending cannot resolve mathematically impossible demands, so DLR explicitly classifies and aborts them under FALLBACK_ABORT.",
  },
  {
    q: "What is the Shapley Blame Index and why is it game-theoretically fair?",
    a: "The Shapley Blame Index treats the deadlocked set as a cooperative game where the characteristic function measures deadlock size without coalition D\\S. The Shapley value computes each process's average marginal contribution to deadlock across all permutations. It uniquely satisfies Efficiency, Symmetry, and Null-Player axioms, ensuring processes that caused the deadlock bear the burden first.",
  },
  {
    q: "How does DLR formally guarantee that lent resources will be repaid (repayment safety)?",
    a: "DLR forms the ledger-augmented state: Allocation' = Allocation - L, Request' = Request + L, Available' = Available + sum(L). A lend plan is approved only if running the Silberschatz detection engine on this augmented state proves zero deadlock. The returned safe sequence serves as the proven repayment router order.",
  },
  {
    q: "What are the four Coffman conditions for deadlock?",
    a: "1. Mutual exclusion (non-shareable resources)\n2. Hold and wait (processes hold resources while waiting for others)\n3. No preemption (resources cannot be forcibly taken)\n4. Circular wait (a closed chain P0 → P1 → … → P0 exists).",
  },
  {
    q: "Why does DLR use branch-and-bound iterative deepening in exact mode?",
    a: "To ensure unit minimality (P5 invariant). By exploring total lent units k = 1, 2, … sequentially, the engine identifies the minimum number of units required to break the cycle. Branch-and-bound prunes candidate branches whose lower-bound cost exceeds the current best.",
  },
  {
    q: "What is the conservation invariant (P3) verified in DLR?",
    a: "At every micro-step of recovery: Available + sum(Allocation) + units_in_transit == Total. No resource instance is ever duplicated, lost, or unaccounted for.",
  },
];

document.addEventListener("DOMContentLoaded", async () => {
  initVisualizers();
  initTabs();
  initScenarioSelect();
  initCustomMatrixEditor();
  initExportHandlers();
  renderVivaQA(VIVA_QA);

  // Load scenarios from API
  await fetchScenarios();

  // Run initial detection
  await runDetection();
});

function initVisualizers() {
  ragDetection = new RAGVisualizer("#rag-svg", "#rag-tooltip", {
    captionId: "det-caption",
    legendId: "det-legend",
  });

  ragRecovery = new RAGVisualizer("#recovery-rag-svg", "#rag-tooltip", {
    captionId: "rec-caption",
    legendId: "rec-legend",
  });

  playback = new PlaybackController(ragDetection, "#det-transport", (stepIdx, candidateIdx, finishFlags) => {
    updateMatrixStrip(candidateIdx, finishFlags);
  });

  recoveryView = new RecoveryViewController(
    ragRecovery,
    () => state.systemData,
    () => state.lastDetectionReport
  );

  // Zoom & Fit controls: Detection
  document.getElementById("zoom-in")?.addEventListener("click", () => ragDetection.zoomIn());
  document.getElementById("zoom-out")?.addEventListener("click", () => ragDetection.zoomOut());
  document.getElementById("zoom-fit")?.addEventListener("click", () => ragDetection.fitToView());

  // Zoom & Fit controls: Recovery
  document.getElementById("recovery-zoom-in")?.addEventListener("click", () => ragRecovery.zoomIn());
  document.getElementById("recovery-zoom-out")?.addEventListener("click", () => ragRecovery.zoomOut());
  document.getElementById("recovery-zoom-fit")?.addEventListener("click", () => ragRecovery.fitToView());

  // Edge Toggles: Detection
  const detAllocToggle = document.getElementById("det-toggle-alloc");
  const detReqToggle = document.getElementById("det-toggle-req");
  let detAllocOn = true;
  let detReqOn = true;

  detAllocToggle?.addEventListener("click", () => {
    detAllocOn = !detAllocOn;
    detAllocToggle.classList.toggle("toggle-on", detAllocOn);
    detAllocToggle.classList.toggle("toggle-alloc", detAllocOn);
    ragDetection.setEdgeVisibility(detAllocOn, detReqOn);
  });

  detReqToggle?.addEventListener("click", () => {
    detReqOn = !detReqOn;
    detReqToggle.classList.toggle("toggle-on", detReqOn);
    detReqToggle.classList.toggle("toggle-req", detReqOn);
    ragDetection.setEdgeVisibility(detAllocOn, detReqOn);
  });

  // Edge Toggles: Recovery
  const recAllocToggle = document.getElementById("rec-toggle-alloc");
  const recReqToggle = document.getElementById("rec-toggle-req");
  let recAllocOn = true;
  let recReqOn = true;

  recAllocToggle?.addEventListener("click", () => {
    recAllocOn = !recAllocOn;
    recAllocToggle.classList.toggle("toggle-on", recAllocOn);
    recAllocToggle.classList.toggle("toggle-alloc", recAllocOn);
    ragRecovery.setEdgeVisibility(recAllocOn, recReqOn);
  });

  recReqToggle?.addEventListener("click", () => {
    recReqOn = !recReqOn;
    recReqToggle.classList.toggle("toggle-on", recReqOn);
    recReqToggle.classList.toggle("toggle-req", recReqOn);
    ragRecovery.setEdgeVisibility(recAllocOn, recReqOn);
  });

  // Run detect button
  document.getElementById("btn-run-detect")?.addEventListener("click", () => runDetection());
}

function initTabs() {
  const tabButtons = document.querySelectorAll(".tab");
  const panes = {
    detection: document.getElementById("pane-detection"),
    recovery: document.getElementById("pane-recovery"),
    "matrix-editor": document.getElementById("pane-matrix-editor"),
    viva: document.getElementById("pane-viva"),
  };

  tabButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      tabButtons.forEach((b) => {
        b.classList.remove("tab-current");
        b.setAttribute("aria-selected", "false");
        b.setAttribute("tabindex", "-1");
      });

      btn.classList.add("tab-current");
      btn.setAttribute("aria-selected", "true");
      btn.removeAttribute("tabindex");

      const target = btn.dataset.tab;
      Object.keys(panes).forEach((k) => {
        if (panes[k]) {
          if (k === target) {
            panes[k].hidden = false;
            panes[k].classList.add("is-active");
          } else {
            panes[k].hidden = true;
            panes[k].classList.remove("is-active");
          }
        }
      });

      if (target === "recovery") {
        recoveryView.syncWithSystem(state.systemData);
      } else if (target === "matrix-editor") {
        renderCustomMatrixInputs();
      } else if (target === "detection") {
        ragDetection.fitToView();
      }
    });
  });
}

async function fetchScenarios() {
  try {
    const res = await fetch("/api/scenarios");
    if (!res.ok) return;
    const data = await res.json();
    state.scenarios = data.scenarios;

    // Populate scenario select title options if available
    const select = document.getElementById("scenario-select");
    if (select && data.summaries) {
      data.summaries.forEach((sum) => {
        const opt = select.querySelector(`option[value="${sum.key}"]`);
        if (opt) {
          opt.textContent = sum.title;
        }
      });
    }
  } catch (err) {
    console.error("Failed to fetch scenarios:", err);
  }
}

function initScenarioSelect() {
  const select = document.getElementById("scenario-select");
  if (!select) return;

  select.addEventListener("change", (e) => {
    const key = e.target.value;
    state.currentScenarioKey = key;

    if (key === "custom") {
      document.getElementById("tab-btn-matrix")?.click();
      return;
    }

    const sc = state.scenarios[key];
    if (sc) {
      state.systemData = {
        title: sc.title || key,
        available: [...sc.available],
        allocation: sc.allocation.map((r) => [...r]),
        request: sc.request.map((r) => [...r]),
        process_names: [...sc.process_names],
        resource_names: [...sc.resource_names],
      };

      const vivaNoteText = document.getElementById("viva-note-text");
      if (vivaNoteText) {
        vivaNoteText.textContent = sc.viva_note || "No specific viva note for this scenario.";
      }

      runDetection();
    }
  });
}

async function runDetection() {
  const payload = {
    available: state.systemData.available,
    allocation: state.systemData.allocation,
    request: state.systemData.request,
    process_names: state.systemData.process_names,
    resource_names: state.systemData.resource_names,
  };

  try {
    const res = await fetch("/api/detect", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const err = await res.json();
      alert(`Detection validation error: ${err.detail}`);
      return;
    }

    const report = await res.json();
    state.lastDetectionReport = report;

    // Load into playback and RAG
    playback.load(state.systemData, report);
    ragDetection.fitToView();

    renderInitialMatrixStrip();

    if (recoveryView) {
      recoveryView.syncWithSystem(state.systemData);
    }
  } catch (err) {
    console.error("Detection error:", err);
  }
}

/* ==========================================================================
   Matrix Strip (below detection graph)
   ========================================================================== */

function renderInitialMatrixStrip() {
  updateMatrixStrip(null, state.lastDetectionReport?.initial_finish || []);
}

function updateMatrixStrip(candidateIdx = null, finishFlags = []) {
  const strip = document.getElementById("matrix-strip");
  if (!strip || !state.lastDetectionReport) return;

  const { available, allocation, request, process_names, resource_names } = state.systemData;
  const n = allocation.length;
  const m = available.length;

  const buildTable = (title, headers, rows, isVector = false) => {
    let html = `<div class="strip-block"><h3 class="strip-title">${title}</h3>`;
    html += `<table class="data"><thead><tr>`;

    if (!isVector) {
      html += `<th scope="col" class="col-sticky">Process</th>`;
    }
    headers.forEach((h) => {
      html += `<th scope="col" class="num">${h}</th>`;
    });
    html += `</tr></thead><tbody>`;

    if (isVector) {
      html += `<tr>`;
      rows.forEach((v) => {
        html += `<td class="num mono">${v}</td>`;
      });
      html += `</tr>`;
    } else {
      rows.forEach((rowVals, i) => {
        const isCand = candidateIdx === i;
        const isDone = finishFlags[i] === true;
        const rowClass = `${isCand ? "hl" : ""} ${isDone ? "row-done" : ""}`;

        html += `<tr class="${rowClass}">`;
        html += `<th scope="row" class="col-sticky">${process_names[i]}</th>`;
        rowVals.forEach((val) => {
          html += `<td class="num mono">${val}</td>`;
        });
        html += `</tr>`;
      });
    }

    html += `</tbody></table></div>`;
    return html;
  };

  const allocHtml = buildTable("Allocation", resource_names, allocation);
  const reqHtml = buildTable("Request", resource_names, request);
  const availHtml = buildTable("Available", resource_names, available, true);

  strip.innerHTML = allocHtml + reqHtml + availHtml;
}

/* ==========================================================================
   Custom Matrix Editor
   ========================================================================== */

function initCustomMatrixEditor() {
  document.getElementById("btn-add-proc")?.addEventListener("click", () => {
    const n = state.systemData.allocation.length;
    const m = state.systemData.available.length;
    state.systemData.allocation.push(new Array(m).fill(0));
    state.systemData.request.push(new Array(m).fill(0));
    state.systemData.process_names.push(`P${n}`);
    renderCustomMatrixInputs();
  });

  document.getElementById("btn-add-res")?.addEventListener("click", () => {
    const m = state.systemData.available.length;
    state.systemData.available.push(1);
    state.systemData.allocation.forEach((r) => r.push(0));
    state.systemData.request.forEach((r) => r.push(0));
    state.systemData.resource_names.push(m < 26 ? String.fromCharCode(65 + m) : `R${m}`);
    renderCustomMatrixInputs();
  });

  document.getElementById("btn-load-scenario")?.addEventListener("click", () => {
    document.getElementById("tab-btn-detection")?.click();
  });

  document.getElementById("btn-apply-custom-matrix")?.addEventListener("click", () => {
    applyCustomMatrix();
  });
}

function removeProcessAt(index) {
  if (state.systemData.allocation.length <= 1) return;
  state.systemData.allocation.splice(index, 1);
  state.systemData.request.splice(index, 1);
  state.systemData.process_names.splice(index, 1);
  renderCustomMatrixInputs();
}

function removeResourceAt(index) {
  if (state.systemData.available.length <= 1) return;
  state.systemData.available.splice(index, 1);
  state.systemData.allocation.forEach((r) => r.splice(index, 1));
  state.systemData.request.forEach((r) => r.splice(index, 1));
  state.systemData.resource_names.splice(index, 1);
  renderCustomMatrixInputs();
}

function renderCustomMatrixInputs() {
  const { available, allocation, request, process_names, resource_names } = state.systemData;
  const n = allocation.length;
  const m = available.length;

  const emptyState = document.getElementById("matrix-empty");
  const matrixBody = document.getElementById("matrix-body");

  if (n === 0 || m === 0) {
    if (emptyState) emptyState.hidden = false;
    if (matrixBody) matrixBody.hidden = true;
    return;
  } else {
    if (emptyState) emptyState.hidden = true;
    if (matrixBody) matrixBody.hidden = false;
  }

  // 1. Available Table
  const availContainer = document.getElementById("custom-available-container");
  if (availContainer) {
    let html = `<table class="data data-edit"><thead><tr>`;
    for (let j = 0; j < m; j++) {
      html += `<th scope="col">
        <div class="head-cell">
          <input type="text" class="name-input res-name-input" data-j="${j}" value="${resource_names[j]}">
          ${m > 1 ? `<button type="button" class="btn-remove btn-del-res" data-j="${j}" title="Remove resource">Remove</button>` : ""}
        </div>
      </th>`;
    }
    html += `</tr></thead><tbody><tr>`;
    for (let j = 0; j < m; j++) {
      html += `<td>
        <input type="number" min="0" class="cell-input inp-avail" data-j="${j}" value="${available[j]}">
        <span class="cell-error" id="err-avail-${j}"></span>
      </td>`;
    }
    html += `</tr></tbody></table>`;
    availContainer.innerHTML = html;
  }

  // 2. Allocation Table
  const allocContainer = document.getElementById("custom-allocation-container");
  if (allocContainer) {
    allocContainer.innerHTML = buildEditableMatrixHtml("alloc", n, m, process_names, resource_names, allocation);
  }

  // 3. Request Table
  const reqContainer = document.getElementById("custom-request-container");
  if (reqContainer) {
    reqContainer.innerHTML = buildEditableMatrixHtml("req", n, m, process_names, resource_names, request);
  }

  attachEditorListeners();
}

function buildEditableMatrixHtml(prefix, n, m, procNames, resNames, matrix) {
  let html = `<table class="data data-edit"><thead><tr>`;
  html += `<th scope="col" class="col-sticky">Process</th>`;
  for (let j = 0; j < m; j++) {
    html += `<th scope="col">${resNames[j]}</th>`;
  }
  html += `<th></th></tr></thead><tbody>`;

  for (let i = 0; i < n; i++) {
    html += `<tr>`;
    html += `<th scope="row" class="col-sticky">
      <input type="text" class="name-input proc-name-input" data-i="${i}" value="${procNames[i]}">
    </th>`;

    for (let j = 0; j < m; j++) {
      html += `<td>
        <input type="number" min="0" class="cell-input inp-${prefix}" data-i="${i}" data-j="${j}" value="${matrix[i][j]}">
        <span class="cell-error" id="err-${prefix}-${i}-${j}"></span>
      </td>`;
    }

    html += `<td>
      ${n > 1 ? `<button type="button" class="btn-remove btn-del-proc" data-i="${i}" title="Remove process">Remove</button>` : ""}
    </td>`;

    html += `</tr>`;
  }

  html += `</tbody></table>`;
  return html;
}

function attachEditorListeners() {
  // Rename processes
  document.querySelectorAll(".proc-name-input").forEach((inp) => {
    inp.addEventListener("change", (e) => {
      const i = parseInt(e.target.dataset.i, 10);
      const val = e.target.value.trim();
      if (val) {
        state.systemData.process_names[i] = val;
        // Sync across tabs
        document.querySelectorAll(`.proc-name-input[data-i="${i}"]`).forEach((other) => {
          other.value = val;
        });
      }
    });
  });

  // Rename resources
  document.querySelectorAll(".res-name-input").forEach((inp) => {
    inp.addEventListener("change", (e) => {
      const j = parseInt(e.target.dataset.j, 10);
      const val = e.target.value.trim();
      if (val) {
        state.systemData.resource_names[j] = val;
        renderCustomMatrixInputs();
      }
    });
  });

  // Delete process buttons
  document.querySelectorAll(".btn-del-proc").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      const i = parseInt(e.target.dataset.i, 10);
      removeProcessAt(i);
    });
  });

  // Delete resource buttons
  document.querySelectorAll(".btn-del-res").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      const j = parseInt(e.target.dataset.j, 10);
      removeResourceAt(j);
    });
  });

  // Live cell validation
  const validateCells = () => {
    let hasError = false;
    const errorAlert = document.getElementById("matrix-error-alert");
    const applyBtn = document.getElementById("btn-apply-custom-matrix");

    document.querySelectorAll(".cell-input").forEach((inp) => {
      const val = parseInt(inp.value, 10);
      const isInvalid = isNaN(val) || val < 0;
      inp.classList.toggle("cell-input-invalid", isInvalid);

      let errSpan = null;
      if (inp.classList.contains("inp-avail")) {
        errSpan = document.getElementById(`err-avail-${inp.dataset.j}`);
      } else if (inp.classList.contains("inp-alloc")) {
        errSpan = document.getElementById(`err-alloc-${inp.dataset.i}-${inp.dataset.j}`);
      } else if (inp.classList.contains("inp-req")) {
        errSpan = document.getElementById(`err-req-${inp.dataset.i}-${inp.dataset.j}`);
      }

      if (errSpan) {
        errSpan.textContent = isInvalid ? "Cannot be negative." : "";
      }

      if (isInvalid) hasError = true;
    });

    if (errorAlert) {
      if (hasError) {
        errorAlert.textContent = "Values cannot be negative or blank.";
        errorAlert.hidden = false;
      } else {
        errorAlert.hidden = true;
      }
    }

    if (applyBtn) {
      applyBtn.disabled = hasError;
    }
  };

  document.querySelectorAll(".cell-input").forEach((inp) => {
    inp.addEventListener("input", validateCells);
  });
}

function applyCustomMatrix() {
  const m = state.systemData.available.length;
  const n = state.systemData.allocation.length;

  const newAvail = [];
  document.querySelectorAll(".inp-avail").forEach((inp) => {
    newAvail.push(parseInt(inp.value, 10) || 0);
  });

  const newAlloc = Array.from({ length: n }, () => new Array(m).fill(0));
  document.querySelectorAll(".inp-alloc").forEach((inp) => {
    const i = parseInt(inp.dataset.i, 10);
    const j = parseInt(inp.dataset.j, 10);
    newAlloc[i][j] = parseInt(inp.value, 10) || 0;
  });

  const newReq = Array.from({ length: n }, () => new Array(m).fill(0));
  document.querySelectorAll(".inp-req").forEach((inp) => {
    const i = parseInt(inp.dataset.i, 10);
    const j = parseInt(inp.dataset.j, 10);
    newReq[i][j] = parseInt(inp.value, 10) || 0;
  });

  state.systemData.available = newAvail;
  state.systemData.allocation = newAlloc;
  state.systemData.request = newReq;
  state.systemData.title = "Custom Matrix";

  // Switch to Detection Tab & Run
  document.getElementById("tab-btn-detection")?.click();
  runDetection();
}

/* ==========================================================================
   Export Handlers (JSON & PNG)
   ========================================================================== */

function initExportHandlers() {
  document.getElementById("btn-export-json")?.addEventListener("click", () => {
    const data = state.lastDetectionReport || state.systemData;
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `deadlock_report_${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
    document.getElementById("export-menu")?.removeAttribute("open");
  });

  document.getElementById("btn-export-png")?.addEventListener("click", () => {
    const svgEl = document.getElementById("rag-svg");
    if (!svgEl) return;

    const serializer = new XMLSerializer();
    const svgStr = serializer.serializeToString(svgEl);

    const canvas = document.createElement("canvas");
    canvas.width = 1920;
    canvas.height = 1080;
    const ctx = canvas.getContext("2d");

    const img = new Image();
    const svgBlob = new Blob([svgStr], { type: "image/svg+xml;charset=utf-8" });
    const url = URL.createObjectURL(svgBlob);

    img.onload = () => {
      // Paper-white sheet plate background
      ctx.fillStyle = "#FFFFFF";
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      URL.revokeObjectURL(url);

      const a = document.createElement("a");
      a.download = `resource_allocation_graph_${Date.now()}.png`;
      a.href = canvas.toDataURL("image/png");
      a.click();
      document.getElementById("export-menu")?.removeAttribute("open");
    };
    img.src = url;
  });
}

/* ==========================================================================
   Viva & Theory Guide
   ========================================================================== */

function renderVivaQA(qaList) {
  const container = document.getElementById("viva-qa-list");
  const searchInp = document.getElementById("viva-search");
  if (!container) return;

  function display(items) {
    container.innerHTML = "";
    items.forEach((item) => {
      const details = document.createElement("details");
      details.className = "qa-item";

      const summary = document.createElement("summary");
      summary.textContent = item.q;

      const ansP = document.createElement("p");
      ansP.className = "qa-answer";
      ansP.textContent = item.a;

      details.appendChild(summary);
      details.appendChild(ansP);
      container.appendChild(details);
    });
  }

  display(qaList);

  if (searchInp) {
    searchInp.addEventListener("input", (e) => {
      const val = e.target.value.toLowerCase();
      const filtered = qaList.filter(
        (item) => item.q.toLowerCase().includes(val) || item.a.toLowerCase().includes(val)
      );
      display(filtered);
    });
  }
}
