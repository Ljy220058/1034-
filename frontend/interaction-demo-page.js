(() => {
  "use strict";

  const workerSamples = [
    {
      id: "frontend-dev",
      name: "前端开发工程师",
      profile: "frontend-dev",
      status: "idle",
      label: "空闲",
      capacity: 92,
      focus: "HTML / CSS / 原生 JS",
      reason: "适合立即接手交互演示页、移动端布局和按钮状态补齐。",
    },
    {
      id: "backend-dev",
      name: "后端接口工程师",
      profile: "backend-dev",
      status: "warm",
      label: "轻载",
      capacity: 64,
      focus: "API 字段 / 数据聚合",
      reason: "适合处理任务创建接口、返回格式校验和错误码对齐。",
    },
    {
      id: "reviewer",
      name: "验收复核工程师",
      profile: "reviewer",
      status: "idle",
      label: "空闲",
      capacity: 86,
      focus: "交互验收 / 回归检查",
      reason: "适合在页面完成后检查 375 / 768 / 1280 三档显示。",
    },
  ];

  const cardSamples = [
    { id: "queued", title: "等待创建", status: "待领取", tone: "idle", progress: 22, detail: "表单校验通过后会进入队列预览。" },
    { id: "running", title: "正在执行", status: "进行中", tone: "warm", progress: 58, detail: "worker 已领取任务，正在同步工作区。" },
    { id: "blocked", title: "需要处理", status: "阻塞", tone: "hot", progress: 36, detail: "依赖未满足时显示错误提示与重试动作。" },
  ];

  const state = {
    loading: true,
    error: "",
    empty: false,
    selectedWorker: "frontend-dev",
    previewTitle: "待填写任务标题",
    submitCount: 0,
  };

  const refs = {};

  document.addEventListener("DOMContentLoaded", initInteractionDemo);

  function initInteractionDemo() {
    cacheDemoRefs();
    if (!refs.root) return;
    bindDemoEvents();
    renderDemoLoading();
    window.setTimeout(() => {
      state.loading = false;
      renderDemoAll();
    }, 520);
  }

  function cacheDemoRefs() {
    refs.root = document.querySelector("[data-interaction-demo]");
    refs.form = document.querySelector("[data-demo-form]");
    refs.title = document.querySelector("[data-demo-title]");
    refs.description = document.querySelector("[data-demo-description]");
    refs.assignee = document.querySelector("[data-demo-assignee]");
    refs.priority = document.querySelector("[data-demo-priority]");
    refs.workspace = document.querySelector("[data-demo-workspace]");
    refs.submit = document.querySelector("[data-demo-submit]");
    refs.reset = document.querySelector("[data-demo-reset]");
    refs.refresh = document.querySelector("[data-demo-refresh]");
    refs.empty = document.querySelector("[data-demo-empty]");
    refs.error = document.querySelector("[data-demo-error]");
    refs.workerList = document.querySelector("[data-demo-workers]");
    refs.cardList = document.querySelector("[data-demo-cards]");
    refs.state = document.querySelector("[data-demo-state]");
    refs.summary = document.querySelector("[data-demo-summary]");
    refs.preview = document.querySelector("[data-demo-preview]");
  }

  function bindDemoEvents() {
    refs.form?.addEventListener("submit", handleDemoSubmit);
    refs.reset?.addEventListener("click", handleDemoReset);
    refs.refresh?.addEventListener("click", handleDemoRefresh);
    refs.empty?.addEventListener("click", handleDemoEmpty);
    refs.error?.addEventListener("click", handleDemoError);
    refs.title?.addEventListener("input", renderDemoPreview);
    refs.description?.addEventListener("input", renderDemoPreview);
    refs.assignee?.addEventListener("change", handleAssigneeChange);
    refs.priority?.addEventListener("change", renderDemoPreview);
    refs.workspace?.addEventListener("change", renderDemoPreview);
    refs.workerList?.addEventListener("click", handleWorkerSelect);
    refs.cardList?.addEventListener("click", handleCardAction);
  }

  function handleDemoSubmit(event) {
    event.preventDefault();
    const errors = validateDemoForm();
    if (errors.length) {
      state.error = errors.join("；");
      renderDemoState("表单校验失败", state.error, "error");
      return;
    }
    refs.submit.disabled = true;
    refs.submit.setAttribute("aria-busy", "true");
    refs.submit.textContent = "创建中...";
    renderDemoState("创建中", "正在生成任务卡片预览，不会写入后端。", "loading");
    window.setTimeout(() => {
      state.submitCount += 1;
      state.error = "";
      refs.submit.disabled = false;
      refs.submit.removeAttribute("aria-busy");
      refs.submit.textContent = "创建预览任务";
      renderDemoState("已生成预览", `已生成 ${state.submitCount} 次本地任务预览，可继续修改表单。`, "success");
      renderDemoPreview();
    }, 620);
  }

  function handleDemoReset() {
    refs.form?.reset();
    state.selectedWorker = "frontend-dev";
    state.error = "";
    state.empty = false;
    renderDemoAll();
    renderDemoState("已重置", "表单已恢复默认值，可重新填写任务。", "success");
  }

  function handleDemoRefresh() {
    state.loading = true;
    state.error = "";
    state.empty = false;
    renderDemoLoading();
    window.setTimeout(() => {
      state.loading = false;
      renderDemoAll();
    }, 520);
  }

  function handleDemoEmpty() {
    state.loading = false;
    state.error = "";
    state.empty = true;
    renderDemoAll();
  }

  function handleDemoError() {
    state.loading = false;
    state.empty = false;
    state.error = "网络错误：任务队列暂时不可用，请点击重试。";
    renderDemoAll();
  }

  function handleAssigneeChange() {
    state.selectedWorker = refs.assignee?.value || "frontend-dev";
    renderWorkers();
    renderDemoPreview();
  }

  function handleWorkerSelect(event) {
    const button = event.target.closest("[data-demo-worker]");
    if (!button) return;
    state.selectedWorker = button.dataset.demoWorker || "frontend-dev";
    if (refs.assignee) refs.assignee.value = state.selectedWorker;
    renderWorkers();
    renderDemoPreview();
  }

  function handleCardAction(event) {
    const button = event.target.closest("[data-demo-card-action]");
    if (!button) return;
    renderDemoState("卡片已选中", `当前查看：${button.dataset.demoCardAction} 状态说明。`, "success");
  }

  function validateDemoForm() {
    const errors = [];
    if (!String(refs.title?.value || "").trim()) errors.push("请输入任务标题");
    if (!String(refs.description?.value || "").trim()) errors.push("请输入任务说明");
    if (!String(refs.assignee?.value || "").trim()) errors.push("请选择负责人");
    return errors;
  }

  function renderDemoLoading() {
    renderDemoState("加载中", "正在准备任务创建表单、空闲 worker 与状态卡片。", "loading");
    if (refs.workerList) refs.workerList.innerHTML = renderSkeletons(3);
    if (refs.cardList) refs.cardList.innerHTML = renderSkeletons(3);
    renderDemoSummary("同步中");
  }

  function renderDemoAll() {
    if (state.error) {
      renderDemoState("网络错误", state.error, "error");
    } else if (state.empty) {
      renderDemoState("暂无数据", "当前没有可展示的 worker 或任务卡片，点击刷新可恢复示例数据。", "empty");
    } else {
      renderDemoState("演示就绪", "所有交互均为本地预览，可直接验证 hover、active、disabled、loading、empty、error。", "success");
    }
    renderWorkers();
    renderCards();
    renderDemoPreview();
    renderDemoSummary();
  }

  function renderWorkers() {
    if (!refs.workerList) return;
    if (state.empty) {
      refs.workerList.innerHTML = renderEmptyPanel("暂无数据", "当前没有空闲 worker。", "刷新 worker");
      bindInlineRetry(refs.workerList);
      return;
    }
    if (state.error) {
      refs.workerList.innerHTML = renderEmptyPanel("暂无数据", "网络错误时保留重试入口。", "重试加载");
      bindInlineRetry(refs.workerList);
      return;
    }
    refs.workerList.innerHTML = workerSamples.map(renderWorkerCard).join("");
  }

  function renderCards() {
    if (!refs.cardList) return;
    if (state.empty) {
      refs.cardList.innerHTML = renderEmptyPanel("暂无数据", "当前没有任务卡片可预览。", "恢复示例");
      bindInlineRetry(refs.cardList);
      return;
    }
    if (state.error) {
      refs.cardList.innerHTML = renderErrorPanel();
      bindInlineRetry(refs.cardList);
      return;
    }
    refs.cardList.innerHTML = cardSamples.map(renderStatusCard).join("");
  }

  function renderWorkerCard(worker) {
    const isActive = worker.id === state.selectedWorker;
    return `
      <article class="demo-worker-card ${isActive ? "is-active" : ""}" data-worker-tone="${escapeHtml(worker.status)}">
        <header>
          <span class="demo-badge">${escapeHtml(worker.label)}</span>
          <h3>${escapeHtml(worker.name)}</h3>
          <p>${escapeHtml(worker.profile)}</p>
        </header>
        <p>${escapeHtml(worker.reason)}</p>
        <section class="demo-meter" aria-label="空闲容量">
          <span>空闲容量</span>
          <strong>${worker.capacity}%</strong>
          <span class="demo-meter__track"><i style="--demo-progress: ${worker.capacity}%"></i></span>
        </section>
        <button class="btn btn-secondary" type="button" data-demo-worker="${escapeHtml(worker.id)}">选为负责人</button>
      </article>
    `;
  }

  function renderStatusCard(card) {
    return `
      <article class="demo-status-card" data-card-tone="${escapeHtml(card.tone)}">
        <header>
          <span class="demo-badge">${escapeHtml(card.status)}</span>
          <h3>${escapeHtml(card.title)}</h3>
        </header>
        <p>${escapeHtml(card.detail)}</p>
        <section class="demo-meter" aria-label="状态进度">
          <span>状态进度</span>
          <strong>${card.progress}%</strong>
          <span class="demo-meter__track"><i style="--demo-progress: ${card.progress}%"></i></span>
        </section>
        <nav class="demo-card-actions" aria-label="卡片操作">
          <button class="btn btn-primary" type="button" data-demo-card-action="${escapeHtml(card.status)}">查看状态</button>
          <button class="btn btn-secondary" type="button" disabled>等待后端</button>
        </nav>
      </article>
    `;
  }

  function renderDemoPreview() {
    if (!refs.preview) return;
    const title = String(refs.title?.value || "").trim() || "待填写任务标题";
    const description = String(refs.description?.value || "").trim() || "填写任务说明后会在这里实时预览。";
    const assignee = refs.assignee?.value || state.selectedWorker;
    const priority = refs.priority?.value || "high";
    const workspace = refs.workspace?.value || "dir";
    refs.preview.innerHTML = `
      <article class="demo-preview-card">
        <span class="summary-chip">本地预览</span>
        <h3>${escapeHtml(title)}</h3>
        <p>${escapeHtml(description)}</p>
        <section class="demo-preview-card__chips" aria-label="任务字段预览">
          <span class="summary-chip">负责人 <strong>${escapeHtml(assignee)}</strong></span>
          <span class="summary-chip">优先级 <strong>${escapeHtml(priority)}</strong></span>
          <span class="summary-chip">工作区 <strong>${escapeHtml(workspace)}</strong></span>
          <span class="summary-chip">次数 <strong>${state.submitCount}</strong></span>
        </section>
      </article>
    `;
  }

  function renderDemoState(title, message, tone) {
    if (!refs.state) return;
    refs.state.className = `demo-state is-${tone}`;
    refs.state.innerHTML = `
      <section class="state-inline">
        ${tone === "loading" ? '<span class="spinner" aria-hidden="true"></span>' : ""}
        <h3>${escapeHtml(title)}</h3>
      </section>
      <p>${escapeHtml(message)}</p>
      ${tone === "error" || tone === "empty" ? '<button class="btn btn-primary" type="button" data-demo-inline-retry>重试</button>' : ""}
    `;
    refs.state.querySelector("[data-demo-inline-retry]")?.addEventListener("click", handleDemoRefresh);
  }

  function renderDemoSummary(text) {
    if (!refs.summary) return;
    if (text) {
      refs.summary.innerHTML = `<span class="summary-chip">${escapeHtml(text)}</span>`;
      return;
    }
    refs.summary.innerHTML = [
      `worker <strong>${state.empty ? 0 : workerSamples.length}</strong>`,
      `状态卡 <strong>${state.empty ? 0 : cardSamples.length}</strong>`,
      `已提交 <strong>${state.submitCount}</strong>`,
    ].map((item) => `<span class="summary-chip">${item}</span>`).join("");
  }

  function renderSkeletons(count) {
    return Array.from({ length: count }, () => '<article class="panel-skeleton" aria-hidden="true"></article>').join("");
  }

  function renderEmptyPanel(title, message, buttonText) {
    return `
      <article class="panel-empty demo-wide-state">
        <h3>${escapeHtml(title)}</h3>
        <p>${escapeHtml(message)}</p>
        <button class="btn btn-primary" type="button" data-demo-inline-retry>${escapeHtml(buttonText)}</button>
      </article>
    `;
  }

  function renderErrorPanel() {
    return `
      <article class="panel-state is-error demo-wide-state">
        <section class="state-inline"><h3>网络错误</h3></section>
        <p>后端不可用时展示重试按钮，不让页面空白。</p>
        <button class="btn btn-primary" type="button" data-demo-inline-retry>重试加载</button>
      </article>
    `;
  }

  function bindInlineRetry(target) {
    target.querySelector("[data-demo-inline-retry]")?.addEventListener("click", handleDemoRefresh);
  }

  function escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }
})();
