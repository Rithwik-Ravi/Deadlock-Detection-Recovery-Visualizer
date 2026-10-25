/**
 * Resource Allocation Graph (RAG) Visualizer using D3.js v7.
 *
 * Implements the marked-up lecture handout design:
 * - Graph-paper background (24px minor, 120px major) that zooms with content.
 * - Barycenter-ordered columns: processes on left, resources on right, wide channel between.
 * - Nodes: Circles for processes (marks for states, highlighter band when evaluated),
 *   Rectangles for resources (labels outside above, instance grid inside).
 * - Edges: Cubic Bezier with horizontal tangents, arrowheads stopping exactly at node boundaries.
 *   Parallel offset when both holding & requesting same resource.
 * - Multiplicity pills: placed on curve at ~30% from process end, collision nudged.
 * - Hover / Focus dimming to 8%, node pin on click, Escape to clear.
 * - Allocations / Requests visibility toggles.
 * - ResizeObserver responsive layout with auto-fit and Fit button.
 */

/* global d3 */

export class RAGVisualizer {
  constructor(svgSelector, tooltipSelector, options = {}) {
    this.svg = d3.select(svgSelector);
    this.svgNode = this.svg.node();
    this.plateNode = this.svgNode ? this.svgNode.parentElement : null;
    this.tooltip = d3.select(tooltipSelector || "#rag-tooltip");
    this.captionId = options.captionId || null;
    this.legendId = options.legendId || null;

    this.showAllocations = true;
    this.showRequests = true;
    this.pinnedNodeId = null;
    this.hoveredNodeId = null;

    this.systemData = null;
    this.report = null;
    this.processStates = null;
    this.activeCycles = null;
    this.ious = null;
    this.evaluatingProcIdx = null;

    this.width = 960;
    this.height = 540;

    this.initSvg();
    this.initResizeObserver();
    this.initKeyboard();
  }

  initSvg() {
    this.svg.selectAll("*").remove();

    // Definitions: Graph paper patterns and arrow markers
    const defs = this.svg.append("defs");

    // Grid paper pattern
    const patternMinor = defs.append("pattern")
      .attr("id", `grid-minor-${this.getUid()}`)
      .attr("width", 24)
      .attr("height", 24)
      .attr("patternUnits", "userSpaceOnUse");
    patternMinor.append("path")
      .attr("d", "M 24 0 L 0 0 0 24")
      .attr("class", "rag-grid-minor");

    const patternMajor = defs.append("pattern")
      .attr("id", `grid-major-${this.getUid()}`)
      .attr("width", 120)
      .attr("height", 120)
      .attr("patternUnits", "userSpaceOnUse");
    patternMajor.append("rect")
      .attr("width", 120)
      .attr("height", 120)
      .attr("fill", `url(#grid-minor-${this.getUid()})`);
    patternMajor.append("path")
      .attr("d", "M 120 0 L 0 0 0 120")
      .attr("class", "rag-grid-major");

    this.gridPatternId = `grid-major-${this.getUid()}`;

    // Root zoom container
    this.container = this.svg.append("g").attr("class", "rag-zoom-container");

    // Background graph paper (huge rect inside zoomed container so it scales/pans)
    this.bgGrid = this.container.append("rect")
      .attr("class", "rag-grid-bg")
      .attr("x", -10000)
      .attr("y", -10000)
      .attr("width", 20000)
      .attr("height", 20000)
      .attr("fill", `url(#${this.gridPatternId})`);

    // Drawing layers
    this.edgeGroup = this.container.append("g").attr("class", "rag-layer-edges");
    this.arrowGroup = this.container.append("g").attr("class", "rag-layer-arrows");
    this.pillGroup = this.container.append("g").attr("class", "rag-layer-pills");
    this.nodeGroup = this.container.append("g").attr("class", "rag-layer-nodes");

    // Zoom behavior
    this.zoomBehavior = d3.zoom()
      .scaleExtent([0.3, 4.0])
      .on("zoom", (event) => {
        this.container.attr("transform", event.transform);
      });

    this.svg.call(this.zoomBehavior).on("dblclick.zoom", null);

    // Click on background unpins focus
    this.svg.on("click", (event) => {
      if (event.target === this.svgNode || event.target === this.bgGrid.node()) {
        this.clearPin();
      }
    });

    this.updateDimensions();
  }

  getUid() {
    if (!this._uid) {
      this._uid = Math.random().toString(36).substring(2, 8);
    }
    return this._uid;
  }

  initResizeObserver() {
    if (!this.plateNode || typeof ResizeObserver === "undefined") return;
    this.resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const cr = entry.contentRect;
        if (cr.width > 20 && cr.height > 20) {
          this.width = cr.width;
          this.height = cr.height;
          this.svg.attr("viewBox", `0 0 ${this.width} ${this.height}`);
          if (this.systemData) {
            this.recomputeAndRender();
          }
        }
      }
    });
    this.resizeObserver.observe(this.plateNode);
  }

  initKeyboard() {
    window.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && this.pinnedNodeId) {
        this.clearPin();
      }
    });
  }

  updateDimensions() {
    if (this.plateNode) {
      const rect = this.plateNode.getBoundingClientRect();
      if (rect.width > 50 && rect.height > 50) {
        this.width = rect.width;
        this.height = rect.height;
      }
    }
    this.svg.attr("viewBox", `0 0 ${this.width} ${this.height}`);
  }

  setEdgeVisibility(allocations, requests) {
    this.showAllocations = allocations;
    this.showRequests = requests;
    this.applyEdgeVisibility();
  }

  applyEdgeVisibility() {
    this.edgeGroup.selectAll("path.edge").each(function () {
      const el = d3.select(this);
      const isAlloc = el.classed("edge--alloc") || el.classed("edge--allocation");
      const isReq = el.classed("edge--req") || el.classed("edge--request");
      const isLedger = el.classed("edge--ledger") || el.classed("edge--iou");

      if (isLedger) return;
      if (isAlloc) el.classed("edge--hidden", !this.showAllocations);
      if (isReq) el.classed("edge--hidden", !this.showRequests);
    }.bind(this));

    this.arrowGroup.selectAll("path.arrow").each(function () {
      const el = d3.select(this);
      const isAlloc = el.classed("arrow--alloc") || el.classed("arrow--allocation");
      const isReq = el.classed("arrow--req") || el.classed("arrow--request");
      const isLedger = el.classed("arrow--ledger") || el.classed("arrow--iou");

      if (isLedger) return;
      if (isAlloc) el.classed("edge--hidden", !this.showAllocations);
      if (isReq) el.classed("edge--hidden", !this.showRequests);
    }.bind(this));

    this.pillGroup.selectAll("g.pill").each(function () {
      const el = d3.select(this);
      const isAlloc = el.classed("pill--alloc") || el.classed("pill--allocation");
      const isReq = el.classed("pill--req") || el.classed("pill--request");
      const isLedger = el.classed("pill--ledger") || el.classed("pill--iou");

      if (isLedger) return;
      if (isAlloc) el.classed("edge--hidden", !this.showAllocations);
      if (isReq) el.classed("edge--hidden", !this.showRequests);
    }.bind(this));
  }

  zoomIn() {
    this.svg.transition().duration(200).call(this.zoomBehavior.scaleBy, 1.25);
  }

  zoomOut() {
    this.svg.transition().duration(200).call(this.zoomBehavior.scaleBy, 0.8);
  }

  zoomReset() {
    this.fitToView();
  }

  fitToView() {
    if (!this.nodes || this.nodes.length === 0) {
      this.svg.transition().duration(250).call(this.zoomBehavior.transform, d3.zoomIdentity);
      return;
    }

    let minX = Infinity;
    let maxX = -Infinity;
    let minY = Infinity;
    let maxY = -Infinity;

    for (const d of this.nodes) {
      const r = d.type === "process" ? d.radius : d.boxWidth / 2;
      const ry = d.type === "process" ? d.radius : d.boxHeight / 2 + 25;
      minX = Math.min(minX, d.x - r);
      maxX = Math.max(maxX, d.x + r);
      minY = Math.min(minY, d.y - ry);
      maxY = Math.max(maxY, d.y + ry);
    }

    const pad = 40;
    const graphW = Math.max(100, maxX - minX + pad * 2);
    const graphH = Math.max(100, maxY - minY + pad * 2);

    const scale = Math.min(1.2, Math.max(0.4, Math.min(this.width / graphW, this.height / graphH)));
    const centerX = (minX + maxX) / 2;
    const centerY = (minY + maxY) / 2;

    const tx = this.width / 2 - centerX * scale;
    const ty = this.height / 2 - centerY * scale;

    const transform = d3.zoomIdentity.translate(tx, ty).scale(scale);
    this.svg.transition().duration(300).call(this.zoomBehavior.transform, transform);
  }

  /**
   * Main render call.
   */
  render(systemData, report = null, processStates = null, activeCycles = null, ious = null, evaluatingIdx = null) {
    this.systemData = systemData;
    this.report = report;
    this.processStates = processStates;
    this.activeCycles = activeCycles;
    this.ious = ious;
    this.evaluatingProcIdx = evaluatingIdx;

    this.recomputeAndRender();
  }

  recomputeAndRender() {
    if (!this.systemData) return;
    this.updateDimensions();

    const { available, allocation, request, process_names, resource_names, total_resources } = this.systemData;
    const n = allocation.length;
    const m = available.length;

    const deadlockedProcs = new Set(this.report?.deadlocked_processes || []);
    const cycleNodes = new Set();
    const cycleEdgeKeys = new Set();

    const cyclesToProcess = this.activeCycles && this.activeCycles.length > 0
      ? this.activeCycles
      : (this.report?.deadlock_cycles || []);

    cyclesToProcess.forEach((cycle) => {
      for (let i = 0; i < cycle.length; i++) {
        cycleNodes.add(cycle[i]);
        const next = cycle[(i + 1) % cycle.length];
        cycleEdgeKeys.add(`${cycle[i]}->${next}`);
      }
    });

    // 1. Barycenter ordering heuristic
    // Processes order and Resource order
    const procOrder = Array.from({ length: n }, (_, i) => i);
    const resOrder = Array.from({ length: m }, (_, j) => j);

    // Iterative barycenter sweeps (4 passes)
    for (let pass = 0; pass < 4; pass++) {
      // Update resource order by average position of connected processes
      const resAvg = resOrder.map((j) => {
        let sum = 0;
        let count = 0;
        for (let i = 0; i < n; i++) {
          if (allocation[i][j] > 0 || request[i][j] > 0) {
            sum += procOrder.indexOf(i);
            count++;
          }
        }
        return { j, avg: count > 0 ? sum / count : j };
      });
      resAvg.sort((a, b) => a.avg - b.avg || a.j - b.j);
      resAvg.forEach((item, idx) => { resOrder[idx] = item.j; });

      // Update process order by average position of connected resources
      const procAvg = procOrder.map((i) => {
        let sum = 0;
        let count = 0;
        for (let j = 0; j < m; j++) {
          if (allocation[i][j] > 0 || request[i][j] > 0) {
            sum += resOrder.indexOf(j);
            count++;
          }
        }
        return { i, avg: count > 0 ? sum / count : i };
      });
      procAvg.sort((a, b) => a.avg - b.avg || a.i - b.i);
      procAvg.forEach((item, idx) => { procOrder[idx] = item.i; });
    }

    // 2. Geometry & Coordinates
    // Process radius: clamp(22, height / (2.6 * n), 32)
    const procRadius = Math.max(22, Math.min(32, (this.height - 80) / Math.max(1, n * 2.2)));
    const padX = Math.max(60, Math.min(100, this.width * 0.1));
    const procX = padX + procRadius;

    // Distribute processes vertically across available height
    const topMargin = 50;
    const botMargin = 50;
    const usableH = Math.max(150, this.height - topMargin - botMargin);

    const procYMap = new Map();
    if (n === 1) {
      procYMap.set(procOrder[0], this.height / 2);
    } else {
      const step = usableH / (n - 1);
      procOrder.forEach((pIdx, rank) => {
        procYMap.set(pIdx, topMargin + rank * step);
      });
    }

    // Build process nodes
    this.nodes = [];
    for (let i = 0; i < n; i++) {
      let state = "unresolved"; // Default at step 0: uncolored ink outline
      if (this.processStates && this.processStates[i]) {
        state = this.processStates[i];
      } else if (this.report) {
        if (deadlockedProcs.has(i)) {
          state = "deadlocked";
        } else if (this.report.finished_processes && this.report.finished_processes.includes(i)) {
          state = "finished";
        } else if (this.report.initial_finish && this.report.initial_finish[i]) {
          state = "finished";
        } else {
          state = "unresolved";
        }
      }

      this.nodes.push({
        id: `P${i}`,
        type: "process",
        idx: i,
        name: process_names[i] || `P${i}`,
        state: state,
        isCycle: cycleNodes.has(i),
        isEvaluating: this.evaluatingProcIdx === i,
        allocation: allocation[i],
        request: request[i],
        radius: procRadius,
        x: procX,
        y: procYMap.get(i) || this.height / 2,
      });
    }

    // Resource box width & height based on instances
    const resNodeData = [];
    for (let j = 0; j < m; j++) {
      const total = total_resources ? total_resources[j] : (available[j] + allocation.reduce((acc, row) => acc + row[j], 0));
      const allocatedUnits = allocation.reduce((acc, row) => acc + row[j], 0);
      const freeUnits = available[j];

      // Grid of instances (at most 4 rows, up to 6 per row)
      const cols = total <= 4 ? total : Math.min(6, Math.ceil(Math.sqrt(total * 1.5)));
      const rows = Math.min(4, Math.ceil(total / cols));
      const dotSpacing = 14;
      const boxW = Math.max(76, (cols + 1) * dotSpacing + 12);
      const boxH = Math.max(38, (rows + 1) * dotSpacing + 8);

      resNodeData.push({
        idx: j,
        total,
        allocatedUnits,
        freeUnits,
        cols,
        rows,
        boxW,
        boxH,
      });
    }

    const maxBoxW = Math.max(...resNodeData.map((d) => d.boxW));
    const resX = this.width - padX - maxBoxW / 2;

    const resYMap = new Map();
    if (m === 1) {
      resYMap.set(resOrder[0], this.height / 2);
    } else {
      const step = usableH / (m - 1);
      resOrder.forEach((rIdx, rank) => {
        resYMap.set(rIdx, topMargin + rank * step);
      });
    }

    // Build resource nodes
    for (let j = 0; j < m; j++) {
      const rData = resNodeData[j];
      this.nodes.push({
        id: `R${j}`,
        type: "resource",
        idx: j,
        name: resource_names[j] || `R${j}`,
        totalUnits: rData.total,
        allocatedUnits: rData.allocatedUnits,
        freeUnits: rData.freeUnits,
        cols: rData.cols,
        rows: rData.rows,
        boxWidth: rData.boxW,
        boxHeight: rData.boxH,
        x: resX,
        y: resYMap.get(j) || this.height / 2,
      });
    }

    // 3. Build Edges
    this.links = [];

    // Check for pairs that have both allocation and request to apply parallel offset
    const pairBoth = new Set();
    for (let i = 0; i < n; i++) {
      for (let j = 0; j < m; j++) {
        if (allocation[i][j] > 0 && request[i][j] > 0) {
          pairBoth.add(`P${i}-R${j}`);
        }
      }
    }

    // Allocations: Resource -> Process
    for (let i = 0; i < n; i++) {
      for (let j = 0; j < m; j++) {
        const units = allocation[i][j];
        if (units > 0) {
          const hasBoth = pairBoth.has(`P${i}-R${j}`);
          this.links.push({
            id: `alloc-R${j}-P${i}`,
            sourceId: `R${j}`,
            targetId: `P${i}`,
            type: "allocation",
            units: units,
            resIdx: j,
            procIdx: i,
            offsetY: hasBoth ? -7 : 0, // Parallel offset so they don't overlap
            isCycle: false,
          });
        }
      }
    }

    // Requests: Process -> Resource
    for (let i = 0; i < n; i++) {
      for (let j = 0; j < m; j++) {
        const units = request[i][j];
        if (units > 0) {
          const hasBoth = pairBoth.has(`P${i}-R${j}`);
          this.links.push({
            id: `req-P${i}-R${j}`,
            sourceId: `P${i}`,
            targetId: `R${j}`,
            type: "request",
            units: units,
            resIdx: j,
            procIdx: i,
            offsetY: hasBoth ? 7 : 0, // Parallel offset
            isCycle: false,
          });
        }
      }
    }

    // Mark edges on deadlock cycle
    for (const link of this.links) {
      if (link.type === "request") {
        if (cycleNodes.has(link.procIdx)) {
          // Process is in cycle requesting this resource
          link.isCycle = true;
        }
      } else if (link.type === "allocation") {
        if (cycleNodes.has(link.procIdx)) {
          link.isCycle = true;
        }
      }
    }

    // IOU Edges (DLR recovery)
    if (this.ious && this.ious.length > 0) {
      this.ious.forEach((iou) => {
        if (!iou.repaid) {
          this.links.push({
            id: `iou-${iou.entry_id}`,
            sourceId: `R${iou.resource_idx}`,
            targetId: `P${iou.creditor_idx}`,
            type: "iou",
            units: iou.units,
            label: `IOU: ${iou.units}`,
            offsetY: -14,
            isCycle: false,
          });
        }
      });
    }

    this.renderD3();
    this.updateCaptionAndLegend();
  }

  renderD3() {
    const nodeMap = new Map(this.nodes.map((d) => [d.id, d]));

    // Compute curve path, clipped endpoints, and arrowheads
    const computeEdgeGeometry = (link) => {
      const s = nodeMap.get(link.sourceId);
      const t = nodeMap.get(link.targetId);
      if (!s || !t) return null;

      const offsetY = link.offsetY || 0;

      // Identify whether source/target is process or resource
      let pNode = null;
      let rNode = null;
      let isProcToRes = false;

      if (s.type === "process") {
        pNode = s;
        rNode = t;
        isProcToRes = true;
      } else {
        rNode = s;
        pNode = t;
        isProcToRes = false;
      }

      // Process border point: circle intersection
      // Horizontal tangent towards the right channel
      const pBorderX = pNode.x + pNode.radius;
      const pBorderY = pNode.y + offsetY;

      // Resource border point: left border of box
      const rBorderX = rNode.x - rNode.boxWidth / 2;
      const rBorderY = rNode.y + offsetY;

      let startX, startY, endX, endY, tangentEndX, tangentEndY;

      if (isProcToRes) {
        // Request: P -> R (left to right)
        startX = pBorderX;
        startY = pBorderY;
        endX = rBorderX;
        endY = rBorderY;
        tangentEndX = -1; // incoming arrow pointing right
        tangentEndY = 0;
      } else {
        // Allocation: R -> P (right to left)
        startX = rBorderX;
        startY = rBorderY;
        endX = pBorderX;
        endY = pBorderY;
        tangentEndX = 1; // incoming arrow pointing left
        tangentEndY = 0;
      }

      // Control points for smooth horizontal tangent Bezier
      const dx = Math.abs(endX - startX);
      const cpDist = Math.max(40, dx * 0.45);

      const cp1X = isProcToRes ? startX + cpDist : startX - cpDist;
      const cp1Y = startY;
      const cp2X = isProcToRes ? endX - cpDist : endX + cpDist;
      const cp2Y = endY;

      const pathData = `M ${startX} ${startY} C ${cp1X} ${cp1Y}, ${cp2X} ${cp2Y}, ${endX} ${endY}`;

      // Arrowhead geometry: triangle terminating exactly at (endX, endY)
      const arrowSize = 7;
      let arrowPath = "";
      if (isProcToRes) {
        // pointing right at (endX, endY)
        arrowPath = `M ${endX} ${endY} L ${endX - arrowSize * 1.3} ${endY - arrowSize * 0.6} L ${endX - arrowSize * 1.3} ${endY + arrowSize * 0.6} Z`;
      } else {
        // pointing left at (endX, endY)
        arrowPath = `M ${endX} ${endY} L ${endX + arrowSize * 1.3} ${endY - arrowSize * 0.6} L ${endX + arrowSize * 1.3} ${endY + arrowSize * 0.6} Z`;
      }

      // Multiplicity pill position: evaluate Bezier at t = 0.3 from the process side
      const tParam = isProcToRes ? 0.3 : 0.7;
      const pillPos = evaluateCubicBezier(startX, startY, cp1X, cp1Y, cp2X, cp2Y, endX, endY, tParam);

      return {
        pathData,
        arrowPath,
        pillX: pillPos.x,
        pillY: pillPos.y,
        units: link.units,
        label: link.label || `×${link.units}`,
        type: link.type,
      };
    };

    // Helper to map link type to CSS modifier abbreviations
    const typeToSuffix = (type) => {
      if (type === "allocation") return "alloc";
      if (type === "request") return "req";
      if (type === "iou") return "ledger";
      return type;
    };

    // 1. Render Edges
    const linkSel = this.edgeGroup.selectAll("path.edge").data(this.links, (d) => d.id);
    linkSel.exit().remove();

    const linkEnter = linkSel.enter().append("path");

    const linkAll = linkEnter.merge(linkSel)
      .attr("class", (d) => {
        const sfx = typeToSuffix(d.type);
        let cls = `edge edge--${sfx} edge--${d.type}`;
        if (d.isCycle) cls += " edge--cycle";
        if (this.processStates && this.processStates[d.procIdx] === "finished") {
          cls += " edge--done";
        }
        return cls;
      })
      .attr("stroke-width", (d) => {
        if (d.isCycle) return 3;
        if (d.units > 1) return Math.min(3, 1.5 + (d.units - 1) * 0.35);
        return 1.5;
      })
      .attr("d", (d) => {
        const geom = computeEdgeGeometry(d);
        d._geom = geom;
        return geom ? geom.pathData : "";
      });

    // 2. Render Arrowheads (exact boundary markers)
    const arrowSel = this.arrowGroup.selectAll("path.arrow").data(this.links, (d) => d.id);
    arrowSel.exit().remove();
    arrowSel.enter().append("path")
      .merge(arrowSel)
      .attr("class", (d) => {
        const sfx = typeToSuffix(d.type);
        let cls = `arrow arrow--${sfx} arrow--${d.type}`;
        if (d.isCycle) cls += " arrow--cycle";
        if (this.processStates && this.processStates[d.procIdx] === "finished") {
          cls += " edge--done";
        }
        return cls;
      })
      .attr("d", (d) => (d._geom ? d._geom.arrowPath : ""));

    // 3. Render Multiplicity Pills (only when units > 1 or IOU)
    const pillData = this.links.filter((d) => d.units > 1 || d.type === "iou");

    // Collision avoidance: sort by Y and nudge if too close
    pillData.sort((a, b) => (a._geom?.pillY || 0) - (b._geom?.pillY || 0));
    for (let i = 1; i < pillData.length; i++) {
      const prev = pillData[i - 1]._geom;
      const curr = pillData[i]._geom;
      if (prev && curr) {
        const dist = Math.abs(curr.pillY - prev.pillY);
        const distDistX = Math.abs(curr.pillX - prev.pillX);
        if (dist < 18 && distDistX < 35) {
          curr.pillY = prev.pillY + 20; // Nudge downward
        }
      }
    }

    const pillSel = this.pillGroup.selectAll("g.pill").data(pillData, (d) => d.id);
    pillSel.exit().remove();

    const pillEnter = pillSel.enter().append("g").attr("class", (d) => {
      const sfx = typeToSuffix(d.type);
      return `pill pill--${sfx} pill--${d.type}`;
    });
    pillEnter.append("rect").attr("class", "pill-box");
    pillEnter.append("text").attr("class", "pill-text");

    const pillAll = pillEnter.merge(pillSel);
    pillAll.attr("transform", (d) => `translate(${d._geom.pillX}, ${d._geom.pillY})`);

    pillAll.select("text.pill-text")
      .attr("class", (d) => `pill-text ${d.type === "iou" ? "pill-text--ledger" : ""}`)
      .attr("font-size", "11px")
      .text((d) => d._geom.label);

    pillAll.each(function (d) {
      const g = d3.select(this);
      const textEl = g.select("text.pill-text").node();
      if (textEl) {
        const bbox = textEl.getBBox();
        const pw = Math.max(22, bbox.width + 10);
        const ph = 16;
        g.select("rect.pill-box")
          .attr("x", -pw / 2)
          .attr("y", -ph / 2)
          .attr("width", pw)
          .attr("height", ph)
          .attr("rx", 4);
      }
    });

    // 4. Render Nodes
    const nodeSel = this.nodeGroup.selectAll("g.node").data(this.nodes, (d) => d.id);
    nodeSel.exit().remove();

    const nodeEnter = nodeSel.enter().append("g")
      .attr("class", (d) => `node node--${d.type}`)
      .attr("tabindex", "0")
      .attr("role", "button")
      .attr("aria-label", (d) => d.name);

    // Setup Process Node Elements
    const procEnter = nodeEnter.filter((d) => d.type === "process");

    // Highlighter band (behind node)
    procEnter.append("path").attr("class", "node-hl");

    // Focus ring
    procEnter.append("circle").attr("class", "node-focus");

    // Main ring
    procEnter.append("circle").attr("class", "ring");

    // Marks for process states
    // Check mark (finished)
    const checkGroup = procEnter.append("g").attr("class", "mark mark-check");
    checkGroup.append("circle").attr("class", "mark-check-bg").attr("r", 9).attr("cx", 18).attr("cy", -18);
    checkGroup.append("path").attr("d", "M 14 -18 L 17 -15 L 23 -21");

    // Diagonal hatch (deadlocked)
    procEnter.append("path").attr("class", "mark mark-hatch");

    // Pause mark (suspended)
    const pauseGroup = procEnter.append("g").attr("class", "mark mark-pause");
    pauseGroup.append("line").attr("x1", -5).attr("y1", -8).attr("x2", -5).attr("y2", 8);
    pauseGroup.append("line").attr("x1", 5).attr("y1", -8).attr("x2", 5).attr("y2", 8);

    // Strike-through line (aborted)
    procEnter.append("line").attr("class", "mark mark-strike");

    // Process text label
    procEnter.append("text").attr("class", "node-label");

    // Setup Resource Node Elements
    const resEnter = nodeEnter.filter((d) => d.type === "resource");
    resEnter.append("rect").attr("class", "node-focus");
    resEnter.append("rect").attr("class", "res-box");
    resEnter.append("text").attr("class", "res-name");
    resEnter.append("text").attr("class", "res-free");
    resEnter.append("g").attr("class", "res-instances");

    const nodeAll = nodeEnter.merge(nodeSel)
      .attr("transform", (d) => `translate(${d.x}, ${d.y})`);

    // Update Process Nodes
    nodeAll.filter((d) => d.type === "process").each(function (d) {
      const g = d3.select(this);
      const r = d.radius;

      // Focus indicator
      g.select("circle.node-focus")
        .attr("r", r + 4);

      // Highlighter band: slightly irregular organic rounded path behind node
      const hlPath = `M ${-r - 8} ${-r - 4} Q ${0} ${-r - 7} ${r + 8} ${-r - 5} Q ${r + 10} ${0} ${r + 7} ${r + 6} Q ${0} ${r + 8} ${-r - 8} ${r + 5} Z`;
      g.select("path.node-hl")
        .attr("d", hlPath)
        .classed("node-hl-on", d.isEvaluating);

      // Main circle ring
      const ring = g.select("circle.ring")
        .attr("r", r)
        .attr("class", "ring");

      // State marks & rings
      g.selectAll(".mark").classed("mark-on", false);
      g.select("text.node-label").attr("class", "node-label");

      if (d.state === "finished") {
        ring.classed("ring--ok", true);
        g.select(".mark-check").classed("mark-on", true);
      } else if (d.state === "deadlocked") {
        ring.classed("ring--dead", true);
        const hatchEl = g.select(".mark-hatch");
        hatchEl.classed("mark-on", true)
          .attr("d", `M ${-r * 0.6} ${r * 0.4} L ${r * 0.4} ${-r * 0.6} M ${-r * 0.4} ${r * 0.7} L ${r * 0.7} ${-r * 0.4}`);
      } else if (d.state === "suspended") {
        ring.classed("ring--suspend", true);
        g.select(".mark-pause").classed("mark-on", true);
      } else if (d.state === "aborted") {
        ring.classed("ring--abort", true);
        g.select(".mark-strike")
          .classed("mark-on", true)
          .attr("x1", -r - 2)
          .attr("y1", 0)
          .attr("x2", r + 2)
          .attr("y2", 0);
        g.select("text.node-label").classed("node-label--abort", true);
      } else if (d.state === "running") {
        ring.classed("ring--running", true);
      } else if (d.state === "blocked") {
        ring.classed("ring--blocked", true);
      } else {
        // "unresolved": clean plain ink ring, no fill color, no badge
      }

      g.select("text.node-label")
        .text(d.name)
        .attr("font-size", `${Math.round(r * 0.65)}px`);
    });

    // Update Resource Nodes
    nodeAll.filter((d) => d.type === "resource").each(function (d) {
      const g = d3.select(this);
      const w = d.boxWidth;
      const h = d.boxHeight;

      // Focus rect
      g.select("rect.node-focus")
        .attr("x", -w / 2 - 4)
        .attr("y", -h / 2 - 4)
        .attr("width", w + 8)
        .attr("height", h + 8)
        .attr("rx", 6);

      // Main box
      g.select("rect.res-box")
        .attr("x", -w / 2)
        .attr("y", -h / 2)
        .attr("width", w)
        .attr("height", h)
        .attr("rx", 4);

      // Outside label above the box (never struck through by edges)
      g.select("text.res-name")
        .attr("x", -w / 2)
        .attr("y", -h / 2 - 8)
        .attr("font-size", "14px")
        .text(d.name);

      g.select("text.res-free")
        .attr("x", -w / 2 + 18)
        .attr("y", -h / 2 - 8)
        .attr("font-size", "12px")
        .text(`${d.freeUnits} of ${d.totalUnits} free`);

      // Instances inside the box (grid up to 4 rows)
      const instG = g.select("g.res-instances");
      instG.selectAll("*").remove();

      const dotSpacing = 14;
      const startX = -((d.cols - 1) * dotSpacing) / 2;
      const startY = -((d.rows - 1) * dotSpacing) / 2;

      for (let k = 0; k < d.totalUnits; k++) {
        const col = k % d.cols;
        const row = Math.floor(k / d.cols);
        const isHeld = k < d.allocatedUnits;

        instG.append("circle")
          .attr("class", `inst ${isHeld ? "inst--held" : "inst--free"}`)
          .attr("cx", startX + col * dotSpacing)
          .attr("cy", startY + row * dotSpacing)
          .attr("r", 4);
      }
    });

    // Node Interaction: Focus, Hover, Dimming, Pinning, Tooltip
    nodeAll
      .on("mouseenter", (event, d) => {
        if (!this.pinnedNodeId) {
          this.hoveredNodeId = d.id;
          this.applyHighlighting();
        }
        this.showTooltip(event, d);
      })
      .on("mousemove", (event) => {
        this.moveTooltip(event);
      })
      .on("mouseleave", () => {
        if (!this.pinnedNodeId) {
          this.hoveredNodeId = null;
          this.applyHighlighting();
        }
        this.hideTooltip();
      })
      .on("click", (event, d) => {
        event.stopPropagation();
        if (this.pinnedNodeId === d.id) {
          this.clearPin();
        } else {
          this.pinnedNodeId = d.id;
          this.hoveredNodeId = d.id;
          this.applyHighlighting();
          this.showTooltip(event, d);
        }
      });

    this.applyEdgeVisibility();
    this.applyHighlighting();
  }

  applyHighlighting() {
    const targetId = this.pinnedNodeId || this.hoveredNodeId;

    if (!targetId) {
      // Clear dimming
      this.edgeGroup.selectAll("path.edge").classed("edge--dim", false);
      this.arrowGroup.selectAll("path.arrow").classed("edge--dim", false);
      this.pillGroup.selectAll("g.pill").classed("edge--dim", false);
      this.nodeGroup.selectAll(".node-focus").classed("node-focus-on", false);
      return;
    }

    // Identify connected links
    const connectedLinks = new Set();
    this.links.forEach((l) => {
      if (l.sourceId === targetId || l.targetId === targetId) {
        connectedLinks.add(l.id);
      }
    });

    // Dim unrelated edges to 8%
    this.edgeGroup.selectAll("path.edge").classed("edge--dim", (d) => !connectedLinks.has(d.id));
    this.arrowGroup.selectAll("path.arrow").classed("edge--dim", (d) => !connectedLinks.has(d.id));
    this.pillGroup.selectAll("g.pill").classed("edge--dim", (d) => !connectedLinks.has(d.id));

    // Focus ring on active node
    this.nodeGroup.selectAll("g.node").each(function (d) {
      const g = d3.select(this);
      g.select(".node-focus").classed("node-focus-on", d.id === targetId);
    });
  }

  clearPin() {
    this.pinnedNodeId = null;
    this.hoveredNodeId = null;
    this.applyHighlighting();
    this.hideTooltip();
  }

  showTooltip(event, d) {
    if (!this.tooltip || !this.tooltip.node()) return;

    let html = "";
    if (d.type === "process") {
      const { available, resource_names } = this.systemData;
      const holds = [];
      const requests = [];

      for (let j = 0; j < d.allocation.length; j++) {
        const rName = resource_names[j] || `R${j}`;
        if (d.allocation[j] > 0) holds.push(`${d.allocation[j]} ${rName}`);
        if (d.request[j] > 0) requests.push(`${d.request[j]} ${rName}`);
      }

      html = `
        <div class="tip-title">${d.name}</div>
        <div>State: <strong>${d.state}</strong></div>
        <div>Holds: ${holds.length > 0 ? holds.join(", ") : "none"}</div>
        <div>Requests: ${requests.length > 0 ? requests.join(", ") : "none"}</div>
      `;
    } else {
      const { process_names } = this.systemData;
      const allocatedTo = [];
      const requestedBy = [];

      for (let i = 0; i < this.systemData.allocation.length; i++) {
        const pName = process_names[i] || `P${i}`;
        if (this.systemData.allocation[i][d.idx] > 0) {
          allocatedTo.push(`${pName} (${this.systemData.allocation[i][d.idx]})`);
        }
        if (this.systemData.request[i][d.idx] > 0) {
          requestedBy.push(`${pName} (${this.systemData.request[i][d.idx]})`);
        }
      }

      html = `
        <div class="tip-title">Resource ${d.name}</div>
        <div>Total units: ${d.totalUnits} (${d.freeUnits} free)</div>
        <div>Allocated to: ${allocatedTo.length > 0 ? allocatedTo.join(", ") : "none"}</div>
        <div>Requested by: ${requestedBy.length > 0 ? requestedBy.join(", ") : "none"}</div>
      `;
    }

    this.tooltip
      .attr("class", "rag-tooltip")
      .style("display", "block")
      .html(html);

    this.moveTooltip(event);
  }

  moveTooltip(event) {
    if (!this.tooltip || !this.tooltip.node()) return;
    const pad = 14;
    this.tooltip
      .style("left", `${event.pageX + pad}px`)
      .style("top", `${event.pageY + pad}px`);
  }

  hideTooltip() {
    if (!this.tooltip || !this.tooltip.node()) return;
    this.tooltip.style("display", "none");
  }

  updateCaptionAndLegend() {
    if (this.captionId) {
      const captionEl = document.getElementById(this.captionId);
      if (captionEl) {
        const scName = this.systemData?.title || "Resource allocation graph";
        const statusStr = this.report ? (this.report.deadlocked ? "deadlocked" : "safe") : "initial";
        captionEl.textContent = `Figure: ${scName} (${statusStr}).`;
      }
    }

    if (this.legendId) {
      const legendEl = document.getElementById(this.legendId);
      if (legendEl && legendEl.children.length === 0) {
        legendEl.innerHTML = `
          <li class="legend-item">
            <svg class="legend-mark" viewBox="-12 -12 24 24"><circle r="8" class="ring"/></svg>
            <span>Unresolved</span>
          </li>
          <li class="legend-item">
            <svg class="legend-mark" viewBox="-12 -12 24 24">
              <circle r="9" class="node-hl node-hl-on"/>
              <circle r="8" class="ring"/>
            </svg>
            <span>Evaluating</span>
          </li>
          <li class="legend-item">
            <svg class="legend-mark" viewBox="-12 -12 24 24">
              <circle r="8" class="ring ring--ok"/>
              <path d="M -3 0 L 0 3 L 5 -3" class="mark-check" style="display:inline;"/>
            </svg>
            <span>Finished</span>
          </li>
          <li class="legend-item">
            <svg class="legend-mark" viewBox="-12 -12 24 24">
              <circle r="8" class="ring ring--dead"/>
              <line x1="-5" y1="4" x2="4" y2="-5" class="mark-hatch" style="display:inline;"/>
            </svg>
            <span>Deadlocked</span>
          </li>
          <li class="legend-item">
            <svg class="legend-mark" viewBox="-12 -12 24 24">
              <circle r="8" class="ring ring--suspend"/>
              <line x1="-3" y1="-4" x2="-3" y2="4" class="mark-pause" style="display:inline;"/>
              <line x1="3" y1="-4" x2="3" y2="4" class="mark-pause" style="display:inline;"/>
            </svg>
            <span>Suspended</span>
          </li>
          <li class="legend-item">
            <svg class="legend-mark" viewBox="-12 -12 24 24">
              <circle r="8" class="ring ring--abort"/>
              <line x1="-9" y1="0" x2="9" y2="0" class="mark-strike" style="display:inline;"/>
            </svg>
            <span>Aborted</span>
          </li>
        `;
      }
    }
  }

  animateProcessRelease(procIdx, allocatedUnits) {
    // Pulse highlighter band behind the node
    const procId = `P${procIdx}`;
    this.nodeGroup.selectAll("g.node")
      .filter((d) => d.id === procId)
      .select("path.node-hl")
      .transition()
      .duration(160)
      .attr("transform", "scale(1.15)")
      .transition()
      .duration(200)
      .attr("transform", "scale(1.0)");
  }
}

/**
 * Utility: evaluate position on cubic Bezier at parameter t in [0, 1].
 */
function evaluateCubicBezier(x0, y0, x1, y1, x2, y2, x3, y3, t) {
  const mt = 1 - t;
  const mt2 = mt * mt;
  const mt3 = mt2 * mt;
  const t2 = t * t;
  const t3 = t2 * t;

  return {
    x: mt3 * x0 + 3 * mt2 * t * x1 + 3 * mt * t2 * x2 + t3 * x3,
    y: mt3 * y0 + 3 * mt2 * t * y1 + 3 * mt * t2 * y2 + t3 * x3 ? mt3 * y0 + 3 * mt2 * t * y1 + 3 * mt * t2 * y2 + t3 * y3 : 0,
  };
}
