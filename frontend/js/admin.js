const API_BASE_URL =
  window.location.hostname === "localhost"
    ? "http://localhost:8000/api/v1"
    : "/api/v1";

const tokenInput = document.getElementById("admin-token");
const dateInput = document.getElementById("report-date");
const summaryOutput = document.getElementById("summary-output");
const errorEl = document.getElementById("error-message");

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

function getInputs() {
  const token = tokenInput.value.trim();
  const date = dateInput.value;
  if (!token || !date) {
    showError("Please enter both admin token and date.");
    return null;
  }
  return { token, date };
}

document.getElementById("load-summary").addEventListener("click", async () => {
  hideError();
  const inputs = getInputs();
  if (!inputs) return;

  try {
    const res = await fetch(
      `${API_BASE_URL}/admin/traffic-summary?date=${inputs.date}&token=${encodeURIComponent(inputs.token)}`
    );
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || `HTTP ${res.status}`);
    }
    const data = await res.json();
    summaryOutput.textContent = JSON.stringify(data, null, 2);
  } catch (err) {
    showError(err.message || "Failed to load summary.");
  }
});

document.getElementById("download-report").addEventListener("click", async () => {
  hideError();
  const inputs = getInputs();
  if (!inputs) return;

  try {
    const res = await fetch(
      `${API_BASE_URL}/admin/traffic-report?date=${inputs.date}&token=${encodeURIComponent(inputs.token)}`
    );
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
    showError(err.message || "Failed to download report.");
  }
});

setDateDefault();
