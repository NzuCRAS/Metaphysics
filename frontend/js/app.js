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
  formNote: "Tip: if you do not know the exact birth time, leave it blank and we can still prepare a general reading.",
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
  errorPrefix: "Analysis failed",
  footerNote: "For entertainment and cultural study only. Please view the results rationally.",
};

const ALLOWED_REGIONS = ["cn", "eu", "us"];
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

form.addEventListener("input", updateSummary);
form.addEventListener("change", updateSummary);

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

async function postBazi(data) {
  hideGlobalError();
  const response = await fetch(`${API_BASE_URL}/bazi`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Region": region,
    },
    body: JSON.stringify(data),
  });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(result.detail || `${copy.errorPrefix}: ${response.status}`);
  }
  return result;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!form.reportValidity()) return;

  const payload = {
    birth_date: form.elements.birthDate.value,
    birth_time: form.elements.birthTime.value,
    gender: form.elements.gender.value,
    birthplace: form.elements.birthPlace.value,
  };

  setSubmitDisabled(true);
  showLoading();

  try {
    const result = await postBazi(payload);
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
