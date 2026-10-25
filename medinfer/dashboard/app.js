"use strict";
const $ = (id) => document.getElementById(id);
let runtime,
  allRuns = [],
  selectedRun,
  timer;
const fmt = (n, unit = "s") =>
  Number.isFinite(n) ? `${n.toFixed(2)} ${unit}` : "N/A";
const node = (tag, text, cls) => {
  const e = document.createElement(tag);
  if (text !== undefined) e.textContent = text;
  if (cls) e.className = cls;
  return e;
};
async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...options.headers };
  if ($("api-key").value)
    headers.Authorization = `Bearer ${$("api-key").value}`;
  const res = await fetch(path, { ...options, headers });
  if (res.status === 401) {
    document.querySelector(".keybox").classList.add("show");
    throw Error("Gateway requires an API key. Enter it above and connect.");
  }
  if (!res.ok) {
    const error = await res.json().catch(() => ({}));
    throw Error(
      typeof error.detail === "string"
        ? error.detail
        : `Request failed (${res.status})`,
    );
  }
  return res;
}
function notice(text, warn = false) {
  $("notice").textContent = text;
  $("notice").className = "notice" + (warn ? " warn" : "");
}
async function connect() {
  try {
    runtime = await (await api("/api/status")).json();
    $("runtime-name").textContent =
      runtime.backend === "mlx"
        ? "MLX / Apple Silicon"
        : runtime.backend.toUpperCase();
    $("model-name").textContent = runtime.model;
    $("mode").textContent = runtime.simulated
      ? "SIMULATED RUNTIME"
      : runtime.ready
        ? "MODEL RUNTIME"
        : "BACKEND OFFLINE";
    $("mode").className =
      "badge" + (runtime.simulated || !runtime.ready ? " warn" : "");
    notice(
      runtime.simulated
        ? "SIMULATED MODE · No model is running. Demo latency is software test evidence; token rates and model performance are unavailable."
        : runtime.ready
          ? "Private runtime connected. All bundled records are synthetic; benchmark outputs are stored locally."
          : "Backend is unavailable or the configured model is missing. Start the upstream service or check the model configuration.",
      runtime.simulated || !runtime.ready,
    );
    await refresh();
  } catch (e) {
    notice(e.message, true);
  }
}
function renderCharts(runs, latest) {
  const root = $("latency-chart");
  root.replaceChildren();
  const display = runs
    .filter((r) => r.summary && r.summary.latency_p95_s != null)
    .slice(0, 5)
    .reverse();
  if (!display.length) {
    root.textContent = "No completed measurements yet.";
    return;
  }
  const ns = "http://www.w3.org/2000/svg",
    svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", "0 0 550 185");
  svg.setAttribute("role", "img");
  svg.setAttribute(
    "aria-label",
    "P50 and P95 latency in seconds for recent runs",
  );
  const max =
    Math.max(...display.map((r) => r.summary.latency_p95_s), 0.001) * 1.15;
  function s(tag, attrs, text) {
    const el = document.createElementNS(ns, tag);
    for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
    if (text !== undefined) el.textContent = text;
    svg.append(el);
  }
  for (let i = 0; i <= 3; i++) {
    let x = 120 + (i * 370) / 3;
    s("line", { x1: x, y1: 10, x2: x, y2: 160, stroke: "#243246" });
    s(
      "text",
      { x, y: 180, fill: "#7b8da7", "font-size": 10, "text-anchor": "middle" },
      ((max * i) / 3).toFixed(1),
    );
  }
  display.forEach((r, i) => {
    const y = 15 + i * 29;
    s(
      "text",
      { x: 0, y: y + 11, fill: "#a4b7ce", "font-size": 10 },
      `${r.config.backend} · c${r.config.concurrency}${r.config.simulated ? " [SIM]" : ""}`,
    );
    s("rect", {
      x: 120,
      y,
      width: (r.summary.latency_p50_s / max) * 370,
      height: 7,
      fill: "#6ce5c4",
      rx: 2,
    });
    s("rect", {
      x: 120,
      y: y + 10,
      width: (r.summary.latency_p95_s / max) * 370,
      height: 7,
      fill: "#e9b96f",
      rx: 2,
    });
  });
  root.append(svg);
  const quality = $("quality-chart");
  quality.replaceChildren();
  quality.classList.remove("empty");
  const q = latest?.summary?.quality;
  for (const [label, value, n] of [
    [
      "Extraction · macro leaf F1",
      q?.extraction?.f1,
      q?.extraction?.n_successful,
    ],
    ["Passage QA · exact match", q?.qa?.exact_match, q?.qa?.n_successful],
    [
      "Summary · fact coverage proxy",
      q?.summary?.key_fact_coverage_proxy,
      q?.summary?.n_successful,
    ],
  ]) {
    const row = node("div", undefined, "quality-row"),
      title = node("div");
    title.append(
      node("span", `${label} (n=${n || 0})`),
      node(
        "span",
        Number.isFinite(value) ? `${(value * 100).toFixed(1)}%` : "N/A",
      ),
    );
    const track = node("div", undefined, "track");
    // SVG width attribute avoids inline styles, keeping a strict Content-Security-Policy.
    const bar = document.createElementNS(ns, "svg");
    bar.setAttribute("width", "100%");
    bar.setAttribute("height", "5");
    const rect = document.createElementNS(ns, "rect");
    rect.setAttribute("width", `${(value || 0) * 100}%`);
    rect.setAttribute("height", "5");
    rect.setAttribute("fill", "#6ce5c4");
    bar.append(rect);
    track.append(bar);
    row.append(title, track);
    quality.append(row);
  }
}
async function refresh() {
  allRuns = await (await api("/api/runs")).json();
  const latest = allRuns.find((r) => r.summary);
  if (latest) {
    const s = latest.summary;
    $("ttft").textContent = fmt(s.ttft_p50_s);
    $("p95").textContent = fmt(s.latency_p95_s);
    $("tps").textContent = fmt(s.output_tokens_s, "tok/s");
    $("success").textContent = `${s.successful} / ${s.requests}`;
    $("error-rate").textContent =
      `${((s.error_rate || 0) * 100).toFixed(1)}% errors · ${s.truncated} length-limited`;
    $("latest-label").textContent =
      `${latest.config.backend} · c${latest.config.concurrency} · max ${latest.config.max_tokens} tokens · ${latest.config.simulated ? "SIMULATED" : "MEASURED"}`;
  }
  renderCharts(allRuns, latest);
  const body = $("runs");
  body.replaceChildren();
  for (const run of allRuns) {
    const tr = node("tr"),
      first = node("td", run.id.slice(0, 8));
    first.append(node("small", new Date(run.created_at).toLocaleString()));
    const model = node("td", run.config.backend.toUpperCase());
    model.append(node("small", run.config.model));
    const status = node("td");
    status.append(
      node(
        "span",
        `${run.status}${run.config.simulated ? " · SIM" : ""}`,
        "badge" +
          (run.config.simulated || run.status !== "completed" ? " warn" : ""),
      ),
    );
    const action = node("td"),
      button = node("button", "Inspect ↗", "secondary");
    button.addEventListener("click", () => inspect(run.id));
    action.append(button);
    tr.append(
      first,
      model,
      node("td", `c${run.config.concurrency} × ${run.config.repetitions}`),
      status,
      node(
        "td",
        run.summary
          ? `${fmt(run.summary.latency_p50_s)} / ${fmt(run.summary.latency_p95_s)}`
          : "—",
      ),
      node("td", fmt(run.summary?.output_tokens_s, "")),
      action,
    );
    body.append(tr);
  }
  if (!allRuns.length) {
    const row = node("tr"),
      cell = node("td", "No runs yet. Start an experiment above.", "empty");
    cell.colSpan = 7;
    row.append(cell);
    body.append(row);
  }
}
async function inspect(id) {
  try {
    selectedRun = await (
      await api(`/api/runs/${encodeURIComponent(id)}`)
    ).json();
    $("run-detail").hidden = false;
    $("detail-meta").textContent =
      `Dataset SHA256: ${selectedRun.config.dataset_sha256} · Gateway RSS peak: ${selectedRun.summary?.resources?.gateway_rss_peak_bytes ? (selectedRun.summary.resources.gateway_rss_peak_bytes / 1e6).toFixed(1) + " MB" : "N/A"}`;
    $("raw-run").textContent = JSON.stringify(selectedRun, null, 2);
    const root = $("records");
    root.replaceChildren();
    for (const r of selectedRun.records) {
      const tr = node("tr"),
        caseCell = node("td"),
        caseButton = node("button", r.case_id, "secondary");
      caseButton.addEventListener("click", () => {
        $("raw-run").textContent = JSON.stringify(r, null, 2);
        const detail = document.querySelector("#run-detail details");
        detail.open = true;
        detail.scrollIntoView({ behavior: "smooth", block: "center" });
      });
      caseCell.append(caseButton);
      tr.append(caseCell);
      for (const value of [
        fmt(r.latency_s),
        fmt(r.ttft_s),
        r.finish_reason || "error",
        r.error || JSON.stringify(r.scores),
      ])
        tr.append(node("td", value));
      root.append(tr);
    }
    $("run-detail").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (e) {
    notice(e.message, true);
  }
}
$("benchmark-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  $("run-button").disabled = true;
  try {
    const payload = {
      task: $("task").value,
      concurrency: +$("concurrency").value,
      repetitions: +$("repetitions").value,
      max_tokens: +$("max-tokens").value,
      warmup: +$("warmup").value,
    };
    const run = await (
      await api("/api/benchmarks", {
        method: "POST",
        body: JSON.stringify(payload),
      })
    ).json();
    $("run-progress").textContent =
      `Experiment ${run.id.slice(0, 8)} is running. Warmup and model loading may take time.`;
    clearInterval(timer);
    let polling = false;
    timer = setInterval(async () => {
      if (polling) return;
      polling = true;
      try {
        await refresh();
        const current = allRuns.find((r) => r.id === run.id);
        if (current && current.status !== "running") {
          clearInterval(timer);
          $("run-progress").textContent =
            `Experiment ${current.status}${current.error ? ": " + current.error : ". Inspect the per-request evidence below."}`;
          $("run-button").disabled = false;
        }
      } catch (error) {
        clearInterval(timer);
        notice(error.message, true);
        $("run-button").disabled = false;
      } finally {
        polling = false;
      }
    }, 1500);
  } catch (error) {
    notice(error.message, true);
    $("run-button").disabled = false;
  }
});
$("chat-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!runtime) return;
  $("chat-button").disabled = true;
  $("chat-output").textContent = "Generating…";
  try {
    const result = await (
      await api("/v1/chat/completions", {
        method: "POST",
        body: JSON.stringify({
          model: runtime.model,
          messages: [{ role: "user", content: $("prompt").value }],
          max_tokens: 1024,
        }),
      })
    ).json();
    const message = result.choices[0].message;
    $("chat-output").textContent =
      "Final answer:\n" +
      (message.content.trim() ||
        `(No final answer; finish: ${result.choices[0].finish_reason})`) +
      (message.reasoning_content
        ? "\n\nReasoning (not a scored answer):\n" + message.reasoning_content
        : "");
    const m = result.medinfer_metrics;
    $("chat-metrics").textContent =
      `Latency ${fmt(m.latency_s)} · first output ${fmt(m.ttft_s)} · ${fmt(m.tokens_s, "tok/s")}${result.simulated ? " · SIMULATED" : ""}`;
  } catch (error) {
    $("chat-output").textContent = error.message;
  } finally {
    $("chat-button").disabled = false;
  }
});
for (const format of ["json", "csv"])
  $(format + "-export").addEventListener("click", async () => {
    if (!selectedRun) return;
    try {
      const response = await api(
        `/api/runs/${encodeURIComponent(selectedRun.id)}/export?format=${format}`,
      );
      const url = URL.createObjectURL(await response.blob());
      const a = node("a");
      a.href = url;
      a.download = `${selectedRun.id}.${format}`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) {
      notice(e.message, true);
    }
  });
$("refresh").addEventListener("click", () =>
  refresh().catch((e) => notice(e.message, true)),
);
$("connect").addEventListener("click", connect);
connect();
