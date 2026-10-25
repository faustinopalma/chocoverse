const NS = "http://www.w3.org/2000/svg";
const COLORS = [
  { color: "var(--cp-accent)", name: "Accent" },
  { color: "var(--cp-link)", name: "Blue" },
  { color: "var(--cp-success)", name: "Green" },
  { color: "var(--cp-warning)", name: "Amber" },
  { color: "var(--cp-text)", name: "Text" },
];
const TAP_TARGETS = "a[href],button,summary,label,[role=button]";
const MIN_STEP = 1.2;
const TAP_MS = 350;

export function initializeWhiteboard() {
  const root = document.documentElement;
  const app = document.getElementById("top");
  const ink = document.getElementById("ink");
  const bar = document.getElementById("wbbar");
  const language = root.lang === "it" ? "it" : "en";
  const labels = language === "it"
    ? { toolbar: "Strumenti di annotazione", mouse: "Disegno con il mouse", colors: "Colore dell'inchiostro",
      width: "Spessore", undo: "Annulla", clear: "Cancella", clearConfirm: "Cancellare tutte le annotazioni?",
      undoTitle: "Annulla l'ultimo tratto (Ctrl+Z)", clearTitle: "Cancella le annotazioni di questa pagina",
      colorNames: ["Accento", "Blu", "Verde", "Ambra", "Testo"] }
    : { toolbar: "Whiteboard tools", mouse: "Mouse draws", colors: "Ink colour",
      width: "Stroke width", undo: "Undo", clear: "Clear", clearConfirm: "Clear all annotations?",
      undoTitle: "Undo last stroke (Ctrl+Z)", clearTitle: "Clear annotations on this page",
      colorNames: COLORS.map(item => item.name) };
  const storeKey = `giandoria-whiteboard-data-agent-story-${language}-v1`;
  const pages = {};
  let color = COLORS[0].color;
  let width = 3;
  let mouseDraw = false;
  let current = null;
  let pendingSync = false;

  bar.setAttribute("aria-label", labels.toolbar);
  document.getElementById("mousedraw").textContent = labels.mouse;
  document.getElementById("colors").setAttribute("aria-label", labels.colors);
  document.getElementById("width-label").textContent = labels.width;
  document.getElementById("undo").textContent = labels.undo;
  document.getElementById("undo").title = labels.undoTitle;
  document.getElementById("clear").textContent = labels.clear;
  document.getElementById("clear").title = labels.clearTitle;

  const strokes = () => pages.page || (pages.page = []);

  function readStore() {
    try {
      const stored = localStorage.getItem(storeKey);
      if (!stored) return {};
      const data = JSON.parse(stored);
      if (data && typeof data === "object" && !Array.isArray(data)) return data;
      console.warn("Whiteboard ink was not loaded because its saved data is invalid.");
    } catch (error) {
      console.warn("Whiteboard ink could not be read.", error);
    }
    return null;
  }

  function persist() {
    const data = readStore();
    if (!data) return;
    if (strokes().length) {
      data.page = strokes().map(stroke => ({
        c: stroke.color,
        w: stroke.width,
        p: stroke.points,
      }));
    } else {
      delete data.page;
    }
    try {
      localStorage.setItem(storeKey, JSON.stringify(data));
    } catch (error) {
      console.warn("Whiteboard ink was not saved.", error);
    }
  }

  function load() {
    const data = readStore();
    if (!data) return;
    pages.page = Array.isArray(data.page)
      ? data.page.flatMap(stroke => {
        if (!stroke || !Array.isArray(stroke.p) || !stroke.p.length) return [];
        const points = stroke.p.filter(point => Number.isFinite(point?.x) && Number.isFinite(point?.y));
        if (!points.length) return [];
        return [{
          color: COLORS.some(item => item.color === stroke.c) ? stroke.c : COLORS[0].color,
          width: Number.isFinite(stroke.w) ? Math.max(1, Math.min(27, stroke.w)) : 3,
          points,
          element: null,
        }];
      })
      : [];
  }

  function pathData(points) {
    if (points.length === 1) {
      const point = points[0];
      return `M ${point.x} ${point.y} L ${point.x + 0.01} ${point.y}`;
    }
    let path = `M ${points[0].x} ${points[0].y}`;
    for (let index = 1; index < points.length - 1; index++) {
      const point = points[index];
      const next = points[index + 1];
      path += ` Q ${point.x} ${point.y} ${(point.x + next.x) / 2} ${(point.y + next.y) / 2}`;
    }
    const last = points.at(-1);
    return `${path} L ${last.x} ${last.y}`;
  }

  function createElement(stroke) {
    const path = document.createElementNS(NS, "path");
    path.setAttribute("d", pathData(stroke.points));
    path.setAttribute("stroke-width", stroke.width);
    path.style.stroke = stroke.color;
    ink.appendChild(path);
    stroke.element = path;
  }

  function resizeInk() {
    ink.style.height = `${app.offsetHeight}px`;
  }

  function render() {
    ink.replaceChildren();
    strokes().forEach(createElement);
    resizeInk();
  }

  function syncToolbar() {
    const height = `${Math.ceil(bar.getBoundingClientRect().height)}px`;
    if (document.body.style.paddingTop !== height) {
      document.body.style.paddingTop = height;
      root.style.scrollPaddingTop = height;
    }
  }

  function pointFrom(event) {
    const rect = ink.getBoundingClientRect();
    return {
      x: Math.round((event.clientX - rect.left) * 10) / 10,
      y: Math.round((event.clientY - rect.top) * 10) / 10,
    };
  }

  function segmentDistanceSquared(px, py, ax, ay, bx, by) {
    const dx = bx - ax;
    const dy = by - ay;
    const lengthSquared = dx * dx + dy * dy;
    const t = lengthSquared
      ? Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / lengthSquared))
      : 0;
    const ex = px - (ax + t * dx);
    const ey = py - (ay + t * dy);
    return ex * ex + ey * ey;
  }

  function eraseAt(point) {
    let changed = false;
    for (let index = strokes().length - 1; index >= 0; index--) {
      const stroke = strokes()[index];
      const radius = Math.max(stroke.width, 10) + 10;
      const radiusSquared = radius * radius;
      const points = stroke.points;
      let hit = points.length === 1
        && (points[0].x - point.x) ** 2 + (points[0].y - point.y) ** 2 <= radiusSquared;
      for (let segment = 0; segment < points.length - 1 && !hit; segment++) {
        hit = segmentDistanceSquared(point.x, point.y,
          points[segment].x, points[segment].y, points[segment + 1].x, points[segment + 1].y) <= radiusSquared;
      }
      if (hit) {
        stroke.element?.remove();
        strokes().splice(index, 1);
        changed = true;
      }
    }
    return changed;
  }

  const isPen = event => event.pointerType === "pen" || event.pointerType === "eraser";
  const isEraser = event => event.pointerType === "eraser"
    || (event.pointerType === "pen" && ((event.buttons & 32) === 32 || event.button === 5));
  function arm(capture, lockPan) {
    ink.style.pointerEvents = capture ? "auto" : "none";
    root.style.touchAction = lockPan ? "none" : "";
  }

  function route(event) {
    if (current) return;
    if (isPen(event)) arm(true, true);
    else if (event.pointerType === "mouse") arm(mouseDraw, false);
    else arm(false, false);
  }

  function release(pointerId) {
    if (ink.hasPointerCapture(pointerId)) ink.releasePointerCapture(pointerId);
  }

  function finish() {
    if (!current) return;
    const drawing = current;
    current = null;
    try {
      release(drawing.pointerId);
    } catch {
      // Pointer capture may already have been released by the browser.
    }
    if (drawing.mode === "pen" || drawing.changed) persist();
    if (pendingSync) {
      pendingSync = false;
      load();
      render();
    }
  }

  function interactiveTarget(x, y) {
    const previous = ink.style.pointerEvents;
    ink.style.pointerEvents = "none";
    const hit = document.elementFromPoint(x, y);
    ink.style.pointerEvents = previous;
    return hit?.closest(TAP_TARGETS);
  }

  function onPointerDown(event) {
    if (event.pointerType === "touch") return;
    if (event.pointerType === "mouse" && (!mouseDraw || event.button !== 0)) return;
    finish();
    event.preventDefault();
    try {
      ink.setPointerCapture(event.pointerId);
    } catch {
      // Synthetic pointers and devices that do not support capture still use in-bounds events.
    }
    const point = pointFrom(event);
    if (isEraser(event)) {
      current = { pointerId: event.pointerId, mode: "erase", changed: eraseAt(point) };
      return;
    }
    const pressure = event.pressure > 0 ? event.pressure : 0.5;
    const stroke = {
      color,
      width: Math.round(Math.max(1, width * (0.55 + 0.9 * pressure)) * 100) / 100,
      points: [point],
      element: null,
    };
    strokes().push(stroke);
    createElement(stroke);
    current = {
      pointerId: event.pointerId,
      mode: "pen",
      stroke,
      startedAt: event.timeStamp,
      moved: false,
      pen: event.pointerType === "pen",
    };
  }

  function onPointerMove(event) {
    if (!current || event.pointerId !== current.pointerId) return;
    event.preventDefault();
    const samples = event.getCoalescedEvents?.() ?? [];
    for (const sample of samples.length ? samples : [event]) {
      const point = pointFrom(sample);
      if (current.mode === "erase") {
        current.changed = eraseAt(point) || current.changed;
        continue;
      }
      const points = current.stroke.points;
      const last = points.at(-1);
      if (Math.hypot(point.x - last.x, point.y - last.y) < MIN_STEP) continue;
      points.push(point);
      current.moved = true;
    }
    if (current.mode === "pen") {
      current.stroke.element.setAttribute("d", pathData(current.stroke.points));
    }
  }

  function onPointerUp(event) {
    if (!current || event.pointerId !== current.pointerId) return;
    const drawing = current;
    if (drawing.mode === "pen" && drawing.pen && event.type === "pointerup"
      && !drawing.moved && event.timeStamp - drawing.startedAt < TAP_MS) {
      const target = interactiveTarget(event.clientX, event.clientY);
      if (target) {
        strokes().splice(strokes().indexOf(drawing.stroke), 1);
        drawing.stroke.element.remove();
        finish();
        target.click();
        return;
      }
    }
    finish();
  }

  const colorBox = document.getElementById("colors");
  COLORS.forEach((item, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "wb-swatch";
    button.style.background = item.color;
    button.title = labels.colorNames[index];
    button.setAttribute("aria-label", labels.colorNames[index]);
    button.setAttribute("aria-pressed", String(index === 0));
    button.addEventListener("click", () => {
      color = item.color;
      colorBox.querySelectorAll(".wb-swatch").forEach(swatch => {
        swatch.setAttribute("aria-pressed", String(swatch === button));
      });
    });
    colorBox.appendChild(button);
  });

  const mouseButton = document.getElementById("mousedraw");
  mouseButton.addEventListener("click", () => {
    mouseDraw = !mouseDraw;
    mouseButton.setAttribute("aria-pressed", String(mouseDraw));
    ink.classList.toggle("mouse", mouseDraw);
  });
  document.getElementById("width").addEventListener("input", event => {
    width = Number(event.target.value);
  });
  document.getElementById("undo").addEventListener("click", () => {
    finish();
    const stroke = strokes().pop();
    if (stroke) {
      stroke.element?.remove();
      persist();
    }
  });
  document.getElementById("clear").addEventListener("click", () => {
    finish();
    if (!strokes().length || !window.confirm(labels.clearConfirm)) return;
    pages.page = [];
    render();
    persist();
  });

  window.addEventListener("pointerover", route, { passive: true });
  window.addEventListener("pointermove", route, { passive: true });
  window.addEventListener("pointerout", event => {
    if (!current && isPen(event) && !event.relatedTarget) arm(false, false);
  }, { passive: true });
  window.addEventListener("blur", () => {
    finish();
    arm(false, false);
  });
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      finish();
      arm(false, false);
    }
  });
  ink.addEventListener("pointerdown", onPointerDown);
  ink.addEventListener("pointermove", onPointerMove);
  ink.addEventListener("pointerup", onPointerUp);
  ink.addEventListener("pointercancel", onPointerUp);
  ink.addEventListener("lostpointercapture", event => {
    if (current && event.pointerId === current.pointerId) finish();
  });
  ink.addEventListener("contextmenu", event => event.preventDefault());
  window.addEventListener("pointerup", onPointerUp);
  window.addEventListener("storage", event => {
    if (event.key !== storeKey && event.key !== null) return;
    if (current) {
      pendingSync = true;
      return;
    }
    load();
    render();
  });
  window.addEventListener("keydown", event => {
    if (event.target instanceof Element && event.target.closest("input,select,textarea,[contenteditable]")) return;
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "z") {
      event.preventDefault();
      document.getElementById("undo").click();
    }
  });

  const observer = new ResizeObserver(() => {
    syncToolbar();
    resizeInk();
  });
  observer.observe(app);
  observer.observe(bar);
  root.classList.add("whiteboard-ready");
  syncToolbar();
  load();
  render();
}
