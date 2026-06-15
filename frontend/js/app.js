const copy = {
  en: {
    languageLabel: "中文",
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
  },
  zh: {
    languageLabel: "EN",
    eyebrow: "给现代探索者的东方命理咨询",
    heroTitle: "以安静而精准的方式解读你的八字命盘。",
    heroText: "填写出生信息，即可进入一份融合四柱、五行与道家气质的命理咨询体验。",
    startButton: "开始填写",
    privacyNote: "这里只收集资料，当前页面不涉及付款。",
    panelCaption: "四柱、五行，与一个人的生命节律。",
    formEyebrow: "出生资料",
    formTitle: "告诉我们，你的命盘从哪里开始。",
    birthDateLabel: "出生年月日",
    birthTimeLabel: "出生时间",
    genderLabel: "性别",
    genderPlaceholder: "请选择",
    genderFemale: "女",
    genderMale: "男",
    birthPlaceLabel: "出生地",
    birthPlacePlaceholder: "城市，国家",
    calendarLabel: "历法",
    calendarSolar: "公历 / 阳历",
    calendarLunar: "农历 / 阴历",
    consentText: "我确认填写的信息足够准确，可用于八字解读。",
    submitButton: "查看我的命盘",
    formNote: "提示：如果不知道准确出生时间，可以先留空，我们仍可准备基础解读。",
    summaryEyebrow: "资料预览",
    summaryTitle: "你的资料正在等待填写。",
    summaryDate: "日期",
    summaryTime: "时间",
    summaryGender: "性别",
    summaryPlace: "出生地",
    missing: "--",
    submitted: "出生资料已记录，可以开始八字解读。",
    resultEyebrow: "分析报告",
    resultTitle: "八字命理分析",
    copyReport: "复制全文",
    copied: "已复制",
    failed: "复制失败",
    loadingText: "正在请教 AI 命理大师，请稍候...",
    errorPrefix: "分析失败",
    footerNote: "本应用仅供娱乐与文化研究，命理结果仅供参考，请理性看待。",
  },
};

const API_BASE_URL = window.location.hostname === 'localhost' ? 'http://localhost:8000/api/v1' : '/api/v1';

const form = document.querySelector("#reading-form");
const toast = document.querySelector(".toast");
const languageButton = document.querySelector("[data-language-toggle]");
const summaries = document.querySelectorAll("[data-summary]");
let language = "zh";
let toastTimer;

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove("show"), 2200);
}

function translate() {
  const dictionary = copy[language];
  document.documentElement.lang = language === "zh" ? "zh-CN" : "en";

  document.querySelectorAll("[data-i18n]").forEach((element) => {
    element.textContent = dictionary[element.dataset.i18n];
  });

  document.querySelectorAll("[data-i18n-placeholder]").forEach((element) => {
    element.placeholder = dictionary[element.dataset.i18nPlaceholder];
  });

  updateSummary();
}

function labelForSelect(name, value) {
  const option = form.elements[name].querySelector(`option[value="${value}"]`);
  return option?.textContent || copy[language].missing;
}

function updateSummary() {
  const data = new FormData(form);

  summaries.forEach((item) => {
    const key = item.dataset.summary;
    const value = data.get(key);
    item.textContent = value ? value : copy[language].missing;
  });

  const gender = data.get("gender");
  document.querySelector('[data-summary="gender"]').textContent = gender
    ? labelForSelect("gender", gender)
    : copy[language].missing;
}

languageButton.addEventListener("click", () => {
  language = language === "en" ? "zh" : "en";
  translate();
});

form.addEventListener("input", updateSummary);
form.addEventListener("change", updateSummary);

// API helpers
function hideGlobalError() {
  const globalError = document.getElementById('global-error');
  if (globalError) globalError.classList.add('hidden');
}

function showGlobalError(message) {
  let globalError = document.getElementById('global-error');
  if (!globalError) {
    globalError = document.createElement('div');
    globalError.id = 'global-error';
    globalError.className = 'global-error hidden';
    document.body.appendChild(globalError);
  }
  globalError.textContent = message;
  globalError.classList.remove('hidden');
  console.error('Global Error:', message);
}

function setSubmitDisabled(disabled) {
  document.querySelectorAll('button[type="submit"]').forEach(btn => btn.disabled = disabled);
}

function showLoading() {
  document.getElementById('result-section').classList.remove('hidden');
  document.getElementById('loading').classList.remove('hidden');
  document.getElementById('result-content').innerHTML = '';
  document.getElementById('error-message').classList.add('hidden');
}

function hideLoading() {
  document.getElementById('loading').classList.add('hidden');
}

function showResult(report) {
  hideLoading();
  if (typeof DOMPurify === 'undefined') {
    const errorEl = document.getElementById('error-message');
    if (errorEl) {
      errorEl.textContent = 'Security library failed to load. Please refresh the page.';
      errorEl.classList.remove('hidden');
    }
    return;
  }
  const rawHtml = marked.parse(report);
  const safeHtml = DOMPurify.sanitize(rawHtml);
  document.getElementById('result-content').innerHTML = safeHtml;
  document.getElementById('result-section').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function showError(message) {
  hideLoading();
  const errorEl = document.getElementById('error-message');
  errorEl.textContent = message;
  errorEl.classList.remove('hidden');
  document.getElementById('result-section').scrollIntoView({ behavior: 'smooth', block: 'start' });
  console.error('API Error:', message);
}

async function postBazi(data) {
  hideGlobalError();
  const response = await fetch(`${API_BASE_URL}/bazi`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(result.detail || `${copy[language].errorPrefix}: ${response.status}`);
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
    showToast(copy[language].submitted);
  } catch (err) {
    const msg = err.message || `${copy[language].errorPrefix}，请检查网络或稍后重试。`;
    showError(msg);
    showGlobalError(msg);
  } finally {
    setSubmitDisabled(false);
  }
});

// Copy report
const copyBtn = document.getElementById('copy-report');
if (copyBtn) {
  copyBtn.addEventListener('click', () => {
    const text = document.getElementById('result-content').innerText;
    navigator.clipboard.writeText(text).then(() => {
      const original = copyBtn.textContent;
      copyBtn.textContent = copy[language].copied;
      setTimeout(() => copyBtn.textContent = original, 2000);
    }).catch(() => {
      const original = copyBtn.textContent;
      copyBtn.textContent = copy[language].failed;
      setTimeout(() => copyBtn.textContent = original, 2000);
    });
  });
}

translate();
