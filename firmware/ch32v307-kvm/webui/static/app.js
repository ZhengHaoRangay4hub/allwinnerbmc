const params = new URLSearchParams(location.search);
const token = params.get("token") || localStorage.getItem("kvm-web-token") || "";
if (token) localStorage.setItem("kvm-web-token", token);

const api = async (path, body) => {
  const response = await fetch(path, {
    method: body === undefined ? "GET" : "POST",
    headers: { "Content-Type": "application/json", "X-KVM-Token": token },
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: "no-store",
  });
  const result = await response.json().catch(() => ({ ok: false, error: `HTTP ${response.status}` }));
  if (!response.ok || !result.ok) throw new Error(result.error || `HTTP ${response.status}`);
  return result;
};

const statusCards = Object.fromEntries(
  [...document.querySelectorAll("[data-status]")].map((el) => [el.dataset.status, el]),
);

function setCard(name, state, label, detail = "") {
  const card = statusCards[name];
  card.classList.remove("is-good", "is-warn", "is-bad");
  card.classList.add(`is-${state}`);
  card.querySelector("strong").textContent = label;
  const em = card.querySelector("em");
  if (em) em.textContent = detail;
}

function formatUptime(seconds) {
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  return minutes < 60 ? `${minutes}m` : `${Math.floor(minutes / 60)}h ${minutes % 60}m`;
}

async function refreshStatus() {
  const notice = document.querySelector("#notice");
  try {
    const status = await api("/api/status");
    setCard("server", "good", "运行中", `已运行 ${formatUptime(status.server.uptime)}`);
    setCard(
      "serial",
      status.serial.connected ? "warn" : "bad",
      status.serial.connected ? "串口已打开" : "未连接",
      status.serial.device || "等待 WCH-Link",
    );
    setCard("keyboard", status.hid.keyboard ? "good" : "bad", status.hid.keyboard ? "已枚举" : "未发现");
    setCard("mouse", status.hid.mouse ? "good" : "bad", status.hid.mouse ? "已枚举" : "未发现");
    document.querySelector("#serial-device").textContent = status.serial.device || "—";
    document.querySelector("#serial-baud").textContent = String(status.serial.baudrate);
    document.querySelector("#frames-sent").textContent = String(status.serial.framesSent);
    document.querySelector("#last-action").textContent = status.lastAction;
    document.querySelector("#connection-detail").textContent = `${location.host} · ${status.serial.mode}`;
    if (status.serial.lastError) {
      notice.className = "notice error";
      notice.textContent = status.serial.lastError;
    } else if (status.serial.connected) {
      notice.className = "notice";
      notice.textContent = "WCH-Link 串口可以写入；当前协议没有回执，是否被 CH32 接收需结合 P6 实际键鼠动作确认。";
    } else {
      notice.className = "notice error";
      notice.textContent = "请连接 WCH-Link，或检查串口是否正被其他程序占用。";
    }
  } catch (error) {
    setCard("server", "bad", "连接失败");
    notice.className = "notice error";
    notice.textContent = token ? error.message : "URL 中缺少访问令牌，请使用服务启动时显示的完整地址。";
  }
}

const pointer = { x: 16384, y: 16384, buttons: 0 };
const pointerLabelX = document.querySelector("#pointer-x");
const pointerLabelY = document.querySelector("#pointer-y");
let pointerQueued = null;
let pointerSending = false;

function updatePointerLabels() {
  pointerLabelX.textContent = String(pointer.x);
  pointerLabelY.textContent = String(pointer.y);
}

async function flushPointer() {
  if (pointerSending || !pointerQueued) return;
  pointerSending = true;
  while (pointerQueued) {
    const next = pointerQueued;
    pointerQueued = null;
    try {
      await api("/api/pointer", next);
    } catch (error) {
      document.querySelector("#notice").textContent = error.message;
    }
  }
  pointerSending = false;
}

function sendPointer(wheel = 0) {
  pointerQueued = { ...pointer, wheel };
  requestAnimationFrame(flushPointer);
  updateHeartbeat();
}

const touchpad = document.querySelector("#touchpad");
const activePointers = new Map();
let gestureStart = null;
let lastMidY = null;
let gestureWasMulti = false;

touchpad.addEventListener("pointerdown", (event) => {
  event.preventDefault();
  touchpad.setPointerCapture(event.pointerId);
  activePointers.set(event.pointerId, { x: event.clientX, y: event.clientY });
  if (activePointers.size === 1) {
    gestureStart = { x: event.clientX, y: event.clientY, at: performance.now(), moved: 0 };
    gestureWasMulti = false;
  }
  if (activePointers.size === 2) {
    gestureWasMulti = true;
    lastMidY = [...activePointers.values()].reduce((sum, item) => sum + item.y, 0) / 2;
  }
  touchpad.classList.add("is-active");
});

touchpad.addEventListener("pointermove", (event) => {
  const previous = activePointers.get(event.pointerId);
  if (!previous) return;
  event.preventDefault();
  const dx = event.clientX - previous.x;
  const dy = event.clientY - previous.y;
  activePointers.set(event.pointerId, { x: event.clientX, y: event.clientY });

  if (activePointers.size >= 2) {
    const midY = [...activePointers.values()].reduce((sum, item) => sum + item.y, 0) / activePointers.size;
    if (lastMidY !== null && Math.abs(midY - lastMidY) >= 5) {
      sendPointer(midY > lastMidY ? 1 : -1);
      lastMidY = midY;
    }
    return;
  }

  const sensitivity = Number(document.querySelector("#sensitivity").value);
  pointer.x = Math.max(0, Math.min(32767, Math.round(pointer.x + dx * sensitivity)));
  pointer.y = Math.max(0, Math.min(32767, Math.round(pointer.y + dy * sensitivity)));
  if (gestureStart) gestureStart.moved += Math.hypot(dx, dy);
  updatePointerLabels();
  sendPointer();
});

function finishPointer(event) {
  const wasSingle = activePointers.size === 1;
  activePointers.delete(event.pointerId);
  if (wasSingle && !gestureWasMulti && gestureStart && gestureStart.moved < 9 && performance.now() - gestureStart.at < 260) {
    pointer.buttons |= 1;
    sendPointer();
    setTimeout(() => { pointer.buttons &= ~1; sendPointer(); }, 70);
  }
  if (activePointers.size === 0) {
    touchpad.classList.remove("is-active");
    gestureStart = null;
    lastMidY = null;
    gestureWasMulti = false;
  }
  updateHeartbeat();
}

touchpad.addEventListener("pointerup", finishPointer);
touchpad.addEventListener("pointercancel", finishPointer);
touchpad.addEventListener("contextmenu", (event) => event.preventDefault());

document.querySelectorAll("[data-mouse-button]").forEach((button) => {
  const mask = Number(button.dataset.mouseButton);
  const down = (event) => {
    event.preventDefault();
    pointer.buttons |= mask;
    button.classList.add("is-pressed");
    sendPointer();
  };
  const up = () => {
    pointer.buttons &= ~mask;
    button.classList.remove("is-pressed");
    sendPointer();
  };
  button.addEventListener("pointerdown", down);
  button.addEventListener("pointerup", up);
  button.addEventListener("pointercancel", up);
  button.addEventListener("pointerleave", (event) => { if (event.buttons) up(); });
});

document.querySelector("#recenter").addEventListener("click", () => {
  pointer.x = pointer.y = 16384;
  updatePointerLabels();
  sendPointer();
});
const sensitivity = document.querySelector("#sensitivity");
sensitivity.addEventListener("input", () => { document.querySelector("#sensitivity-value").value = sensitivity.value; });

const rows = [
  [k("Esc", 0x29, 1.25), k("F1", 0x3a), k("F2", 0x3b), k("F3", 0x3c), k("F4", 0x3d), gap(.35), k("F5", 0x3e), k("F6", 0x3f), k("F7", 0x40), k("F8", 0x41), gap(.35), k("F9", 0x42), k("F10", 0x43), k("F11", 0x44), k("F12", 0x45), k("Del", 0x4c, 1.2)],
  [k("`", 0x35), k("1", 0x1e), k("2", 0x1f), k("3", 0x20), k("4", 0x21), k("5", 0x22), k("6", 0x23), k("7", 0x24), k("8", 0x25), k("9", 0x26), k("0", 0x27), k("-", 0x2d), k("=", 0x2e), k("Backspace", 0x2a, 2)],
  [k("Tab", 0x2b, 1.5), ...letters("QWERTYUIOP", 0x14), k("[", 0x2f), k("]", 0x30), k("\\", 0x31, 1.5)],
  [k("Caps", 0x39, 1.8), ...letters("ASDFGHJKL", 0x04), k(";", 0x33), k("'", 0x34), k("Enter", 0x28, 2.2)],
  [mod("Shift", 0x02, 2.25), ...letters("ZXCVBNM", 0x1d), k(",", 0x36), k(".", 0x37), k("/", 0x38), mod("Shift", 0x20, 2.25)],
  [mod("Ctrl", 0x01, 1.35), mod("⌥ Alt", 0x04, 1.35), mod("⌘", 0x08, 1.25), k("Space", 0x2c, 6), mod("⌘", 0x80, 1.25), mod("⌥ Alt", 0x40, 1.35), k("←", 0x50), k("↑", 0x52), k("↓", 0x51), k("→", 0x4f)],
];

function k(label, usage, width = 1) { return { label, usage, width }; }
function mod(label, modifier, width = 1) { return { label, modifier, width }; }
function gap(width) { return { spacer: true, width }; }
function letters(text, firstUsage) {
  return [...text].map((label) => ({ label, usage: 0x04 + label.toLowerCase().charCodeAt(0) - 97 }));
}

const keyboard = document.querySelector("#keyboard");
const activeKeys = new Set();
let modifiers = 0;
let keyboardQueue = Promise.resolve();
let heartbeatTimer = null;

function sendKeyboard() {
  const body = { modifiers, keys: [...activeKeys].slice(0, 6) };
  keyboardQueue = keyboardQueue.then(() => api("/api/keyboard", body)).catch((error) => {
    document.querySelector("#notice").textContent = error.message;
  });
  updateHeartbeat();
}

function updateHeartbeat() {
  const active = activeKeys.size > 0 || modifiers !== 0 || pointer.buttons !== 0 || activePointers.size > 0;
  if (active && !heartbeatTimer) heartbeatTimer = setInterval(() => api("/api/heartbeat", {}).catch(() => {}), 400);
  if (!active && heartbeatTimer) { clearInterval(heartbeatTimer); heartbeatTimer = null; }
}

rows.forEach((items) => {
  const row = document.createElement("div");
  row.className = "key-row";
  items.forEach((item) => {
    const key = document.createElement("button");
    key.type = "button";
    key.className = `key${item.modifier ? " is-modifier" : ""}${item.spacer ? " is-spacer" : ""}`;
    key.style.setProperty("--key-width", item.width || 1);
    key.textContent = item.label || "";
    if (!item.spacer && item.modifier) {
      key.addEventListener("click", () => {
        modifiers ^= item.modifier;
        key.classList.toggle("is-active", Boolean(modifiers & item.modifier));
        sendKeyboard();
      });
    } else if (!item.spacer) {
      const down = (event) => {
        event.preventDefault();
        activeKeys.add(item.usage);
        key.classList.add("is-active");
        sendKeyboard();
      };
      const up = () => {
        if (!activeKeys.delete(item.usage)) return;
        key.classList.remove("is-active");
        sendKeyboard();
      };
      key.addEventListener("pointerdown", down);
      key.addEventListener("pointerup", up);
      key.addEventListener("pointercancel", up);
      key.addEventListener("pointerleave", (event) => { if (event.buttons) up(); });
    }
    row.appendChild(key);
  });
  keyboard.appendChild(row);
});

async function releaseAll() {
  activeKeys.clear();
  modifiers = 0;
  pointer.buttons = 0;
  document.querySelectorAll(".key.is-active, .mouse-buttons .is-pressed").forEach((el) => el.classList.remove("is-active", "is-pressed"));
  updateHeartbeat();
  try { await api("/api/release", {}); } catch (error) { document.querySelector("#notice").textContent = error.message; }
}

document.querySelector("#release-all").addEventListener("click", releaseAll);
window.addEventListener("blur", releaseAll);
document.addEventListener("visibilitychange", () => { if (document.hidden) releaseAll(); });
window.addEventListener("beforeunload", () => {
  fetch(`/api/release?token=${encodeURIComponent(token)}`, { method: "POST", body: "{}", headers: { "Content-Type": "application/json" }, keepalive: true });
});

refreshStatus();
setInterval(refreshStatus, 1500);
