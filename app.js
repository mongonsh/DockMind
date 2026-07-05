const truckPresets = {
  smallVan: {
    id: "smallVan",
    name: "Small van",
    length: 320,
    width: 170,
    height: 160,
    maxWeight: 900,
    refrigerated: false
  },
  fourTon: {
    id: "fourTon",
    name: "4-ton truck",
    length: 620,
    width: 220,
    height: 230,
    maxWeight: 4000,
    refrigerated: false
  },
  reefer: {
    id: "reefer",
    name: "Refrigerated truck",
    length: 560,
    width: 210,
    height: 220,
    maxWeight: 3200,
    refrigerated: true
  }
};

const route = ["Osaka", "Kyoto", "Nagoya"];
const colors = ["#245fbb", "#14724e", "#b96818", "#127581", "#6658a8", "#b43b32", "#344054"];
const roles = [
  { id: "loader", label: "Loader" },
  { id: "driver", label: "Driver" },
  { id: "ops", label: "Ops" },
  { id: "customer", label: "Customer" },
  { id: "agent", label: "Agent" }
];

let cargo = [
  { id: "FRZ-01", label: "Frozen food", length: 90, width: 60, height: 55, weight: 42, stop: "Kyoto", tags: ["cold"] },
  { id: "FRG-02", label: "Fragile electronics", length: 70, width: 50, height: 45, weight: 18, stop: "Nagoya", tags: ["fragile"] },
  { id: "MCH-03", label: "Machine parts", length: 110, width: 70, height: 65, weight: 95, stop: "Nagoya", tags: ["heavy"] },
  { id: "DRY-04", label: "Dry goods", length: 85, width: 50, height: 50, weight: 26, stop: "Kyoto", tags: [] },
  { id: "MED-05", label: "Medical samples", length: 60, width: 45, height: 42, weight: 12, stop: "Nagoya", tags: ["cold", "fragile"] },
  { id: "RET-06", label: "Retail cartons", length: 75, width: 55, height: 48, weight: 31, stop: "Kyoto", tags: [] }
];

let activeTruckId = "fourTon";
let activeRole = "loader";
let activeSkill = "loader";
let currentPlan = null;
let lastDetections = [];
let drawingMode = false;
let draftDetection = null;
let detectionCounter = 0;
const sampleImageSrc = "assets/sample-warehouse.svg";

const el = {
  statusCargo: document.getElementById("status-cargo"),
  statusFit: document.getElementById("status-fit"),
  statusRisk: document.getElementById("status-risk"),
  detectionCount: document.getElementById("detection-count"),
  canvasWeight: document.getElementById("canvas-weight"),
  imageInput: document.getElementById("image-input"),
  warehouseImage: document.getElementById("warehouse-image"),
  detectionOverlay: document.getElementById("detection-overlay"),
  sampleDetectBtn: document.getElementById("sample-detect-btn"),
  autoDetectBtn: document.getElementById("auto-detect-btn"),
  drawBoxBtn: document.getElementById("draw-box-btn"),
  useBoxesBtn: document.getElementById("use-boxes-btn"),
  clearDetectBtn: document.getElementById("clear-detect-btn"),
  promptInput: document.getElementById("prompt-input"),
  promptBtn: document.getElementById("prompt-btn"),
  truckSelect: document.getElementById("truck-select"),
  manifestList: document.getElementById("manifest-list"),
  addCargoBtn: document.getElementById("add-cargo-btn"),
  optimizeBtn: document.getElementById("optimize-btn"),
  exportJsonBtn: document.getElementById("export-json-btn"),
  exportBlenderBtn: document.getElementById("export-blender-btn"),
  truckTitle: document.getElementById("truck-title"),
  truckLayout: document.getElementById("truck-layout"),
  riskList: document.getElementById("risk-list"),
  roleTabs: document.getElementById("role-tabs"),
  roleContent: document.getElementById("role-content"),
  skillSelect: document.getElementById("skill-select"),
  skillOutput: document.getElementById("skill-output"),
  copySkillBtn: document.getElementById("copy-skill-btn"),
  blenderPreview: document.getElementById("blender-preview"),
  blenderNote: document.getElementById("blender-note")
};

function routeRank(stop) {
  const index = route.indexOf(stop);
  return index === -1 ? 0 : index;
}

function sortedCargoForLoading(items) {
  return [...items].sort((a, b) => {
    const stopDelta = routeRank(b.stop) - routeRank(a.stop);
    if (stopDelta !== 0) return stopDelta;
    const heavyDelta = Number(b.tags.includes("heavy")) - Number(a.tags.includes("heavy"));
    if (heavyDelta !== 0) return heavyDelta;
    return b.weight - a.weight;
  });
}

function createPlan() {
  const truck = truckPresets[activeTruckId];
  const items = sortedCargoForLoading(cargo);
  const placements = [];
  const warnings = [];
  let cursorX = 12;
  let cursorY = 12;
  let shelfDepth = 0;
  let layer = 0;

  for (const item of items) {
    const itemLength = Math.max(36, item.length);
    const itemWidth = Math.max(32, item.width);
    const itemHeight = Math.max(24, item.height);

    if (cursorY + itemWidth > truck.width - 12) {
      cursorY = 12;
      cursorX += shelfDepth + 10;
      shelfDepth = 0;
    }

    let fits = true;
    if (cursorX + itemLength > truck.length - 12) fits = false;
    if (itemWidth > truck.width || itemHeight > truck.height) fits = false;
    if (item.tags.includes("cold") && !truck.refrigerated) {
      fits = false;
      warnings.push({
        level: "bad",
        title: "Cold-chain mismatch",
        body: `${item.id} requires refrigeration.`
      });
    }
    if (item.tags.includes("fragile") && layer === 0 && item.weight > 25) {
      warnings.push({
        level: "warn",
        title: "Fragile handling",
        body: `${item.id} should stay above heavy cargo.`
      });
    }

    placements.push({
      ...item,
      x: cursorX,
      y: cursorY,
      z: layer * 12,
      placedLength: itemLength,
      placedWidth: itemWidth,
      placedHeight: itemHeight,
      fits
    });

    cursorY += itemWidth + 8;
    shelfDepth = Math.max(shelfDepth, itemLength);
    if (item.tags.includes("heavy")) layer = 0;
  }

  const totalWeight = cargo.reduce((sum, item) => sum + item.weight, 0);
  const footprint = placements.reduce((sum, item) => item.fits ? sum + (item.placedLength * item.placedWidth) : sum, 0);
  const fill = Math.min(100, Math.round((footprint / (truck.length * truck.width)) * 100));
  const unfit = placements.filter(item => !item.fits);

  if (totalWeight > truck.maxWeight) {
    warnings.push({
      level: "bad",
      title: "Weight limit",
      body: `${totalWeight}kg exceeds ${truck.maxWeight}kg.`
    });
  }

  if (unfit.length > 0) {
    warnings.push({
      level: "bad",
      title: "Overflow",
      body: `${unfit.length} item${unfit.length === 1 ? "" : "s"} need a larger or refrigerated truck.`
    });
  }

  warnings.push({
    level: "ok",
    title: "Unload order",
    body: "Nagoya cargo loaded first, Kyoto cargo nearer the rear door."
  });

  return {
    name: "DockMind sample load plan",
    generatedAt: new Date().toISOString(),
    route,
    truck,
    cargo,
    placements,
    metrics: {
      totalWeight,
      fill,
      fitCount: placements.filter(item => item.fits).length,
      riskCount: warnings.filter(item => item.level !== "ok").length
    },
    warnings
  };
}

function renderManifest() {
  el.manifestList.innerHTML = "";
  for (const item of cargo) {
    const row = document.createElement("div");
    row.className = "manifest-item";
    row.innerHTML = `
      <div>
        <strong>${item.id} · ${item.label}</strong>
        <small>${item.length}x${item.width}x${item.height}cm · ${item.weight}kg · ${item.stop}</small>
      </div>
      <div class="tag-stack">${renderTags(item.tags)}</div>
    `;
    el.manifestList.appendChild(row);
  }
}

function renderTags(tags) {
  if (!tags.length) return `<span class="tag">standard</span>`;
  return tags.map(tag => `<span class="tag ${tag}">${tag}</span>`).join("");
}

function renderLayout(plan) {
  const { truck } = plan;
  el.truckLayout.innerHTML = "";
  el.truckTitle.textContent = `${truck.name} · ${truck.length}x${truck.width}x${truck.height}cm`;

  for (const [index, item] of plan.placements.entries()) {
    const box = document.createElement("div");
    box.className = `cargo-box${item.fits ? "" : " unfit"}`;
    box.style.left = `${(item.x / truck.length) * 100}%`;
    box.style.top = `${(item.y / truck.width) * 100}%`;
    box.style.width = `${Math.max(7, (item.placedLength / truck.length) * 100)}%`;
    box.style.height = `${Math.max(12, (item.placedWidth / truck.width) * 100)}%`;
    box.style.setProperty("--cargo-color", item.fits ? colors[index % colors.length] : "#b43b32");
    box.title = `${item.id}: ${item.label}`;

    const id = document.createElement("strong");
    id.textContent = item.id;
    const stop = document.createElement("span");
    stop.textContent = item.stop;
    const size = document.createElement("em");
    size.textContent = `${item.length}x${item.width}cm`;
    box.append(id, stop, size);

    el.truckLayout.appendChild(box);
  }
}

function renderRisks(plan) {
  el.riskList.innerHTML = "";
  for (const risk of plan.warnings.slice(0, 6)) {
    const node = document.createElement("div");
    node.className = `risk ${risk.level === "bad" ? "bad" : risk.level === "warn" ? "warn" : ""}`;
    const title = document.createElement("strong");
    title.textContent = risk.title;
    const body = document.createElement("span");
    body.textContent = risk.body;
    node.append(title, body);
    el.riskList.appendChild(node);
  }
}

function renderStatus(plan) {
  el.statusCargo.innerHTML = `<small>Cargo</small><strong>${plan.cargo.length}</strong>`;
  el.statusFit.innerHTML = `<small>Fill</small><strong>${plan.metrics.fill}%</strong>`;
  el.statusRisk.innerHTML = `<small>Risks</small><strong>${plan.metrics.riskCount}</strong>`;
  el.canvasWeight.textContent = `${plan.metrics.totalWeight}kg of ${plan.truck.maxWeight}kg`;
}

function renderRoleTabs() {
  el.roleTabs.innerHTML = "";
  for (const role of roles) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `role-tab${activeRole === role.id ? " active" : ""}`;
    button.textContent = role.label;
    button.addEventListener("click", () => {
      activeRole = role.id;
      activeSkill = role.id;
      el.skillSelect.value = role.id;
      renderAll();
    });
    el.roleTabs.appendChild(button);
  }
}

function renderRoleContent(plan) {
  const byStop = Object.groupBy ? Object.groupBy(plan.placements, item => item.stop) : groupBy(plan.placements, item => item.stop);
  const loaderSteps = plan.placements.map((item, index) => `<li>${index + 1}. Load ${item.id} at bay ${Math.round(item.x)}cm / ${Math.round(item.y)}cm. ${item.fits ? "Clear." : "Needs exception."}</li>`).join("");
  const driverStops = route.slice(1).map(stop => {
    const stopItems = byStop[stop] || [];
    return `<li>${stop}: unload ${stopItems.map(item => item.id).join(", ") || "none"}</li>`;
  }).join("");

  const views = {
    loader: `
      <h3>Warehouse Worker View</h3>
      <ol>${loaderSteps}</ol>
    `,
    driver: `
      <h3>Driver View</h3>
      <ul>${driverStops}</ul>
      <p class="muted-line">Rear-door cargo is shown nearest the right edge of the plan.</p>
    `,
    ops: `
      <h3>Ops Manager View</h3>
      <ul>
        <li>Truck utilization: ${plan.metrics.fill}% footprint fill.</li>
        <li>Total cargo weight: ${plan.metrics.totalWeight}kg of ${plan.truck.maxWeight}kg.</li>
        <li>Open exceptions: ${plan.metrics.riskCount}.</li>
        <li>Route: ${route.join(" -> ")}.</li>
      </ul>
    `,
    customer: `
      <h3>Customer View</h3>
      <ul>
        <li>Kyoto delivery: ${countByStop("Kyoto")} packages staged near rear door.</li>
        <li>Nagoya delivery: ${countByStop("Nagoya")} packages locked in first-load zone.</li>
        <li>Exception notices are hidden unless they affect ETA.</li>
      </ul>
    `,
    agent: `
      <h3>AI Agent View</h3>
      <ul>
        <li>Plan JSON includes cargo, truck, route, placements, metrics, and warnings.</li>
        <li>Generated skills are role-specific and executable by an agent.</li>
        <li>Blender script reads the same plan shape for 3D output.</li>
      </ul>
    `
  };

  el.roleContent.innerHTML = views[activeRole];
}

function groupBy(items, getKey) {
  return items.reduce((acc, item) => {
    const key = getKey(item);
    acc[key] = acc[key] || [];
    acc[key].push(item);
    return acc;
  }, {});
}

function countByStop(stop) {
  return cargo.filter(item => item.stop === stop).length;
}

function skillMarkdown(kind, plan) {
  const placements = plan.placements.map(item => `${item.id}: ${item.label}, ${item.stop}, x=${item.x}, y=${item.y}, fits=${item.fits}`).join("\n");
  const warnings = plan.warnings.map(item => `- ${item.title}: ${item.body}`).join("\n");

  const skillBodies = {
    loader: `---
name: dockmind-loader-agent
description: Execute warehouse loading steps from a DockMind plan.
---

# DockMind Loader Agent Skill

## Goal
Load cargo into ${plan.truck.name} in the sequence that protects fragile goods, keeps cold-chain cargo valid, and preserves unload order.

## Inputs
- DockMind cargo plan JSON
- Warehouse bay photo detections
- Truck preset: ${plan.truck.name}

## Steps
${plan.placements.map((item, index) => `${index + 1}. Move ${item.id} (${item.label}) to x=${item.x}cm, y=${item.y}cm. Stop: ${item.stop}.`).join("\n")}

## Safety Checks
${warnings}
`,
    driver: `---
name: dockmind-driver-agent
description: Execute unload sequence and delivery checks from a DockMind plan.
---

# DockMind Driver Agent Skill

## Route
${route.join(" -> ")}

## Unload Sequence
${route.slice(1).map(stop => `- ${stop}: ${plan.placements.filter(item => item.stop === stop).map(item => item.id).join(", ")}`).join("\n")}

## Warnings
${warnings}
`,
    ops: `---
name: dockmind-ops-exception-agent
description: Resolve cargo exceptions during truck loading.
---

# DockMind Ops Exception Skill

## Metrics
- Footprint fill: ${plan.metrics.fill}%
- Total weight: ${plan.metrics.totalWeight}kg
- Risk count: ${plan.metrics.riskCount}

## Exception Policy
1. Cold-chain mismatch blocks departure unless a refrigerated truck is selected.
2. Overflow triggers truck upgrade before manual override.
3. Fragile and heavy conflicts require supervisor confirmation.

## Current Exceptions
${warnings}
`,
    customer: `---
name: dockmind-customer-status-agent
description: Convert a logistics loading plan into customer-safe status.
---

# DockMind Customer Status Skill

## Public Status
- Kyoto cargo count: ${countByStop("Kyoto")}
- Nagoya cargo count: ${countByStop("Nagoya")}
- Route state: planned

## Hide Internals
Do not expose weight-limit, packing, or warehouse exception details unless ETA changes.
`,
    agent: JSON.stringify(publicPlan(plan), null, 2)
  };

  return skillBodies[kind];
}

function publicPlan(plan) {
  return {
    app: "DockMind",
    type: "dockmind.load_plan.v1",
    generatedAt: plan.generatedAt,
    truck: plan.truck,
    route: plan.route,
    detections: lastDetections.filter(detection => !detection.draft),
    cargo: plan.cargo,
    placements: plan.placements,
    metrics: plan.metrics,
    warnings: plan.warnings
  };
}

function renderSkill(plan) {
  el.skillOutput.textContent = skillMarkdown(activeSkill, plan);
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function nextDetectionUid() {
  detectionCounter += 1;
  return `det-${detectionCounter}`;
}

function normalizeDetection(detection, index) {
  const x = Number(detection.x) || 0;
  const y = Number(detection.y) || 0;
  const w = Number(detection.w) || 0;
  const h = Number(detection.h) || 0;
  const left = clamp(Math.min(x, x + w), 0, 98);
  const top = clamp(Math.min(y, y + h), 0, 98);
  return {
    uid: detection.uid || nextDetectionUid(),
    id: detection.id || `BOX-${String(index + 1).padStart(2, "0")}`,
    label: detection.label || "",
    x: left,
    y: top,
    w: clamp(Math.abs(w), 2, Math.max(2, 100 - left)),
    h: clamp(Math.abs(h), 2, Math.max(2, 100 - top)),
    confidence: detection.confidence ?? 0.82,
    source: detection.source || "auto",
    draft: Boolean(detection.draft)
  };
}

function imageContentBounds() {
  const rect = el.detectionOverlay.getBoundingClientRect();
  const naturalWidth = el.warehouseImage.naturalWidth || rect.width || 1;
  const naturalHeight = el.warehouseImage.naturalHeight || rect.height || 1;
  const stageAspect = rect.width / Math.max(rect.height, 1);
  const imageAspect = naturalWidth / Math.max(naturalHeight, 1);

  if (stageAspect > imageAspect) {
    const width = (imageAspect / stageAspect) * 100;
    return { x: (100 - width) / 2, y: 0, w: width, h: 100 };
  }

  const height = (stageAspect / imageAspect) * 100;
  return { x: 0, y: (100 - height) / 2, w: 100, h: height };
}

function imageToOverlayDetection(detection) {
  const bounds = imageContentBounds();
  return {
    left: bounds.x + (detection.x * bounds.w / 100),
    top: bounds.y + (detection.y * bounds.h / 100),
    width: detection.w * bounds.w / 100,
    height: detection.h * bounds.h / 100
  };
}

function renderDetections(detections, options = {}) {
  lastDetections = detections
    .map(normalizeDetection)
    .filter(detection => detection.w >= 2 && detection.h >= 2);
  const stableDetections = lastDetections.filter(detection => !detection.draft).length;
  el.detectionCount.textContent = `${stableDetections} mark${stableDetections === 1 ? "" : "s"}`;
  el.detectionOverlay.innerHTML = "";
  for (const detection of lastDetections) {
    const display = imageToOverlayDetection(detection);
    const node = document.createElement("div");
    node.className = `detect-box ${detection.source === "manual" ? "manual" : ""} ${detection.source === "yolo" ? "yolo" : ""} ${detection.draft ? "draft" : ""}`;
    node.dataset.uid = detection.uid;
    node.style.left = `${display.left}%`;
    node.style.top = `${display.top}%`;
    node.style.width = `${display.width}%`;
    node.style.height = `${display.height}%`;

    const label = document.createElement("span");
    label.textContent = `${detection.id} ${Math.round(detection.confidence * 100)}%`;
    node.appendChild(label);

    if (!detection.draft) {
      const remove = document.createElement("button");
      remove.className = "detect-remove";
      remove.type = "button";
      remove.textContent = "x";
      remove.setAttribute("aria-label", `remove ${detection.id}`);
      remove.addEventListener("click", event => {
        event.stopPropagation();
        renderDetections(lastDetections.filter(item => item.uid !== detection.uid), { syncCargo: true });
      });
      node.appendChild(remove);
    }

    el.detectionOverlay.appendChild(node);
  }

  if (options.syncCargo) {
    syncCargoFromDetections();
  }
}

async function loadSampleDetection() {
  setDrawingMode(false);
  el.warehouseImage.src = sampleImageSrc;
  const response = await fetch("data/sample-detection.json");
  const data = await response.json();
  renderDetections(data.detections);
}

function syncCargoFromDetections() {
  const usable = lastDetections
    .filter(detection => !detection.draft)
    .sort((a, b) => (a.y - b.y) || (a.x - b.x))
    .slice(0, 10);

  if (usable.length === 0) return;

  const prompt = el.promptInput.value.toLowerCase();
  const wantsCold = prompt.includes("cold") || prompt.includes("frozen") || prompt.includes("medical");
  const wantsFragile = prompt.includes("fragile") || prompt.includes("glass") || prompt.includes("electronics");
  const wantsHeavy = prompt.includes("heavy") || prompt.includes("machine") || prompt.includes("parts");

  cargo = usable.map((detection, index) => {
    const tags = [];
    if (wantsCold && index % 4 === 0) tags.push("cold");
    if (wantsFragile && index % 3 === 1) tags.push("fragile");
    if (wantsHeavy && index === 0) tags.push("heavy");

    return {
      id: detection.id,
      label: detection.source === "manual" ? "Marked cargo box" : detection.source === "yolo" ? "YOLO cargo box" : "Detected carton",
      length: Math.round(clamp(42 + detection.w * 1.7, 45, 125)),
      width: Math.round(clamp(30 + detection.h * 1.4, 35, 85)),
      height: Math.round(clamp(28 + Math.sqrt(detection.w * detection.h) * 1.1, 32, 80)),
      weight: Math.round(clamp(10 + detection.w * detection.h / 22, 10, 110)),
      stop: index % 2 === 0 ? "Nagoya" : "Kyoto",
      tags
    };
  });

  renderAll();
}

function setDrawingMode(enabled) {
  drawingMode = enabled;
  draftDetection = null;
  el.drawBoxBtn.classList.toggle("active", enabled);
  el.drawBoxBtn.textContent = enabled ? "Drawing" : "Draw";
}

function overlayPoint(event) {
  const rect = el.detectionOverlay.getBoundingClientRect();
  const bounds = imageContentBounds();
  const overlayX = ((event.clientX - rect.left) / rect.width) * 100;
  const overlayY = ((event.clientY - rect.top) / rect.height) * 100;
  return {
    x: clamp(((overlayX - bounds.x) / bounds.w) * 100, 0, 100),
    y: clamp(((overlayY - bounds.y) / bounds.h) * 100, 0, 100)
  };
}

function manualDetectionId() {
  return `BOX-${String(lastDetections.filter(item => !item.draft).length + 1).padStart(2, "0")}`;
}

async function waitForWarehouseImage() {
  if (!el.warehouseImage.complete) {
    await new Promise(resolve => {
      el.warehouseImage.addEventListener("load", resolve, { once: true });
      el.warehouseImage.addEventListener("error", resolve, { once: true });
    });
  }
  if (el.warehouseImage.decode) {
    try {
      await el.warehouseImage.decode();
    } catch {
      // The image can still be drawable after decode rejects for SVG/data URLs.
    }
  }
}

function drawImageForFallback(ctx, image, width, height) {
  ctx.drawImage(image, 0, 0, width, height);
}

function isCardboardPixel(r, g, b, a) {
  if (a < 120) return false;
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  const saturation = max === 0 ? 0 : (max - min) / max;
  const warmEnough = r > 95 && g > 65 && b < 190 && r >= g * 0.82 && g >= b * 0.78;
  const brownEnough = r > b * 1.08 && g > b * 0.92 && saturation > 0.12;
  const notSkinOrWoodDark = max > 95 && min > 35;
  return warmEnough && brownEnough && notSkinOrWoodDark;
}

function componentBoxesFromMask(mask, width, height) {
  const visited = new Uint8Array(mask.length);
  const components = [];
  const stack = [];

  for (let start = 0; start < mask.length; start += 1) {
    if (!mask[start] || visited[start]) continue;
    let minX = width;
    let minY = height;
    let maxX = 0;
    let maxY = 0;
    let count = 0;
    stack.length = 0;
    stack.push(start);
    visited[start] = 1;

    while (stack.length) {
      const index = stack.pop();
      const x = index % width;
      const y = Math.floor(index / width);
      count += 1;
      minX = Math.min(minX, x);
      minY = Math.min(minY, y);
      maxX = Math.max(maxX, x);
      maxY = Math.max(maxY, y);

      const neighbors = [index - 1, index + 1, index - width, index + width];
      for (const next of neighbors) {
        if (next < 0 || next >= mask.length || visited[next] || !mask[next]) continue;
        const nx = next % width;
        if (Math.abs(nx - x) > 1) continue;
        visited[next] = 1;
        stack.push(next);
      }
    }

    const boxWidth = maxX - minX + 1;
    const boxHeight = maxY - minY + 1;
    const area = boxWidth * boxHeight;
    const density = count / Math.max(area, 1);
    if (count < width * height * 0.004 || boxWidth < width * 0.055 || boxHeight < height * 0.055 || density < 0.18) {
      continue;
    }

    components.push({ minX, minY, maxX, maxY, width: boxWidth, height: boxHeight, count, area });
  }

  return components.sort((a, b) => b.count - a.count);
}

function splitComponent(component, canvasWidth, canvasHeight) {
  const large = component.width > canvasWidth * 0.36 || component.height > canvasHeight * 0.34 || component.count > canvasWidth * canvasHeight * 0.18;
  if (!large) return [component];

  const cols = clamp(Math.round(component.width / (canvasWidth * 0.21)), 1, 3);
  const rows = clamp(Math.round(component.height / (canvasHeight * 0.2)), 1, 3);
  const boxes = [];
  const gutterX = Math.max(3, component.width * 0.025);
  const gutterY = Math.max(3, component.height * 0.025);
  const cellWidth = component.width / cols;
  const cellHeight = component.height / rows;

  for (let row = 0; row < rows; row += 1) {
    for (let col = 0; col < cols; col += 1) {
      const minX = component.minX + col * cellWidth + gutterX;
      const minY = component.minY + row * cellHeight + gutterY;
      const maxX = component.minX + (col + 1) * cellWidth - gutterX;
      const maxY = component.minY + (row + 1) * cellHeight - gutterY;
      if (maxX - minX > canvasWidth * 0.05 && maxY - minY > canvasHeight * 0.05) {
        boxes.push({ minX, minY, maxX, maxY, width: maxX - minX, height: maxY - minY, count: component.count / (rows * cols) });
      }
    }
  }

  return boxes;
}

async function autoDetectCurrentImage(options = {}) {
  setDrawingMode(false);
  await waitForWarehouseImage();

  const naturalWidth = el.warehouseImage.naturalWidth || 640;
  const naturalHeight = el.warehouseImage.naturalHeight || 400;
  const canvas = document.createElement("canvas");
  canvas.width = 640;
  canvas.height = Math.max(240, Math.round(canvas.width * (naturalHeight / naturalWidth)));
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  drawImageForFallback(ctx, el.warehouseImage, canvas.width, canvas.height);

  const image = ctx.getImageData(0, 0, canvas.width, canvas.height);
  const mask = new Uint8Array(canvas.width * canvas.height);
  for (let i = 0, pixel = 0; i < image.data.length; i += 4, pixel += 1) {
    if (isCardboardPixel(image.data[i], image.data[i + 1], image.data[i + 2], image.data[i + 3])) {
      mask[pixel] = 1;
    }
  }

  const boxes = componentBoxesFromMask(mask, canvas.width, canvas.height)
    .flatMap(component => splitComponent(component, canvas.width, canvas.height))
    .sort((a, b) => (a.minY - b.minY) || (a.minX - b.minX))
    .slice(0, 8)
    .map((box, index) => ({
      id: `BOX-${String(index + 1).padStart(2, "0")}`,
      x: (box.minX / canvas.width) * 100,
      y: (box.minY / canvas.height) * 100,
      w: ((box.maxX - box.minX) / canvas.width) * 100,
      h: ((box.maxY - box.minY) / canvas.height) * 100,
      confidence: clamp(0.68 + (box.count / (canvas.width * canvas.height)) * 6, 0.68, 0.91),
      source: "auto"
    }));

  renderDetections(boxes, { syncCargo: options.syncCargo && boxes.length > 0 });
  el.autoDetectBtn.textContent = boxes.length ? `Fallback ${boxes.length}` : "Fallback 0";
  setTimeout(() => { el.autoDetectBtn.textContent = "YOLO"; }, 1400);
}

async function yoloDetectCurrentImage(options = {}) {
  setDrawingMode(false);
  await waitForWarehouseImage();

  if (!el.warehouseImage.src.startsWith("data:image/")) {
    await autoDetectCurrentImage(options);
    return;
  }

  const previousLabel = el.autoDetectBtn.textContent;
  el.autoDetectBtn.disabled = true;
  el.autoDetectBtn.textContent = "YOLO...";

  try {
    const response = await fetch("/api/detect", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        imageData: el.warehouseImage.src,
        prompts: ["cardboard box", "cargo box", "package", "carton", "crate", "pallet"],
        confidence: 0.06
      })
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "YOLO API failed");
    }

    renderDetections(data.detections || [], { syncCargo: options.syncCargo && data.detections && data.detections.length > 0 });
    el.autoDetectBtn.textContent = `YOLO ${(data.detections || []).length}`;
  } catch (error) {
    console.warn("YOLO unavailable, using fallback detector", error);
    await autoDetectCurrentImage(options);
  } finally {
    el.autoDetectBtn.disabled = false;
    setTimeout(() => { el.autoDetectBtn.textContent = previousLabel === "YOLO..." ? "YOLO" : "YOLO"; }, 1400);
  }
}

function runPromptScenario() {
  const prompt = el.promptInput.value.toLowerCase();
  const needsCold = prompt.includes("frozen") || prompt.includes("cold") || prompt.includes("medical");
  const hasFragile = prompt.includes("fragile") || prompt.includes("electronics");
  const hasHeavy = prompt.includes("machine") || prompt.includes("heavy");

  cargo = [
    { id: "FRZ-01", label: needsCold ? "Frozen food" : "Food cartons", length: 90, width: 60, height: 55, weight: 42, stop: "Kyoto", tags: needsCold ? ["cold"] : [] },
    { id: "FRG-02", label: hasFragile ? "Fragile electronics" : "Consumer electronics", length: 70, width: 50, height: 45, weight: 18, stop: "Nagoya", tags: hasFragile ? ["fragile"] : [] },
    { id: "MCH-03", label: hasHeavy ? "Machine parts" : "Parts bin", length: 110, width: 70, height: 65, weight: hasHeavy ? 95 : 45, stop: "Nagoya", tags: hasHeavy ? ["heavy"] : [] },
    { id: "DRY-04", label: "Dry goods", length: 85, width: 50, height: 50, weight: 26, stop: "Kyoto", tags: [] },
    { id: "MED-05", label: "Medical samples", length: 60, width: 45, height: 42, weight: 12, stop: "Nagoya", tags: ["cold", "fragile"] }
  ];
  renderAll();
}

function addCargo() {
  const next = cargo.length + 1;
  const stop = next % 2 === 0 ? "Kyoto" : "Nagoya";
  cargo.push({
    id: `BOX-${String(next).padStart(2, "0")}`,
    label: "Tagged carton",
    length: 70,
    width: 45,
    height: 42,
    weight: 22,
    stop,
    tags: next % 3 === 0 ? ["fragile"] : []
  });
  renderAll();
}

function downloadText(filename, text, type = "application/json") {
  const blob = new Blob([text], { type });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

function blenderScriptForPlan(plan) {
  return `# DockMind Blender entrypoint
# Run:
# /Applications/Blender.app/Contents/MacOS/Blender --background --python scripts/generate_blender_plan.py -- data/sample-plan.json assets/blender-preview.png assets/dockmind-load-plan.glb

PLAN = ${JSON.stringify(publicPlan(plan), null, 2)}
`;
}

function renderAll() {
  currentPlan = createPlan();
  renderManifest();
  renderLayout(currentPlan);
  renderRisks(currentPlan);
  renderStatus(currentPlan);
  renderRoleTabs();
  renderRoleContent(currentPlan);
  renderSkill(currentPlan);
}

el.imageInput.addEventListener("change", event => {
  const file = event.target.files && event.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => {
    setDrawingMode(false);
    el.warehouseImage.addEventListener("load", () => {
      yoloDetectCurrentImage({ syncCargo: true });
    }, { once: true });
    el.warehouseImage.src = reader.result;
  };
  reader.readAsDataURL(file);
});

el.sampleDetectBtn.addEventListener("click", loadSampleDetection);
el.autoDetectBtn.addEventListener("click", () => yoloDetectCurrentImage({ syncCargo: true }));
el.drawBoxBtn.addEventListener("click", () => setDrawingMode(!drawingMode));
el.useBoxesBtn.addEventListener("click", () => {
  syncCargoFromDetections();
  el.useBoxesBtn.textContent = "Used";
  setTimeout(() => { el.useBoxesBtn.textContent = "Use"; }, 1000);
});
el.clearDetectBtn.addEventListener("click", () => {
  setDrawingMode(false);
  renderDetections([]);
});
el.promptBtn.addEventListener("click", runPromptScenario);
el.truckSelect.addEventListener("change", event => {
  activeTruckId = event.target.value;
  renderAll();
});
el.optimizeBtn.addEventListener("click", renderAll);
el.addCargoBtn.addEventListener("click", addCargo);
el.skillSelect.addEventListener("change", event => {
  activeSkill = event.target.value;
  activeRole = roles.some(role => role.id === activeSkill) ? activeSkill : activeRole;
  renderAll();
});
el.copySkillBtn.addEventListener("click", async () => {
  await navigator.clipboard.writeText(el.skillOutput.textContent);
  el.copySkillBtn.textContent = "Copied";
  setTimeout(() => { el.copySkillBtn.textContent = "Copy"; }, 1000);
});
el.exportJsonBtn.addEventListener("click", () => {
  downloadText("dockmind-plan.json", JSON.stringify(publicPlan(currentPlan), null, 2));
});
el.exportBlenderBtn.addEventListener("click", () => {
  downloadText("dockmind-blender-entry.py", blenderScriptForPlan(currentPlan), "text/x-python");
});
el.blenderPreview.addEventListener("error", () => {
  el.blenderPreview.src = "assets/blender-preview.svg";
  el.blenderNote.textContent = "Fallback preview active. Run npm run render:blender to create a PNG.";
});

el.detectionOverlay.addEventListener("pointerdown", event => {
  if (!drawingMode || event.target.closest(".detect-remove")) return;
  event.preventDefault();
  const start = overlayPoint(event);
  draftDetection = {
    uid: nextDetectionUid(),
    id: manualDetectionId(),
    startX: start.x,
    startY: start.y,
    x: start.x,
    y: start.y,
    w: 0,
    h: 0,
    confidence: 1,
    source: "manual",
    draft: true
  };
  el.detectionOverlay.setPointerCapture(event.pointerId);
  renderDetections([...lastDetections.filter(item => !item.draft), draftDetection]);
});

el.detectionOverlay.addEventListener("pointermove", event => {
  if (!drawingMode || !draftDetection) return;
  event.preventDefault();
  const point = overlayPoint(event);
  draftDetection = {
    ...draftDetection,
    x: Math.min(draftDetection.startX, point.x),
    y: Math.min(draftDetection.startY, point.y),
    w: Math.abs(point.x - draftDetection.startX),
    h: Math.abs(point.y - draftDetection.startY)
  };
  renderDetections([...lastDetections.filter(item => !item.draft), draftDetection]);
});

el.detectionOverlay.addEventListener("pointerup", event => {
  if (!drawingMode || !draftDetection) return;
  event.preventDefault();
  const finalDetection = { ...draftDetection, draft: false };
  const nextDetections = lastDetections
    .filter(item => !item.draft)
    .concat(finalDetection)
    .filter(item => item.w >= 3 && item.h >= 3);
  draftDetection = null;
  setDrawingMode(false);
  renderDetections(nextDetections, { syncCargo: true });
});

loadSampleDetection();
renderAll();
