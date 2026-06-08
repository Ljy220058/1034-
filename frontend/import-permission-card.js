(()=>{
  "use strict";

  const STORAGE_KEY = "1034.import-permission.records.v1";
  const DEFAULT_FORM = {
    title: "",
    summary: "",
    priority: "normal",
    tags: "",
  };

  const scenarios = {
    ready: {
      key: "ready",
      title: "导入前说明已准备好",
      summary: "支持填写创意标题、摘要、优先级和标签，并把记录写入本地数据文件。",
      stateTitle: "等待提交",
      stateText: "填写完整后即可保存到本地记录，列表会在下方即时更新。",
      primary: "保存记录",
      secondary: "清空表单",
      tone: "",
      detailTitle: "写入说明",
      checklistTitle: "字段与存储说明",
      checklist: [
        "来源：页面表单输入。",
        "读取字段：创意标题、摘要、优先级、标签。",
        "保存位置：浏览器本地数据文件（localStorage）。",
        "撤销入口：可随时清空表单并撤回未保存内容。"
      ],
    },
    loading: {
      key: "loading",
      title: "正在保存记录",
      summary: "模拟保存过程中的加载态，按钮会暂时置灰。",
      stateTitle: "保存中",
      stateText: "正在把当前表单写入本地数据文件，请稍候。",
      primary: "保存中",
      secondary: "稍后再试",
      tone: "",
      detailTitle: "保存过程",
      checklistTitle: "处理中会发生什么",
      checklist: [
        "先校验必填字段。",
        "再写入本地数据文件。",
        "写入完成后刷新列表。",
        "如校验失败会回到错误态。"
      ],
    },
    error: {
      key: "error",
      title: "表单校验失败",
      summary: "当标题、摘要、优先级或标签缺失时，展示错误状态并提示重试。",
      stateTitle: "提交失败",
      stateText: "请先修正表单内容，再点击重试按钮。",
      primary: "重试保存",
      secondary: "返回编辑",
      tone: "is-error",
      detailTitle: "错误提示",
      checklistTitle: "校验规则",
      checklist: [
        "标题至少 4 个字。",
        "摘要至少 10 个字。",
        "优先级必须从下拉中选择。",
        "标签至少输入 1 个。"
      ],
    }
  };

  const priorityOptions = {
    high: { label: "高", tone: "creative-priority--high" },
    normal: { label: "中", tone: "creative-priority--medium" },
    low: { label: "低", tone: "creative-priority--low" },
  };

  const errorCards = [
    { code: "400", tone: "is-warning", title: "参数有误", text: "请求字段或内容格式不正确，请检查标题、摘要和标签。", action: "返回检查字段" },
    { code: "401", tone: "is-info", title: "未登录", text: "当前会话失效，请先登录后再继续保存。", action: "去登录" },
    { code: "403", tone: "is-error", title: "权限不足", text: "当前账号没有写入权限，请联系管理员处理。", action: "联系管理员" },
    { code: "422", tone: "is-success", title: "校验失败", text: "记录已读取，但字段内容未通过校验，请修正后重试。", action: "重新提交" },
  ];

  const state = {
    current: "ready",
    loading: true,
    records: [],
    error: "",
    draft: { ...DEFAULT_FORM },
  };

  const dom = {};

  document.addEventListener("DOMContentLoaded", initImportPermission);

  function initImportPermission() {
    dom.root = document.querySelector("[data-import-permission]");
    if (!dom.root) return;
    dom.form = dom.root.querySelector("[data-import-permission-form]");
    dom.title = dom.root.querySelector("[data-import-permission-title]");
    dom.summary = dom.root.querySelector("[data-import-permission-summary-input]");
    dom.priority = dom.root.querySelector("[data-import-permission-priority]");
    dom.tags = dom.root.querySelector("[data-import-permission-tags]");
    dom.submit = dom.root.querySelector("[data-import-permission-submit]");
    dom.reset = dom.root.querySelector("[data-import-permission-reset]");
    dom.retry = dom.root.querySelector("[data-import-permission-retry]");
    dom.state = dom.root.querySelector("[data-import-permission-state]");
    dom.summaryChip = dom.root.querySelector("[data-import-permission-summary]");
    dom.list = dom.root.querySelector("[data-import-permission-list]");
    dom.count = dom.root.querySelector("[data-import-permission-count]");
    dom.empty = dom.root.querySelector("[data-import-permission-empty]");
    dom.errors = dom.root.querySelector("[data-import-permission-errors]");
    dom.actions = Array.from(dom.root.querySelectorAll("[data-import-permission-mode]"));

    restoreState();
    bindEvents();
    renderAll();
    window.setTimeout(() => {
      state.loading = false;
      renderAll();
    }, 260);
  }

  function restoreState() {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
      if (saved && typeof saved === "object") {
        state.records = Array.isArray(saved.records) ? saved.records : [];
        state.draft = { ...DEFAULT_FORM, ...(saved.draft || {}) };
      }
    } catch {
      state.error = "本地数据读取失败，将使用空白状态继续。";
      state.current = "error";
    }
    syncFormFields();
  }

  function bindEvents() {
    dom.form?.addEventListener("submit", handleSubmit);
    dom.reset?.addEventListener("click", handleReset);
    dom.retry?.addEventListener("click", handleRetry);
    dom.title?.addEventListener("input", handleDraftChange);
    dom.summary?.addEventListener("input", handleDraftChange);
    dom.priority?.addEventListener("change", handleDraftChange);
    dom.tags?.addEventListener("input", handleDraftChange);
    dom.actions.forEach((button) => {
      button.addEventListener("click", () => handleModeSwitch(button.dataset.importPermissionMode || "ready"));
    });
  }

  function handleModeSwitch(key) {
    if (!scenarios[key]) return;
    state.current = key;
    if (key !== "error") state.error = "";
    renderAll();
  }

  function handleDraftChange() {
    state.draft = {
      title: String(dom.title?.value || "").trim(),
      summary: String(dom.summary?.value || "").trim(),
      priority: String(dom.priority?.value || "normal").trim(),
      tags: String(dom.tags?.value || "").trim(),
    };
    persistState();
    renderSummary();
  }

  function validateForm() {
    if (!state.draft.title || state.draft.title.length < 4) return "请至少填写 4 个字的创意标题。";
    if (!state.draft.summary || state.draft.summary.length < 10) return "请至少填写 10 个字的摘要。";
    if (!state.draft.priority) return "请选择优先级。";
    if (!state.draft.tags) return "请输入至少一个标签。";
    return "";
  }

  function handleSubmit(event) {
    event.preventDefault();
    const validationError = validateForm();
    if (validationError) {
      state.current = "error";
      state.error = validationError;
      renderAll();
      return;
    }
    state.current = "loading";
    state.error = "";
    renderAll();
    window.setTimeout(() => {
      const record = {
        id: `local-${Date.now()}`,
        title: state.draft.title,
        summary: state.draft.summary,
        priority: state.draft.priority,
        tags: state.draft.tags.split(/[，,\s]+/).filter(Boolean),
        createdAt: new Date().toLocaleString("zh-CN", { hour12: false }),
      };
      state.records = [record, ...state.records].slice(0, 8);
      state.current = "ready";
      state.error = "";
      persistState();
      renderAll();
    }, 780);
  }

  function handleReset() {
    state.draft = { ...DEFAULT_FORM };
    state.current = "ready";
    state.error = "";
    syncFormFields();
    persistState();
    renderAll();
  }

  function handleRetry() {
    if (state.current !== "error") return;
    state.current = "ready";
    state.error = "";
    renderAll();
  }

  function syncFormFields() {
    if (dom.title) dom.title.value = state.draft.title;
    if (dom.summary) dom.summary.value = state.draft.summary;
    if (dom.priority) dom.priority.value = state.draft.priority || "normal";
    if (dom.tags) dom.tags.value = state.draft.tags;
  }

  function persistState() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ draft: state.draft, records: state.records }));
    } catch {
      // 本地存储不可用时静默降级
    }
  }

  function renderAll() {
    renderHeaderSummary();
    renderState();
    renderFormButtons();
    renderList();
    renderErrors();
    renderSummary();
  }

  function renderHeaderSummary() {
    const scenario = scenarios[state.current] || scenarios.ready;
    if (dom.summaryChip) {
      dom.summaryChip.innerHTML = `<span class="summary-chip">${escapeHtml(scenario.title)}</span><span class="summary-chip">${state.records.length ? `已有 ${state.records.length} 条记录` : '暂无数据'}</span>`;
    }
  }

  function renderSummary() {
    const count = state.records.length;
    const priorityLabel = priorityOptions[state.draft.priority || "normal"]?.label || "中";
    const tags = state.draft.tags ? state.draft.tags.split(/[，,\s]+/).filter(Boolean).slice(0, 3).join(" · ") : "暂无标签";
    const summaryNodes = [
      `<article class="import-permission__stat"><span>记录数量</span><strong>${count}</strong></article>`,
      `<article class="import-permission__stat"><span>当前优先级</span><strong>${escapeHtml(priorityLabel)}</strong></article>`,
      `<article class="import-permission__stat"><span>标签预览</span><strong>${escapeHtml(tags)}</strong></article>`,
    ];
    const metrics = dom.root.querySelector("[data-import-permission-metrics]");
    if (metrics) metrics.innerHTML = summaryNodes.join("");
    if (dom.count) dom.count.textContent = String(state.records.length);
  }

  function renderState() {
    const scenario = scenarios[state.current] || scenarios.ready;
    if (state.loading) {
      dom.state.className = "import-permission__state";
      dom.state.innerHTML = '<div class="activity-state__inline"><span class="spinner" aria-hidden="true"></span><h3>加载中</h3></div><p>正在准备导入权限表单。</p>';
      setButtonsDisabled(true);
      return;
    }
    setButtonsDisabled(false);
    dom.state.className = `import-permission__state ${scenario.tone || ""}`.trim();
    dom.state.innerHTML = `
      <div class="activity-state__inline">
        ${state.current === "error" ? "" : '<span class="spinner" aria-hidden="true"></span>'}
        <h3>${escapeHtml(scenario.stateTitle)}</h3>
      </div>
      <p>${escapeHtml(state.current === "error" ? state.error || scenario.stateText : scenario.stateText)}</p>
      <div class="import-permission__actions">
        <button class="btn btn-primary" type="button" data-import-permission-retry>${escapeHtml(scenario.primary)}</button>
        <button class="btn btn-secondary" type="button" data-import-permission-reset>${escapeHtml(scenario.secondary)}</button>
      </div>
    `;
    dom.state.querySelector('[data-import-permission-retry]')?.addEventListener('click', handleRetry);
    dom.state.querySelector('[data-import-permission-reset]')?.addEventListener('click', handleReset);
  }

  function setButtonsDisabled(disabled) {
    if (dom.submit) dom.submit.disabled = disabled;
    if (dom.reset) dom.reset.disabled = disabled;
    dom.actions.forEach((button) => {
      button.disabled = disabled;
    });
  }

  function renderFormButtons() {
    if (!dom.submit || !dom.reset) return;
    const disabled = state.loading;
    dom.submit.disabled = disabled;
    dom.reset.disabled = disabled;
    dom.submit.textContent = state.current === "loading" ? "保存中" : "保存记录";
  }

  function renderList() {
    if (!dom.list) return;
    if (!state.records.length) {
      dom.list.innerHTML = '<article class="creative-empty import-permission__empty"><h3>暂无数据</h3><p>请先填写表单并保存，记录会显示在这里。</p></article>';
      if (dom.empty) dom.empty.hidden = false;
      return;
    }
    if (dom.empty) dom.empty.hidden = true;
    dom.list.innerHTML = state.records.map((item) => {
      const priorityView = priorityOptions[item.priority || "normal"] || priorityOptions.normal;
      return `
        <article class="creative-card import-permission__record" data-status="${escapeHtml(item.priority || "normal")}">
          <div class="creative-card__header">
            <div>
              <span class="creative-priority ${priorityView.tone}">${priorityView.label}</span>
              <h3>${escapeHtml(item.title)}</h3>
            </div>
            <span class="creative-status">${escapeHtml(item.createdAt)}</span>
          </div>
          <p>${escapeHtml(item.summary)}</p>
          <dl class="creative-card__meta">
            <div><dt>标签</dt><dd>${escapeHtml((item.tags || []).join(" · ") || "暂无标签")}</dd></div>
            <div><dt>写入位置</dt><dd>本地数据文件</dd></div>
          </dl>
        </article>
      `;
    }).join("");
  }

  function renderErrors() {
    if (!dom.errors) return;
    dom.errors.innerHTML = errorCards.map((card) => `
      <article class="import-permission__error-card ${card.tone}">
        <span class="summary-chip">HTTP ${card.code}</span>
        <h4>${card.code} · ${card.title}</h4>
        <p>${card.text}</p>
        <nav class="import-permission__actions" aria-label="${card.code} 错误操作">
          <button class="btn btn-secondary" type="button">${card.action}</button>
          <button class="btn btn-primary" type="button" data-import-permission-retry-list>重试导入</button>
        </nav>
      </article>
    `).join("");
    dom.errors.querySelectorAll('[data-import-permission-retry-list]').forEach((button) => {
      button.addEventListener('click', handleRetry);
    });
  }

  function escapeHtml(value) {
    return String(value)
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#39;');
  }
})();
