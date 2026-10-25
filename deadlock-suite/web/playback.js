/**
 * Playback Controller for Deadlock Detection Execution.
 *
 * Implements the lecture handout design:
 * - Slim transport bar under plate: first, previous, play/pause, next, last (SVG icons).
 * - Scrubber with tick marks for every step and current step label.
 * - Segmented text speed selector: 0.5x, 1x, 2x, 4x.
 * - Keyboard shortcuts: Space (play/pause), Left / Right (step), Home / End (jump).
 * - Step 0 shows "Initial state" with a plain sentence; unfinished processes are unresolved (not blocked).
 * - Work & Finish cells that changed on this step get the highlighter band.
 * - Current evaluated process gets highlighter in graph and matrix strip.
 * - Trace list numbered sequence with current row highlighted.
 * - Safe order with real arrows (P0 → P2 → P1) or Deadlocked set in red.
 */

export class PlaybackController {
  constructor(ragVisualizer, containerSelector = "#det-transport", onStepChangeCallback = null) {
    this.rag = ragVisualizer;
    this.container = document.querySelector(containerSelector);
    this.onStepChange = onStepChangeCallback;

    this.steps = [];
    this.currentStepIndex = -1; // -1 = initial state
    this.isPlaying = false;
    this.timer = null;
    this.speed = 1.0;
    this.systemData = null;
    this.detectionReport = null;

    // DOM Elements in Inspector
    this.stepTitle = document.getElementById("step-title");
    this.stepExplanation = document.getElementById("step-explanation");
    this.vecAvailable = document.getElementById("vec-available");
    this.vecWork = document.getElementById("vec-work");
    this.vecFinish = document.getElementById("vec-finish");
    this.outcomeLine = document.getElementById("outcome-line");
    this.traceLog = document.getElementById("trace-log");

    this.buildTransportBar();
    this.initKeyboard();
  }

  buildTransportBar() {
    if (!this.container) return;

    this.container.innerHTML = `
      <div class="transport-buttons" role="group" aria-label="Playback controls">
        <button type="button" class="icon-btn" id="btn-first" aria-label="First step" title="First step (Home)">
          <svg class="icon"><use href="#i-first"/></svg>
        </button>
        <button type="button" class="icon-btn" id="btn-prev" aria-label="Previous step" title="Previous step (Left Arrow)">
          <svg class="icon"><use href="#i-prev"/></svg>
        </button>
        <button type="button" class="icon-btn" id="btn-toggle" aria-label="Play" title="Play / Pause (Space)">
          <svg class="icon" id="icon-play-toggle"><use href="#i-play"/></svg>
        </button>
        <button type="button" class="icon-btn" id="btn-next" aria-label="Next step" title="Next step (Right Arrow)">
          <svg class="icon"><use href="#i-next"/></svg>
        </button>
        <button type="button" class="icon-btn" id="btn-last" aria-label="Last step" title="Last step (End)">
          <svg class="icon"><use href="#i-last"/></svg>
        </button>
      </div>

      <div class="scrubber">
        <input type="range" class="scrubber-range" id="scrubber-slider" min="0" max="0" value="0" aria-label="Step scrubber">
        <div class="scrubber-ticks" id="scrubber-ticks"></div>
        <div class="scrubber-label" id="scrubber-label" style="left: 0%;">Initial</div>
      </div>

      <div class="speed" role="radiogroup" aria-label="Playback speed">
        <button type="button" class="speed-option" data-speed="0.5" role="radio" aria-checked="false">0.5x</button>
        <button type="button" class="speed-option speed-current" data-speed="1" role="radio" aria-checked="true">1x</button>
        <button type="button" class="speed-option" data-speed="2" role="radio" aria-checked="false">2x</button>
        <button type="button" class="speed-option" data-speed="4" role="radio" aria-checked="false">4x</button>
      </div>
    `;

    this.btnFirst = this.container.querySelector("#btn-first");
    this.btnPrev = this.container.querySelector("#btn-prev");
    this.btnToggle = this.container.querySelector("#btn-toggle");
    this.btnNext = this.container.querySelector("#btn-next");
    this.btnLast = this.container.querySelector("#btn-last");
    this.scrubber = this.container.querySelector("#scrubber-slider");
    this.scrubberTicks = this.container.querySelector("#scrubber-ticks");
    this.scrubberLabel = this.container.querySelector("#scrubber-label");
    this.iconPlayToggle = this.container.querySelector("#icon-play-toggle use");

    this.btnFirst.addEventListener("click", () => this.jumpToFirst());
    this.btnPrev.addEventListener("click", () => this.stepBackward());
    this.btnToggle.addEventListener("click", () => this.togglePlay());
    this.btnNext.addEventListener("click", () => this.stepForward());
    this.btnLast.addEventListener("click", () => this.jumpToLast());

    this.scrubber.addEventListener("input", (e) => {
      const stepIdx = parseInt(e.target.value, 10) - 1;
      this.goToStep(stepIdx);
    });

    this.container.querySelectorAll(".speed-option").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        const spd = parseFloat(e.target.getAttribute("data-speed"));
        this.setSpeed(spd);
      });
    });
  }

  setSpeed(speedVal) {
    this.speed = speedVal;
    this.container.querySelectorAll(".speed-option").forEach((b) => {
      const match = parseFloat(b.getAttribute("data-speed")) === speedVal;
      b.classList.toggle("speed-current", match);
      b.setAttribute("aria-checked", match ? "true" : "false");
    });

    if (this.isPlaying) {
      this.pause();
      this.play();
    }
  }

  initKeyboard() {
    window.addEventListener("keydown", (e) => {
      if (e.target.tagName === "INPUT" || e.target.tagName === "SELECT" || e.target.tagName === "TEXTAREA") {
        return;
      }

      if (e.code === "Space") {
        e.preventDefault();
        this.togglePlay();
      } else if (e.code === "ArrowRight") {
        e.preventDefault();
        this.stepForward();
      } else if (e.code === "ArrowLeft") {
        e.preventDefault();
        this.stepBackward();
      } else if (e.code === "Home") {
        e.preventDefault();
        this.jumpToFirst();
      } else if (e.code === "End") {
        e.preventDefault();
        this.jumpToLast();
      }
    });
  }

  load(systemData, detectionReport) {
    this.pause();
    this.systemData = systemData;
    this.detectionReport = detectionReport;
    this.steps = detectionReport.steps || [];

    const totalSteps = this.steps.length;
    this.scrubber.max = totalSteps;
    this.scrubber.value = 0;
    this.currentStepIndex = -1;

    // Render ticks on scrubber
    this.renderScrubberTicks();
    this.populateTraceLog();
    this.updateUI();
  }

  renderScrubberTicks() {
    if (!this.scrubberTicks) return;
    this.scrubberTicks.innerHTML = "";

    const total = this.steps.length;
    if (total <= 0) return;

    for (let k = 0; k <= total; k++) {
      const pct = (k / total) * 100;
      const tick = document.createElement("div");
      tick.className = "tick";
      tick.style.left = `${pct}%`;
      this.scrubberTicks.appendChild(tick);
    }
  }

  populateTraceLog() {
    if (!this.traceLog) return;
    this.traceLog.innerHTML = "";

    if (this.steps.length === 0) {
      this.traceLog.innerHTML = `<li class="empty">No processes could finish: available resources do not satisfy any request.</li>`;
      return;
    }

    this.steps.forEach((step, idx) => {
      const li = document.createElement("li");
      li.className = "trace-item";

      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "trace-row";
      btn.id = `trace-row-${idx}`;
      btn.innerHTML = `${step.candidate_name} releases [${step.allocated.join(",")}] → Work [${step.work_after.join(",")}]`;
      btn.addEventListener("click", () => this.goToStep(idx));

      li.appendChild(btn);
      this.traceLog.appendChild(li);
    });
  }

  togglePlay() {
    if (this.isPlaying) {
      this.pause();
    } else {
      this.play();
    }
  }

  play() {
    if (this.steps.length === 0) return;
    if (this.currentStepIndex >= this.steps.length - 1) {
      this.currentStepIndex = -1;
    }

    this.isPlaying = true;
    if (this.iconPlayToggle) {
      this.iconPlayToggle.setAttribute("href", "#i-pause");
    }
    this.btnToggle.setAttribute("aria-label", "Pause");
    this.btnToggle.setAttribute("title", "Pause (Space)");

    const stepIntervalMs = 1200 / this.speed;

    this.timer = setInterval(() => {
      if (this.currentStepIndex < this.steps.length - 1) {
        this.stepForward();
      } else {
        this.pause();
      }
    }, stepIntervalMs);
  }

  pause() {
    this.isPlaying = false;
    clearInterval(this.timer);
    this.timer = null;
    if (this.iconPlayToggle) {
      this.iconPlayToggle.setAttribute("href", "#i-play");
    }
    this.btnToggle.setAttribute("aria-label", "Play");
    this.btnToggle.setAttribute("title", "Play (Space)");
  }

  jumpToFirst() {
    this.pause();
    this.goToStep(-1);
  }

  jumpToLast() {
    this.pause();
    this.goToStep(this.steps.length - 1);
  }

  stepForward() {
    if (this.currentStepIndex < this.steps.length - 1) {
      this.goToStep(this.currentStepIndex + 1);
    }
  }

  stepBackward() {
    if (this.currentStepIndex > -1) {
      this.goToStep(this.currentStepIndex - 1);
    }
  }

  goToStep(index) {
    this.currentStepIndex = index;
    this.updateUI();
  }

  updateUI() {
    const totalSteps = this.steps.length;
    const currentStepNum = this.currentStepIndex + 1; // 0 for initial state

    // Update scrubber value and label position
    this.scrubber.value = currentStepNum;
    const pct = totalSteps > 0 ? (currentStepNum / totalSteps) * 100 : 0;
    if (this.scrubberLabel) {
      this.scrubberLabel.style.left = `${pct}%`;
      this.scrubberLabel.textContent = this.currentStepIndex === -1 ? "Initial" : `Step ${currentStepNum} of ${totalSteps}`;
    }

    // Determine state arrays and changed cells
    const n = this.systemData.allocation.length;
    const m = this.systemData.available.length;

    let prevWork = [...this.systemData.available];
    let prevFinish = [...this.detectionReport.initial_finish];

    let currentWork = [...this.systemData.available];
    let currentFinish = [...this.detectionReport.initial_finish];
    let currentProcessStates = {};
    let candidateIdx = null;

    // Initial state: unfinished processes are "unresolved" (not blocked)
    for (let i = 0; i < n; i++) {
      if (this.detectionReport.initial_finish[i]) {
        currentProcessStates[i] = "finished";
      } else {
        currentProcessStates[i] = "unresolved";
      }
    }

    if (this.currentStepIndex >= 0) {
      // Find state right before this step to identify changed cells
      for (let k = 0; k < this.currentStepIndex; k++) {
        const st = this.steps[k];
        prevWork = [...st.work_after];
        prevFinish = [...st.finish_snapshot];
      }

      for (let k = 0; k <= this.currentStepIndex; k++) {
        const st = this.steps[k];
        currentWork = [...st.work_after];
        currentFinish = [...st.finish_snapshot];
        currentProcessStates[st.candidate] = "finished";
      }

      candidateIdx = this.steps[this.currentStepIndex].candidate;
    }

    // 1. Step title & explanation
    if (this.currentStepIndex === -1) {
      if (this.stepTitle) this.stepTitle.textContent = "Initial state";
      if (this.stepExplanation) {
        this.stepExplanation.textContent = "Available resources initialized. Processes with zero allocation start as finished.";
      }
    } else {
      const step = this.steps[this.currentStepIndex];
      if (this.stepTitle) this.stepTitle.textContent = `Step ${step.step_no} of ${totalSteps}`;
      if (this.stepExplanation) {
        this.stepExplanation.textContent = `${step.candidate_name} can finish: its request [${step.request.join(",")}] fits in Work [${step.work_before.join(",")}]. It releases [${step.allocated.join(",")}].`;
      }
    }

    // 2. Render State vectors (with highlighter on changed cells)
    this.renderVectorCells(this.vecAvailable, this.systemData.available, []);
    const changedWorkIndices = [];
    if (this.currentStepIndex >= 0) {
      for (let j = 0; j < m; j++) {
        if (currentWork[j] !== prevWork[j]) changedWorkIndices.push(j);
      }
    }
    this.renderVectorCells(this.vecWork, currentWork, changedWorkIndices);

    const changedFinishIndices = [];
    if (this.currentStepIndex >= 0) {
      for (let i = 0; i < n; i++) {
        if (currentFinish[i] !== prevFinish[i]) changedFinishIndices.push(i);
      }
    }
    this.renderFinishCells(this.vecFinish, currentFinish, changedFinishIndices);

    // 3. Outcome line (Safe order or Deadlocked set)
    if (this.outcomeLine) {
      const isAtEnd = this.currentStepIndex === totalSteps - 1;
      if (!this.detectionReport.deadlocked) {
        // Safe order: fill in as steps complete
        const safeOrderProcs = [];
        for (let k = 0; k <= this.currentStepIndex; k++) {
          safeOrderProcs.push(this.systemData.process_names[this.steps[k].candidate]);
        }
        if (safeOrderProcs.length > 0) {
          this.outcomeLine.innerHTML = `<span class="outcome-label">Safe order</span> <span class="outcome-safe">${safeOrderProcs.join(" → ")}</span>`;
        } else {
          this.outcomeLine.innerHTML = `<span class="outcome-label">Safe order</span> <span class="soft">None yet</span>`;
        }
      } else {
        if (isAtEnd) {
          const deadNames = this.detectionReport.deadlocked_processes.map((i) => this.systemData.process_names[i]);
          this.outcomeLine.innerHTML = `<span class="outcome-label">Deadlocked</span> <span class="outcome-dead">${deadNames.join(", ")}</span>`;
        } else {
          this.outcomeLine.innerHTML = `<span class="outcome-label">Deadlocked</span> <span class="soft">Evaluating…</span>`;
        }
      }
    }

    // 4. Highlight current trace row
    for (let idx = 0; idx < totalSteps; idx++) {
      const row = document.getElementById(`trace-row-${idx}`);
      if (row) {
        const isCurrent = idx === this.currentStepIndex;
        const isDone = idx < this.currentStepIndex;
        row.classList.toggle("hl", isCurrent);
        row.classList.toggle("trace-row-done", isDone && !isCurrent);
        if (isCurrent) {
          row.scrollIntoView({ block: "nearest", behavior: "smooth" });
        }
      }
    }

    // 5. Update RAG visualizer
    const isAtEnd = this.currentStepIndex === totalSteps - 1;
    const showCycles = isAtEnd && this.detectionReport.deadlocked;

    // On deadlocked final frame, mark deadlocked processes
    if (isAtEnd && this.detectionReport.deadlocked) {
      this.detectionReport.deadlocked_processes.forEach((pIdx) => {
        currentProcessStates[pIdx] = "deadlocked";
      });
    }

    this.rag.render(
      this.systemData,
      this.detectionReport,
      currentProcessStates,
      showCycles ? this.detectionReport.deadlock_cycles : [],
      null,
      candidateIdx
    );

    // 6. Notify matrix strip and external listeners
    if (this.onStepChange) {
      this.onStepChange(this.currentStepIndex, candidateIdx, currentFinish);
    }
  }

  renderVectorCells(container, values, changedIndices) {
    if (!container) return;
    const changedSet = new Set(changedIndices);
    container.innerHTML = `[${values.map((v, idx) => {
      const isChanged = changedSet.has(idx);
      return `<span class="vec-cell ${isChanged ? "hl" : ""}">${v}</span>`;
    }).join(", ")}]`;
  }

  renderFinishCells(container, flags, changedIndices) {
    if (!container) return;
    const changedSet = new Set(changedIndices);
    container.innerHTML = `[${flags.map((f, idx) => {
      const isChanged = changedSet.has(idx);
      const text = f ? "T" : "F";
      return `<span class="vec-cell ${isChanged ? "hl" : ""}">${text}</span>`;
    }).join(" ")}]`;
  }
}
