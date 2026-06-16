
function setHTML(element, htmlString) {
  if (!element) return;
  element.textContent = '';
  const parser = new DOMParser();
  const doc = parser.parseFromString(htmlString, 'text/html');
  while (doc.body.firstChild) {
    element.appendChild(doc.body.firstChild);
  }
}

/**
 * GuiGazer — WebSocket Dashboard Client
 * ======================================
 * Connects to the FastAPI backend over a WebSocket, sends tasks / audit
 * requests, and renders live screenshots + action-log entries.
 */

(() => {
  "use strict";

  // ── DOM refs ──────────────────────────────────────────────────────
  const taskInput      = document.getElementById("task-input");
  const urlInput       = document.getElementById("url-input");
  const startBtn       = document.getElementById("start-btn");
  const auditBtn       = document.getElementById("audit-btn");
  const statusDot      = document.getElementById("status-dot");
  const statusText     = document.getElementById("status-text");
  const screenshotImg  = document.getElementById("screenshot-img");
  const placeholder    = document.getElementById("viewer-placeholder");
  const actionLog      = document.getElementById("action-log");
  const logEmpty       = document.getElementById("log-empty");
  const stepCounter    = document.getElementById("step-counter");
  const clearLogBtn    = document.getElementById("clear-log");

  let ws        = null;
  let stepNum   = 0;
  let isRunning = false;

  // ── WebSocket ─────────────────────────────────────────────────────
  function connect() {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const url   = `${proto}://${location.hostname}:8001/ws`;

    ws = new WebSocket(url);

    ws.addEventListener("open", () => {
      console.log("[GuiGazer] WebSocket connected");
      setStatus("idle", "Connected");
    });

    ws.addEventListener("close", () => {
      console.warn("[GuiGazer] WebSocket closed — reconnecting in 3 s");
      setStatus("error", "Disconnected");
      setTimeout(connect, 3000);
    });

    ws.addEventListener("error", (e) => {
      console.error("[GuiGazer] WebSocket error", e);
    });

    ws.addEventListener("message", (event) => {
      let data;
      try { data = JSON.parse(event.data); }
      catch { return console.error("Bad JSON:", event.data); }
      handleMessage(data);
    });
  }

  // ── Message handler ───────────────────────────────────────────────
  function handleMessage(data) {
    switch (data.type) {

      case "step":
        stepNum++;
        stepCounter.textContent = `Step ${stepNum}`;
        setStatus("running", `Running — step ${stepNum}`);

        // Update screenshot
        if (data.screenshot) {
          screenshotImg.src = `data:image/png;base64,${data.screenshot}`;
          screenshotImg.classList.remove("hidden");
          placeholder.classList.add("hidden");
        }

        // Append log entry
        appendAction({
          step:    stepNum,
          action:  data.action  || "click",
          element: data.element || "",
          reason:  data.reason  || "",
        });
        break;

      case "status":
        setStatus(data.status || "idle", data.message || data.status);
        break;

      case "complete":
        setStatus("complete", data.message || "Task complete");
        appendComplete(data.message || "Task completed successfully ✓");
        setRunning(false);
        break;

      case "audit_result":
        if (data.html) {
          const win = window.open("", "_blank");
          if (win) { win.document.write(data.html); win.document.close(); }
        }
        if (data.url) { window.open(data.url, "_blank"); }
        setStatus("complete", "Audit done");
        setRunning(false);
        break;

      case "error":
        setStatus("error", data.message || "Error");
        appendError(data.message || "An error occurred");
        setRunning(false);
        break;

      default:
        console.log("[GuiGazer] Unknown message type:", data.type, data);
    }
  }

  // ── Button handlers ───────────────────────────────────────────────
  startBtn.addEventListener("click", () => {
    if (!ws || ws.readyState !== WebSocket.OPEN) return alert("Not connected to server.");
    const task = taskInput.value.trim();
    const url  = urlInput.value.trim();
    if (!task) return taskInput.focus();

    resetLog();
    ws.send(JSON.stringify({ type: "start_task", task, url }));
    setRunning(true);
    setStatus("running", "Starting…");
  });

  auditBtn.addEventListener("click", () => {
    if (!ws || ws.readyState !== WebSocket.OPEN) return alert("Not connected to server.");
    const url = urlInput.value.trim();

    ws.send(JSON.stringify({ type: "run_audit", url }));
    setStatus("running", "Running audit…");
    setRunning(true);
  });

  clearLogBtn.addEventListener("click", resetLog);

  // ── Helpers ───────────────────────────────────────────────────────
  function setStatus(state, text) {
    statusDot.className  = `status-dot ${state}`;
    statusText.textContent = text || state;
  }

  function setRunning(v) {
    isRunning = v;
    startBtn.disabled = v;
  }

  function resetLog() {
    stepNum = 0;
    stepCounter.textContent = "Step 0";
    setHTML(actionLog, "");
    logEmpty.style.display = "";
    actionLog.appendChild(logEmpty);
  }

  function hideEmpty() {
    if (logEmpty) logEmpty.style.display = "none";
  }

  function scrollLog() {
    actionLog.scrollTop = actionLog.scrollHeight;
  }

  // ── Log entry renderers ───────────────────────────────────────────
  function appendAction({ step, action, element, reason }) {
    hideEmpty();
    const badgeClass = ["click","type","scroll","done","error","navigate"].includes(action) ? action : "click";

    const entry = document.createElement("div");
    entry.className = "action-entry";
    setHTML(entry, `
      <div class="step-num">${step}</div>
      <div class="action-body">
        <div class="action-meta">
          <span class="action-badge ${badgeClass}">${escHtml(action)}</span>
          <span class="action-element">${escHtml(element)}</span>
        </div>
        ${reason ? `);<div class="action-reason">${escHtml(reason)}</div>` : ""}
      </div>`;
    actionLog.appendChild(entry);
    scrollLog();
  }

  function appendComplete(message) {
    hideEmpty();
    const el = document.createElement("div");
    el.className = "msg-complete";
    setHTML(el, `<svg width="16" height="16" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M10 18a8 8 0 1 0 0-16 8 8 0 0 0 0 16Zm3.857-9.809a.75.75 0 0 0-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 1 0-1.06 1.061l2.5 2.5a.75.75 0 0 0 1.137-.089l4-5.5Z" clip-rule="evenodd"/></svg> ${escHtml(message)}`);
    actionLog.appendChild(el);
    scrollLog();
  }

  function appendError(message) {
    hideEmpty();
    const el = document.createElement("div");
    el.className = "msg-error";
    setHTML(el, `<svg width="16" height="16" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0Zm-8-5a.75.75 0 0 1 .75.75v4.5a.75.75 0 0 1-1.5 0v-4.5A.75.75 0 0 1 10 5Zm0 10a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z" clip-rule="evenodd"/></svg> ${escHtml(message)}`);
    actionLog.appendChild(el);
    scrollLog();
  }

  function escHtml(str) {
    const d = document.createElement("div");
    d.textContent = str;
    return d.innerHTML;
  }

  // ── Boot ──────────────────────────────────────────────────────────
  connect();
})();
