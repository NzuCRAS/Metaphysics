const copy = {
  languageLabel: "EN",
  eyebrow: "Eastern destiny reading for modern seekers",
  heroTitle: "Decode your BaZi birth chart with quiet precision.",
  heroText:
    "Share your birth details and receive a culturally rooted Four Pillars reading, designed for a global audience with a refined Taoist atmosphere.",
  startButton: "Start reading",
  privacyNote: "Private intake. No payment on this screen.",
  panelCaption: "Four pillars, five elements, one personal rhythm.",
  formEyebrow: "Birth information",
  formTitle: "Tell us where your life chart begins.",
  birthDateLabel: "Date of birth",
  birthTimeLabel: "Time of birth",
  yearLabel: "Year",
  monthLabel: "Month",
  dayLabel: "Day",
  hourLabel: "Hour",
  minuteLabel: "Minute",
  ampmLabel: "AM/PM",
  invalidDate: "Please enter a valid date of birth.",
  invalidTime: "Please enter a valid time of birth.",
  genderLabel: "Gender",
  genderPlaceholder: "Select gender",
  genderFemale: "Female",
  genderMale: "Male",
  birthPlaceLabel: "Place of birth",
  birthPlacePlaceholder: "City, country",
  calendarLabel: "Calendar",
  calendarSolar: "Solar / Gregorian",
  calendarLunar: "Lunar",
  consentText: "I confirm the information is accurate enough for a BaZi reading.",
  submitButton: "Reveal my chart",
  formNote: "Tip: if you do not know the exact birth minute, leave Minute blank. If the whole birth time is unknown, use 12:00 PM for a general reading.",
  summaryEyebrow: "Reading preview",
  summaryTitle: "Your intake is waiting.",
  summaryDate: "Date",
  summaryTime: "Time",
  summaryGender: "Gender",
  summaryPlace: "Birthplace",
  missing: "--",
  submitted: "Birth details received. Your BaZi reading can begin.",
  resultEyebrow: "Analysis report",
  resultTitle: "Reading result",
  copyReport: "Copy report",
  copied: "Copied",
  failed: "Failed",
  loadingText: "Consulting the AI master, please wait...",
  loadingNote: "AI master is thinking, it may take a long time.",
  errorPrefix: "Analysis failed",
  footerNote: "For entertainment and cultural study only. Please view the results rationally.",
};

const ALLOWED_REGIONS = ["sun", "luna", "dirt"];
function detectRegion() {
  const segment = window.location.pathname.split("/").filter(Boolean)[0] || "";
  return ALLOWED_REGIONS.includes(segment) ? segment : "global";
}
const region = detectRegion();

const API_BASE_URL =
  window.location.hostname === "localhost"
    ? "http://localhost:8000/api/v1"
    : "/api/v1";

const form = document.querySelector("#reading-form");
const toast = document.querySelector(".toast");
const summaries = document.querySelectorAll("[data-summary]");
let toastTimer;

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove("show"), 2200);
}

function translate() {
  document.documentElement.lang = "en";

  document.querySelectorAll("[data-i18n]").forEach((element) => {
    element.textContent = copy[element.dataset.i18n];
  });

  document.querySelectorAll("[data-i18n-placeholder]").forEach((element) => {
    element.placeholder = copy[element.dataset.i18nPlaceholder];
  });

  updateSummary();
}

function labelForSelect(name, value) {
  const option = form.elements[name].querySelector(`option[value="${value}"]`);
  return option?.textContent || copy.missing;
}

function updateSummary() {
  const data = new FormData(form);

  summaries.forEach((item) => {
    const key = item.dataset.summary;
    const value = data.get(key);
    item.textContent = value ? value : copy.missing;
  });

  const gender = data.get("gender");
  document.querySelector('[data-summary="gender"]').textContent = gender
    ? labelForSelect("gender", gender)
    : copy.missing;
}

const DATE_PARTS = ["year", "month", "day"];
const TIME_PARTS = ["hour", "minute", "ampm"];

function pad2(n) {
  return String(n).padStart(2, "0");
}

function daysInMonth(year, month) {
  return new Date(year, month, 0).getDate();
}

function normalizeAmPm(value) {
  const v = String(value || "").trim().toUpperCase();
  if (v === "AM" || v === "A") return "AM";
  if (v === "PM" || v === "P") return "PM";
  return "";
}

function validateDateParts() {
  const year = parseInt(form.elements.year.value, 10);
  const month = parseInt(form.elements.month.value, 10);
  const day = parseInt(form.elements.day.value, 10);

  if (!Number.isFinite(year) || year < 1900 || year > 2100) {
    return { ok: false, error: "Year must be between 1900 and 2100." };
  }
  if (!Number.isFinite(month) || month < 1 || month > 12) {
    return { ok: false, error: "Month must be between 1 and 12." };
  }
  if (!Number.isFinite(day) || day < 1 || day > daysInMonth(year, month)) {
    return { ok: false, error: "Day is invalid for the selected month." };
  }
  return { ok: true, value: `${year}-${pad2(month)}-${pad2(day)}` };
}

function validateTimeParts() {
  const hour = parseInt(form.elements.hour.value, 10);
  const ampm = normalizeAmPm(form.elements.ampm.value);
  const minuteRaw = form.elements.minute.value;
  const minute = minuteRaw === "" ? 0 : parseInt(minuteRaw, 10);

  if (!Number.isFinite(hour) || hour < 1 || hour > 12) {
    return { ok: false, error: "Hour must be between 1 and 12." };
  }
  if (!ampm) {
    return { ok: false, error: "Please select AM or PM." };
  }
  if (
    minuteRaw !== "" &&
    (!Number.isFinite(minute) || minute < 0 || minute > 59)
  ) {
    return { ok: false, error: "Minute must be between 0 and 59." };
  }
  const hour24 = (hour % 12) + (ampm === "PM" ? 12 : 0);
  return { ok: true, value: `${pad2(hour24)}:${pad2(minute)}` };
}

function clearFieldErrors() {
  DATE_PARTS.concat(TIME_PARTS).forEach((name) => {
    const el = form.elements[name];
    if (el) el.classList.remove("field-error");
  });
}

function markFieldError(names) {
  names.forEach((name) => {
    const el = form.elements[name];
    if (el) el.classList.add("field-error");
  });
}

function updateBirthDateTime() {
  const date = validateDateParts();
  const time = validateTimeParts();
  form.elements.birthDate.value = date.ok ? date.value : "";
  form.elements.birthTime.value = time.ok ? time.value : "";
  updateSummary();
}

form.addEventListener("input", (event) => {
  if (
    DATE_PARTS.includes(event.target.name) ||
    TIME_PARTS.includes(event.target.name)
  ) {
    updateBirthDateTime();
  } else {
    updateSummary();
  }
});
form.addEventListener("change", (event) => {
  if (
    DATE_PARTS.includes(event.target.name) ||
    TIME_PARTS.includes(event.target.name)
  ) {
    updateBirthDateTime();
  } else {
    updateSummary();
  }
});

// API helpers
function hideGlobalError() {
  const globalError = document.getElementById("global-error");
  if (globalError) globalError.classList.add("hidden");
}

function showGlobalError(message) {
  let globalError = document.getElementById("global-error");
  if (!globalError) {
    globalError = document.createElement("div");
    globalError.id = "global-error";
    globalError.className = "global-error hidden";
    document.body.appendChild(globalError);
  }
  globalError.textContent = message;
  globalError.classList.remove("hidden");
  console.error("Global Error:", message);
}

function setSubmitDisabled(disabled) {
  document
    .querySelectorAll('button[type="submit"]')
    .forEach((btn) => (btn.disabled = disabled));
}

function showLoading() {
  document.getElementById("result-section").classList.remove("hidden");
  document.getElementById("loading").classList.remove("hidden");
  document.getElementById("result-content").innerHTML = "";
  document.getElementById("error-message").classList.add("hidden");
}

function hideLoading() {
  document.getElementById("loading").classList.add("hidden");
}

function showResult(report) {
  hideLoading();
  if (typeof DOMPurify === "undefined") {
    const errorEl = document.getElementById("error-message");
    if (errorEl) {
      errorEl.textContent =
        "Security library failed to load. Please refresh the page.";
      errorEl.classList.remove("hidden");
    }
    return;
  }
  const rawHtml = marked.parse(report);
  const safeHtml = DOMPurify.sanitize(rawHtml);
  document.getElementById("result-content").innerHTML = safeHtml;
  document.getElementById("result-section").scrollIntoView({
    behavior: "smooth",
    block: "start",
  });
}

function showError(message) {
  hideLoading();
  const errorEl = document.getElementById("error-message");
  errorEl.textContent = message;
  errorEl.classList.remove("hidden");
  document.getElementById("result-section").scrollIntoView({
    behavior: "smooth",
    block: "start",
  });
  console.error("API Error:", message);
}

async function trackPageview() {
  try {
    await fetch(`${API_BASE_URL}/analytics/pageview`, {
      method: "POST",
      headers: { "X-Region": region },
    });
  } catch (err) {
    // Silent: analytics failure should not block the user.
    console.warn("Pageview tracking failed", err);
  }
}

async function streamBazi(data) {
  hideGlobalError();
  const response = await fetch(`${API_BASE_URL}/bazi/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Region": region,
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const result = await response.json().catch(() => ({}));
    throw new Error(result.detail || `${copy.errorPrefix}: ${response.status}`);
  }

  if (!response.body) {
    throw new Error("Streaming is not supported by this browser.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  let accumulatedReport = "";
  let receivedDone = false;

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // SSE 事件以 \n\n 分隔；兼容 \r\n\r\n
    const parts = buffer.split("\n\n");
    buffer = parts.pop() || "";

    for (const rawEvent of parts) {
      const event = parseSseEvent(rawEvent);
      if (!event) continue;

      if (event.type === "chunk") {
        accumulatedReport += event.delta || "";
        hideLoading();
        renderStreamingReport(accumulatedReport);
      } else if (event.type === "done") {
        receivedDone = true;
        return { report: accumulatedReport, metadata: event.metadata };
      } else if (event.type === "error") {
        throw new Error(event.message || copy.errorPrefix);
      }
    }
  }

  // 连接已关闭但没有收到 done：仍有内容就展示，否则提示被中断
  if (!receivedDone && accumulatedReport) {
    return { report: accumulatedReport, metadata: null };
  }
  if (!accumulatedReport) {
    throw new Error("The stream ended before any content was received.");
  }
  return { report: accumulatedReport, metadata: null };
}

function parseSseEvent(rawEvent) {
  const lines = rawEvent.split("\n").map((l) => l.replace(/\r/g, "").trim());
  let data = "";
  for (const line of lines) {
    if (line.startsWith("data:")) {
      const value = line.slice("data:".length).trim();
      data = value;
    }
  }
  if (!data || data === "[DONE]") return null;
  try {
    return JSON.parse(data);
  } catch (err) {
    console.warn("Failed to parse SSE event:", data);
    return null;
  }
}

function renderStreamingReport(rawMarkdown) {
  if (typeof DOMPurify === "undefined" || typeof marked === "undefined") return;
  const html = DOMPurify.sanitize(marked.parse(rawMarkdown));
  document.getElementById("result-content").innerHTML = html;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  hideGlobalError();
  clearFieldErrors();

  const date = validateDateParts();
  if (!date.ok) {
    markFieldError(DATE_PARTS);
    showGlobalError(date.error || copy.invalidDate);
    return;
  }

  const time = validateTimeParts();
  if (!time.ok) {
    markFieldError(TIME_PARTS);
    showGlobalError(time.error || copy.invalidTime);
    return;
  }

  form.elements.birthDate.value = date.value;
  form.elements.birthTime.value = time.value;
  updateSummary();

  const payload = {
    birth_date: date.value,
    birth_time: time.value,
    gender: form.elements.gender.value,
    birthplace: form.elements.birthPlace.value,
  };

  setSubmitDisabled(true);
  showLoading();

  try {
    const result = await streamBazi(payload);
    showResult(result.report);
    showToast(copy.submitted);
  } catch (err) {
    const msg =
      err.message || `${copy.errorPrefix}; please check your network and try again.`;
    showError(msg);
    showGlobalError(msg);
  } finally {
    setSubmitDisabled(false);
  }
});

// Copy report
const copyBtn = document.getElementById("copy-report");
if (copyBtn) {
  copyBtn.addEventListener("click", () => {
    const text = document.getElementById("result-content").innerText;
    navigator.clipboard.writeText(text).then(
      () => {
        const original = copyBtn.textContent;
        copyBtn.textContent = copy.copied;
        setTimeout(() => (copyBtn.textContent = original), 2000);
      },
      () => {
        const original = copyBtn.textContent;
        copyBtn.textContent = copy.failed;
        setTimeout(() => (copyBtn.textContent = original), 2000);
      }
    );
  });
}

trackPageview();
translate();
