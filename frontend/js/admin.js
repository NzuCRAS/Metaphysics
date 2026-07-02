const API_BASE_URL =
  window.location.hostname === "localhost"
    ? "http://localhost:8000/api/v1"
    : "/api/v1";

const EVENT_COLORS = {
  pageview: "#7abaff",
  bazi_request: "#f1d58a",
  bazi_report: "#7ae88a",
  palmistry_request: "#d9b35a",
  palmistry_report: "#5ee0a0",
};

const EVENT_LABELS = {
  pageview: "页面访问",
  bazi_request: "八字请求",
  bazi_report: "八字报告",
  palmistry_request: "手相请求",
  palmistry_report: "手相报告",
};

const PAGE_SIZE = 100;

const REGION_LABELS = {
  sun: "Sun",
  luna: "Luna",
  dirt: "Dirt",
  global: "Global",
};

function labelForRegion(region) {
  return REGION_LABELS[region] || region;
}

const tokenInput = document.getElementById("admin-token");
const dateInput = document.getElementById("report-date");
const errorEl = document.getElementById("error-message");
const dashboardEl = document.getElementById("dashboard");

let currentOffset = 0;
let currentEvents = [];
let totalEvents = 0;
let totalPages = 0;
let chartInstances = {};

function escapeHtml(str) {
  if (str == null) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function setDateDefault() {
  const now = new Date();
  dateInput.value = now.toISOString().split("T")[0];
}

function showError(message) {
  errorEl.textContent = message;
  errorEl.classList.remove("hidden");
  console.error("Admin error:", message);
}

function hideError() {
  errorEl.textContent = "";
  errorEl.classList.add("hidden");
}

function getToken() {
  return tokenInput.value.trim();
}

function getAuthHeaders() {
  return { Authorization: `Bearer ${getToken()}` };
}

function getInputs() {
  const token = getToken();
  const date = dateInput.value;
  if (!token || !date) {
    showError("请输入管理 Token 和日期。");
    return null;
  }
  return { token, date };
}

async function fetchJson(path) {
  const res = await fetch(`${API_BASE_URL}${path}`, { headers: getAuthHeaders() });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

async function fetchEvents(date, offset) {
  return fetchJson(`/admin/traffic-events?date=${date}&limit=${PAGE_SIZE}&offset=${offset}`);
}

function destroyCharts() {
  Object.values(chartInstances).forEach((c) => c.destroy());
  chartInstances = {};
}

function renderCard(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value;
}

function renderCards(summary) {
  renderCard("card-pv", summary.total_pageviews.toLocaleString());
  renderCard("card-bazi-req", summary.total_bazi_requests.toLocaleString());
  renderCard("card-bazi-rpt", summary.total_bazi_reports.toLocaleString());
  renderCard("card-palm-rpt", (summary.total_palmistry_reports || 0).toLocaleString());
  renderCard("card-ips", summary.unique_ips.toLocaleString());
  renderCard("card-cost", Number(summary.total_cost_cny || 0).toFixed(4));
}

function makeBarChart(canvasId, labels, datasets) {
  const ctx = document.getElementById(canvasId).getContext("2d");
  chartInstances[canvasId] = new Chart(ctx, {
    type: "bar",
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { labels: { color: "#f7f0df" } } },
      scales: {
        x: { ticks: { color: "#b8ab8e" }, grid: { color: "rgba(217,179,90,0.12)" } },
        y: { ticks: { color: "#b8ab8e" }, grid: { color: "rgba(217,179,90,0.12)" }, beginAtZero: true },
      },
    },
  });
}

function eventCountsToDatasets(rows, eventTypes) {
  return eventTypes.map((type) => ({
    label: EVENT_LABELS[type] || type,
    data: rows.map((r) => r[type] || 0),
    backgroundColor: EVENT_COLORS[type] || "#d9b35a",
  }));
}

function renderCharts(summary) {
  destroyCharts();

  const eventTypes = ["pageview", "bazi_request", "bazi_report"];

  makeBarChart(
    "hourly-chart",
    summary.hourly.map((r) => r.hour),
    eventCountsToDatasets(summary.hourly, eventTypes)
  );

  makeBarChart(
    "halfhour-chart",
    summary.half_hourly.map((r) => r.slot),
    eventCountsToDatasets(summary.half_hourly, eventTypes)
  );

  const regions = Object.keys(summary.by_region).sort();
  makeBarChart(
    "region-chart",
    regions.map((r) => labelForRegion(r)),
    eventCountsToDatasets(
      regions.map((region) => ({ ...summary.by_region[region], region })),
      eventTypes
    )
  );

  const costCtx = document.getElementById("cost-chart").getContext("2d");
  chartInstances["cost-chart"] = new Chart(costCtx, {
    type: "bar",
    data: {
      labels: regions.map((r) => labelForRegion(r)),
      datasets: [
        {
          label: "LLM cost (CNY)",
          data: regions.map((r) => summary.cost_by_region[r] || 0),
          backgroundColor: "#f1d58a",
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { labels: { color: "#f7f0df" } } },
      scales: {
        x: { ticks: { color: "#b8ab8e" }, grid: { color: "rgba(217,179,90,0.12)" } },
        y: { ticks: { color: "#b8ab8e" }, grid: { color: "rgba(217,179,90,0.12)" }, beginAtZero: true },
      },
    },
  });
}

function renderRegionTable(summary) {
  const tbody = document.getElementById("region-table");
  const regions = Object.keys(summary.by_region).sort();
  tbody.innerHTML = regions
    .map((region) => {
      const counts = summary.by_region[region] || {};
      return `
        <tr>
          <td>${escapeHtml(labelForRegion(region))}</td>
          <td>${counts.pageview || 0}</td>
          <td>${(counts.bazi_request || 0) + (counts.palmistry_request || 0)}</td>
          <td>${(counts.bazi_report || 0) + (counts.palmistry_report || 0)}</td>
          <td>${Number(summary.cost_by_region[region] || 0).toFixed(4)}</td>
        </tr>`;
    })
    .join("");
}

function renderBucketTable(tbodyId, rows, keyName) {
  const tbody = document.getElementById(tbodyId);
  tbody.innerHTML = rows
    .map((r) => {
      const label = r[keyName];
      return `
        <tr>
          <td>${escapeHtml(label)}</td>
          <td>${r.pageview || 0}</td>
          <td>${(r.bazi_request || 0) + (r.palmistry_request || 0)}</td>
          <td>${(r.bazi_report || 0) + (r.palmistry_report || 0)}</td>
        </tr>`;
    })
    .join("");
}

function formatTime(iso) {
  if (!iso) return "--";
  const d = new Date(iso);
  return d.toLocaleString();
}

function eventTag(type) {
  const label = EVENT_LABELS[type] || type;
  return `<span class="tag tag-${type}">${label}</span>`;
}

function renderEventLog(events) {
  const tbody = document.getElementById("event-log-table");
  tbody.innerHTML = events
    .map((ev) => {
      const ua = escapeHtml(ev.user_agent || "");
      return `
        <tr>
          <td>${formatTime(ev.timestamp)}</td>
          <td>${eventTag(escapeHtml(ev.event_type))}</td>
          <td>${escapeHtml(labelForRegion(ev.region))}</td>
          <td>${escapeHtml(ev.ip_address)}</td>
          <td>${escapeHtml(ev.path || "--")}</td>
          <td>${ev.tokens_input ?? "-"}</td>
          <td>${ev.tokens_output ?? "-"}</td>
          <td>${ev.cost_cny != null ? Number(ev.cost_cny).toFixed(4) : "-"}</td>
          <td class="ua" title="${ua}">${ua || "--"}</td>
        </tr>`;
    })
    .join("");
  const page = Math.floor(currentOffset / PAGE_SIZE) + 1;
  document.getElementById("page-info").textContent = `第 ${page} / ${totalPages} 页`;
  updatePaginationButtons();
}

function updatePaginationButtons() {
  document.getElementById("prev-page").disabled = currentOffset <= 0;
  document.getElementById("next-page").disabled =
    currentOffset + PAGE_SIZE >= totalEvents;
}

async function loadDashboard() {
  hideError();
  const inputs = getInputs();
  if (!inputs) return;

  try {
    destroyCharts();
    const summary = await fetchJson(`/admin/traffic-summary?date=${inputs.date}`);
    renderCards(summary);
    renderCharts(summary);
    renderRegionTable(summary);
    renderBucketTable("hourly-table", summary.hourly, "hour");
    renderBucketTable("halfhour-table", summary.half_hourly, "slot");

    currentOffset = 0;
    totalEvents = summary.total_events || 0;
    totalPages = Math.max(1, Math.ceil(totalEvents / PAGE_SIZE));
    currentEvents = await fetchEvents(inputs.date, currentOffset);
    renderEventLog(currentEvents);

    dashboardEl.classList.remove("hidden");
  } catch (err) {
    showError(err.message || "加载仪表盘失败。");
    dashboardEl.classList.add("hidden");
  }
}

async function changePage(delta) {
  const inputs = getInputs();
  if (!inputs) return;
  const newOffset = currentOffset + delta * PAGE_SIZE;
  if (newOffset < 0 || newOffset >= totalEvents) return;
  try {
    const events = await fetchEvents(inputs.date, newOffset);
    currentOffset = newOffset;
    currentEvents = events;
    renderEventLog(currentEvents);
  } catch (err) {
    showError(err.message || "加载事件失败。");
  }
}

async function jumpToPage(page) {
  const inputs = getInputs();
  if (!inputs) return;
  const target = Math.max(1, Math.min(totalPages, page));
  const newOffset = (target - 1) * PAGE_SIZE;
  if (newOffset === currentOffset) return;
  try {
    const events = await fetchEvents(inputs.date, newOffset);
    currentOffset = newOffset;
    currentEvents = events;
    renderEventLog(currentEvents);
  } catch (err) {
    showError(err.message || "加载事件失败。");
  }
}

document.getElementById("load-dashboard").addEventListener("click", loadDashboard);

document.getElementById("download-report").addEventListener("click", async () => {
  hideError();
  const inputs = getInputs();
  if (!inputs) return;

  try {
    const res = await fetch(`${API_BASE_URL}/admin/traffic-report?date=${inputs.date}`, {
      headers: getAuthHeaders(),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || `HTTP ${res.status}`);
    }
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `traffic_${inputs.date}.txt`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  } catch (err) {
    showError(err.message || "下载报告失败。");
  }
});

document.getElementById("prev-page").addEventListener("click", () => changePage(-1));
document.getElementById("next-page").addEventListener("click", () => changePage(1));

const jumpInput = document.getElementById("jump-page");
document.getElementById("go-page").addEventListener("click", () => {
  const page = parseInt(jumpInput.value, 10);
  if (Number.isFinite(page)) jumpToPage(page);
});
jumpInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    const page = parseInt(jumpInput.value, 10);
    if (Number.isFinite(page)) jumpToPage(page);
  }
});

setDateDefault();
