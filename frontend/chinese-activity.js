(()=>{
  "use strict";

  const STORAGE_KEY = "1034.chinese-activity.form.v1";
  const THEME_KEY = "1034.chinese-activity.theme.v1";
  const DEFAULT_FORM = {
    title: "",
    summary: "",
    tags: "",
  };

  const state = {
    mode: "idle",
    error: "",
    theme: "dark",
    draft: { ...DEFAULT_FORM },
    records: [],
  };

  const refs = {};

  document.addEventListener("DOMContentLoaded", initChineseActivityPage);

  function initChineseActivityPage() {
    cacheChineseActivityRefs();
    if (!refs.root) return;
    restoreChineseActivityState();
    bindChineseActivityEvents();
    renderChineseActivityTheme();
    renderChineseActivityFormState();
    renderChineseActivityList();
    renderChineseActivitySummary();
  }

  function cacheChineseActivityRefs() {
    refs.root = document.querySelector("[data-chinese-activity]");
    if (!refs.root) return;
    refs.scrollButton = refs.root.querySelector("[data-chinese-activity-scroll]");
    refs.themeToggle = refs.root.querySelector("[data-theme-toggle]");
    refs.form = refs.root.querySelector("[data-chinese-activity-form]");
    refs.title = refs.root.querySelector("#activity-name");
    refs.summary = refs.root.querySelector("#activity-note");
    refs.tags = refs.root.querySelector("#activity-tags");
    refs.submit = refs.root.querySelector("[data-chinese-activity-submit]");
    refs.reset = refs.root.querySelector("[data-chinese-activity-reset]");
    refs.state = refs.root.querySelector("[data-chinese-activity-state]");
    refs.list = refs.root.querySelector("[data-chinese-activity-list]");
    refs.badge = refs.root.querySelector("[data-chinese-activity-badge]");
    refs.participants = refs.root.querySelector("[data-chinese-activity-participants]");
    refs.rate = refs.root.querySelector("[data-chinese-activity-rate]");
    refs.deadline = refs.root.querySelector("[data-chinese-activity-deadline]");
    refs.filter = refs.root.querySelector("[data-chinese-activity-filter]");
    refs.count = refs.root.querySelector("[data-chinese-activity-count]");
  }

  function bindChineseActivityEvents() {
    refs.scrollButton?.addEventListener("click", handleChineseActivityScroll);
    refs.themeToggle?.addEventListener("click", handleThemeToggle);
    refs.form?.addEventListener("submit", handleFormSubmit);
    refs.reset?.addEventListener("click", handleFormReset);
    refs.title?.addEventListener("input", handleDraftChange);
    refs.summary?.addEventListener("input", handleDraftChange);
    refs.tags?.addEventListener("input", handleDraftChange);
    refs.filter?.addEventListener("input", renderChineseActivityList);
  }

  function restoreChineseActivityState() {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
      if (saved && typeof saved === "object") {
        state.draft = { ...DEFAULT_FORM, ...(saved.draft || {}) };
        state.records = Array.isArray(saved.records) ? saved.records : [];
      }
      state.theme = localStorage.getItem(THEME_KEY) || "dark";
    } catch {
      state.mode = "error";
      state.error = "本地草稿恢复失败，请手动重新输入。";
    }
    syncFormFields();
  }

  function syncFormFields() {
    if (refs.title) refs.title.value = state.draft.title;
    if (refs.summary) refs.summary.value = state.draft.summary;
    if (refs.tags) refs.tags.value = state.draft.tags;
  }

  function handleChineseActivityScroll() {
    document.getElementById("chinese-activity-form-title")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function handleThemeToggle() {
    state.theme = state.theme === "dark" ? "light" : "dark";
    localStorage.setItem(THEME_KEY, state.theme);
    renderChineseActivityTheme();
  }

  function renderChineseActivityTheme() {
    document.documentElement.dataset.theme = state.theme;
    if (refs.themeToggle) {
      const isDark = state.theme === "dark";
      refs.themeToggle.setAttribute("aria-pressed", String(!isDark));
      refs.themeToggle.textContent = isDark ? "切换浅色主题" : "切换深色主题";
    }
    if (refs.badge) refs.badge.textContent = state.theme === "dark" ? "深色主题" : "浅色主题";
  }

  function handleDraftChange() {
    state.draft = {
      title: refs.title?.value.trim() || "",
      summary: refs.summary?.value.trim() || "",
      tags: refs.tags?.value.trim() || "",
    };
    persistChineseActivityState();
    renderChineseActivitySummary();
  }

  function validateChineseActivityForm() {
    if (!state.draft.title) return "请先填写创意标题。";
    if (state.draft.title.length < 4) return "标题至少填写 4 个字。";
    if (!state.draft.summary) return "请补充一句活动摘要。";
    if (state.draft.summary.length < 10) return "摘要至少需要 10 个字。";
    if (!state.draft.tags) return "请输入至少一个标签。";
    return "";
  }

  function handleFormSubmit(event) {
    event.preventDefault();
    const validationError = validateChineseActivityForm();
    if (validationError) {
      state.mode = "error";
      state.error = validationError;
      renderChineseActivityFormState();
      return;
    }
    state.mode = "loading";
    state.error = "";
    renderChineseActivityFormState();
    setTimeout(() => {
      const record = {
        id: `local-${Date.now()}`,
        title: state.draft.title,
        summary: state.draft.summary,
        tags: state.draft.tags.split(/[，,\s]+/).filter(Boolean),
        createdAt: new Date().toLocaleString("zh-CN", { hour12: false }),
      };
      state.records = [record, ...state.records].slice(0, 8);
      state.mode = "success";
      state.error = "";
      persistChineseActivityState();
      renderChineseActivityList();
      renderChineseActivityFormState();
      renderChineseActivitySummary();
    }, 900);
  }

  function handleFormReset() {
    state.draft = { ...DEFAULT_FORM };
    state.mode = "idle";
    state.error = "";
    syncFormFields();
    persistChineseActivityState();
    renderChineseActivityFormState();
    renderChineseActivitySummary();
  }

  function persistChineseActivityState() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ draft: state.draft, records: state.records }));
  }

  function renderChineseActivityFormState() {
    if (!refs.state) return;
    if (state.mode === "loading") {
      refs.state.className = "chinese-activity__form-status is-loading";
      refs.state.innerHTML = '<div class="activity-state__inline"><span class="spinner" aria-hidden="true"></span><h3>正在提交</h3></div><p>正在把创意写入本地草稿。</p>';
      toggleChineseActivityButtons(true);
      return;
    }
    toggleChineseActivityButtons(false);
    if (state.mode === "error") {
      refs.state.className = "chinese-activity__form-status is-error";
      refs.state.innerHTML = `<div class="activity-state__inline"><span class="spinner" aria-hidden="true"></span><h3>提交失败</h3></div><p>${escapeChineseActivityHtml(state.error || "表单校验失败")}</p>`;
      return;
    }
    if (state.mode === "success") {
      refs.state.className = "chinese-activity__form-status is-success";
      refs.state.innerHTML = '<div class="activity-state__inline"><span class="spinner" aria-hidden="true"></span><h3>已保存</h3></div><p>创意记录已写入本地数据文件。</p>';
      return;
    }
    refs.state.className = "chinese-activity__form-status";
    refs.state.innerHTML = '<div class="activity-state__inline"><span class="spinner" aria-hidden="true"></span><h3>等待提交</h3></div><p>填写标题、摘要和标签后即可保存。</p>';
  }

  function toggleChineseActivityButtons(disabled) {
    if (refs.submit) refs.submit.disabled = disabled;
    if (refs.reset) refs.reset.disabled = disabled;
  }

  function renderChineseActivitySummary() {
    const count = state.records.length;
    if (refs.participants) refs.participants.textContent = String(120 + count * 3);
    if (refs.rate) refs.rate.textContent = `${88 + count}%`;
    if (refs.deadline) refs.deadline.textContent = count ? "今晚 22:00" : "今晚 20:00";
  }

  function renderChineseActivityList() {
    if (!refs.list) return;
    const keyword = String(refs.filter?.value || "").trim().toLowerCase();
    const filtered = state.records.filter((item) => {
      if (!keyword) return true;
      return [item.title, item.summary, ...(item.tags || [])].join(" ").toLowerCase().includes(keyword);
    });
    if (refs.count) refs.count.textContent = String(filtered.length);
    if (!filtered.length) {
      refs.list.innerHTML = `
        <article class="creative-empty chinese-activity__empty">
          <h3>暂无数据</h3>
          <p>${state.records.length ? "没有符合筛选条件的记录。" : "还没有保存过任何创意记录。"}</p>
        </article>
      `;
      return;
    }
    refs.list.innerHTML = filtered.map((item) => `
      <article class="creative-card chinese-activity__card" data-status="${escapeChineseActivityHtml(item.priority || "doing")}">
        <div class="creative-card__header">
          <div>
            <span class="creative-priority creative-priority--medium">本地记录</span>
            <h3>${escapeChineseActivityHtml(item.title)}</h3>
          </div>
          <span class="creative-status">${escapeChineseActivityHtml(item.createdAt)}</span>
        </div>
        <p>${escapeChineseActivityHtml(item.summary)}</p>
        <dl class="creative-card__meta">
          <div><dt>标签</dt><dd>${escapeChineseActivityHtml((item.tags || []).join(" · ") || "暂无标签")}</dd></div>
          <div><dt>写入位置</dt><dd>本地数据文件</dd></div>
        </dl>
      </article>
    `).join("");
  }

  function escapeChineseActivityHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }
})();
