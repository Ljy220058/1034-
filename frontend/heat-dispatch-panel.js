(()=>{
  "use strict";

  const API_BASE = "/api/v1";
  const STORAGE_KEY = "1034.dispatch-panel.filters.v1";
  const AUTH_TOKEN_KEYS = ["access_token", "accessToken", "token", "authToken", "workerAccessToken"];

  const WORKERS = [
    {
      id: "frontend-dev",
      name: "frontend-dev",
      title: "前端空闲 worker",
      availability: "空闲",
      heat: "idle",
      priority: "高",
      score: 96,
      load: 18,
      taskTypes: ["页面搭建", "响应式布局", "交互补全", "状态处理"],
      suggestion: "适合承担卡片布局、筛选联动和移动端细节优化。",
    },
    {
      id: "backend-dev",
      name: "backend-dev",
      title: "后端协作 worker",
      availability: "忙碌",
      heat: "warm",
      priority: "中",
      score: 74,
      load: 42,
      taskTypes: ["接口对齐", "字段校验", "数据聚合", "持久化"],
      suggestion: "适合处理接口返回格式、聚合字段与数据一致性。",
    },
    {
      id: "devops-engineer",
      name: "devops-engineer",
      title: "运维调度 worker",
      availability: "离线",
      heat: "hot",
      priority: "低",
      score: 58,
      load: 68,
      taskTypes: ["部署检查", "服务探活", "日志巡检", "环境配置"],
      suggestion: "适合接收需要环境检查与发布保障的任务。",
    },
  ];

  const state = {
    loading: true,
    error: "",
    tasks: [],
    workers: structuredClone(WORKERS),
    selectedWorker: "frontend-dev",
    search: "",
    scope: "all",
  };

  const refs = {};

  document.addEventListener("DOMContentLoaded", initApp);

  function initApp() {
    cacheRefs();
    bindEvents();
    restoreState();
    loadDispatchData();
  }

  function cacheRefs() {
    refs.summary = document.querySelector("[data-dispatch-summary]");
    refs.state = document.querySelector("[data-dispatch-state]");
    refs.grid = document.querySelector("[data-worker-grid]");
    refs.search = document.querySelector("[data-dispatch-search]");
    refs.scope = document.querySelector("[data-dispatch-scope]");
    refs.reset = document.querySelector("[data-dispatch-reset]");
    refs.refresh = document.querySelector("[data-dispatch-refresh]");
    refs.export = document.querySelector("[data-dispatch-export]");
    refs.scroll = Array.from(document.querySelectorAll("[data-dispatch-scroll]"));
    refs.bestWorker = document.querySelector("[data-best-worker]");
    refs.bestSuggestion = document.querySelector("[data-best-suggestion]");
    refs.updatedAt = document.querySelector("[data-updated-at]");
    refs.idleCount = document.querySelector("[data-idle-count]");
    refs.runningCount = document.querySelector("[data-running-count]");
    refs.readyCount = document.querySelector("[data-ready-count]");
    refs.blockedCount = document.querySelector("[data-blocked-count]");
  }

  function bindEvents() {
    refs.search?.addEventListener("input", handleFilterChange);
    refs.scope?.addEventListener("change", handleFilterChange);
    refs.reset?.addEventListener("click", handleResetFilters);
    refs.refresh?.addEventListener("click", loadDispatchData);
    refs.export?.addEventListener("click", handleExportSummary);
    refs.scroll.forEach((button) => button.addEventListener("click", handleScrollRequest));
  }

  function restoreState() {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
      if (!saved) return;
      state.search = saved.search || "";
      state.scope = saved.scope || "all";
      if (refs.search) refs.search.value = state.search;
      if (refs.scope) refs.scope.value = state.scope;
    } catch {
      state.error = "本地筛选状态恢复失败";
    }
  }

  function saveState() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ search: state.search, scope: state.scope }));
  }

  function readAccessToken() {
    if (typeof localStorage === "undefined") return "";
    for (const key of AUTH_TOKEN_KEYS) {
      const value = localStorage.getItem(key);
      if (value && String(value).trim()) return String(value).trim();
    }
    return "";
  }

  function createAuthHeaders() {
    const token = readAccessToken();
    return token ? { Accept: "application/json", Authorization: `Bearer ${token}` } : { Accept: "application/json" };
  }

  function isAuthError(error) {
    const status = Number(error?.status || 0);
    return status === 401 || status === 403;
  }

  function buildErrorMessage(error) {
    return isAuthError(error) ? "未登录或权限不足，无法读取任务队列数据。请先登录后重试。" : (error?.message || "任务队列暂时不可用。");
  }

  async function loadDispatchData() {
    state.loading = true;
    state.error = "";
    renderAll();
    try {
      const tasks = await fetchTaskQueue();
      state.tasks = tasks;
      state.workers = buildWorkerSnapshots(tasks);
    } catch (error) {
      state.error = buildErrorMessage(error);
      state.tasks = [];
      state.workers = structuredClone(WORKERS);
    } finally {
      state.loading = false;
      renderAll();
      saveState();
    }
  }

  async function fetchTaskQueue() {
    const response = await fetch(`${API_BASE}/workspaces/task-queue/tasks`, { headers: createAuthHeaders() });
    if (!response.ok) {
      const error = new Error(response.status === 401 || response.status === 403 ? "未登录或权限不足" : "fetch failed");
      error.status = response.status;
      throw error;
    }
    return normalizeTaskList(await response.json());
  }

  function normalizeTaskList(payload) {
    const list = Array.isArray(payload) ? payload : payload?.data || payload?.tasks || payload?.items || [];
    return list.map((item, index) => ({
      id: item.id || item.task_id || `local-${index + 1}`,
      title: item.title || item.name || `任务 ${index + 1}`,
      assignee: item.assignee || "未分配",
      status: normalizeStatus(item.status),
      priority: item.priority || item.priority_level || "中",
      workspace: item.workspace || item.workspace_kind || "dir",
      updatedAt: item.updated_at || item.updatedAt || Date.now(),
    }));
  }

  function normalizeStatus(value) {
    const raw = String(value || "").toLowerCase();
    if (["running", "doing", "in_progress"].includes(raw)) return "running";
    if (["blocked", "block"].includes(raw)) return "blocked";
    if (["done", "completed"].includes(raw)) return "done";
    return raw || "running";
  }

  function buildWorkerSnapshots(tasks) {
    return WORKERS.map((worker) => {
      const assigned = tasks.filter((task) => task.assignee === worker.id);
      const running = assigned.filter((task) => task.status === "running");
      const blocked = assigned.filter((task) => task.status === "blocked");
      const ready = assigned.filter((task) => task.status === "done").length;
      const idle = assigned.length === 0;
      return {
        ...worker,
        availability: idle ? "空闲" : worker.availability,
        score: Math.max(32, worker.score - running.length * 8 - blocked.length * 10 + ready * 2),
        assigned,
        running,
        blocked,
        ready,
      };
    });
  }

  function getFilteredWorkers() {
    const keyword = state.search.trim().toLowerCase();
    return state.workers.filter((worker) => {
      const searchable = [worker.id, worker.name, worker.title, worker.availability, worker.priority, worker.taskTypes.join(" "), worker.suggestion].join(" ").toLowerCase();
      if (keyword && !searchable.includes(keyword)) return false;
      if (state.scope === "idle" && worker.assigned.length > 0) return false;
      if (state.scope === "warm" && worker.heat !== "warm") return false;
      if (state.scope === "hot" && worker.heat !== "hot") return false;
      return true;
    });
  }

  function getBestWorker(workers) {
    if (!workers.length) return null;
    return [...workers].sort((a, b) => b.score - a.score)[0];
  }

  function handleFilterChange() {
    state.search = refs.search?.value || "";
    state.scope = refs.scope?.value || "all";
    saveState();
    renderAll();
  }

  function handleResetFilters() {
    state.search = "";
    state.scope = "all";
    if (refs.search) refs.search.value = "";
    if (refs.scope) refs.scope.value = "all";
    saveState();
    renderAll();
  }

  async function handleExportSummary() {
    const filtered = getFilteredWorkers();
    const best = getBestWorker(filtered);
    const summary = buildExportText(filtered, best);
    await copyExportText(summary);
  }

  function handleScrollRequest(event) {
    const targetId = event.currentTarget?.dataset.dispatchScroll;
    const target = targetId ? document.getElementById(targetId) : null;
    target?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  async function copyExportText(text) {
    try {
      await navigator.clipboard.writeText(text);
      if (refs.updatedAt) refs.updatedAt.textContent = "已复制到剪贴板";
    } catch {
      const area = document.createElement("textarea");
      area.value = text;
      area.setAttribute("readonly", "true");
      area.style.position = "fixed";
      area.style.opacity = "0";
      document.body.appendChild(area);
      area.select();
      document.execCommand("copy");
      document.body.removeChild(area);
      if (refs.updatedAt) refs.updatedAt.textContent = "已复制到剪贴板";
    }
  }

  function buildExportText(workers, best) {
    const counts = workers.reduce((acc, worker) => {
      if (worker.assigned.length === 0) acc.idle += 1;
      if (worker.running.length > 0) acc.running += 1;
      if (worker.blocked.length > 0) acc.blocked += 1;
      return acc;
    }, { idle: 0, running: 0, blocked: 0 });
    const lines = [
      "1034 看板摘要",
      `空闲工人：${counts.idle}`,
      `运行中：${counts.running}`,
      `阻塞中：${counts.blocked}`,
      best ? `推荐工人：${best.name}（${best.score} 分）` : "推荐工人：暂无",
      "",
      "工人明细：",
    ];
    workers.forEach((worker) => {
      lines.push(`- ${worker.name}｜${worker.availability}｜${worker.score}分｜待派发 ${worker.assigned.length} 个`);
    });
    return lines.join("
");
  }

  function renderAll() {
    renderSummary();
    renderState();
    renderGrid();
    renderHeaderPreview();
  }

  function renderSummary() {
    const counts = state.workers.reduce((acc, worker) => {
      if (worker.assigned.length === 0) acc.idle += 1;
      if (worker.running.length > 0) acc.running += 1;
      if (worker.ready > 0) acc.ready += 1;
      if (worker.blocked.length > 0) acc.blocked += 1;
      return acc;
    }, { idle: 0, running: 0, ready: 0, blocked: 0 });
    if (refs.summary) {
      refs.summary.innerHTML = [
        `profile <strong>${state.search || "全部"}</strong>`,
        `空闲 <strong>${counts.idle}</strong>`,
        `运行中 <strong>${counts.running}</strong>`,
        `待完成 <strong>${counts.ready}</strong>`,
      ].map((item) => `<span class="summary-chip">${item}</span>`).join("");
    }
    if (refs.idleCount) refs.idleCount.textContent = String(counts.idle);
    if (refs.runningCount) refs.runningCount.textContent = String(counts.running);
    if (refs.readyCount) refs.readyCount.textContent = String(counts.ready);
    if (refs.blockedCount) refs.blockedCount.textContent = String(counts.blocked);
    if (refs.updatedAt) refs.updatedAt.textContent = state.loading ? "正在刷新" : `更新于 ${new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })}`;
  }

  function renderHeaderPreview() {
    const best = getBestWorker(getFilteredWorkers());
    if (!refs.bestWorker || !refs.bestSuggestion) return;
    if (state.loading) {
      refs.bestWorker.textContent = "正在同步";
      refs.bestSuggestion.textContent = "加载后会展示推荐工人与派发理由。";
      return;
    }
    if (state.error) {
      refs.bestWorker.textContent = "加载失败";
      refs.bestSuggestion.textContent = state.error;
      return;
    }
    if (!best) {
      refs.bestWorker.textContent = "暂无匹配";
      refs.bestSuggestion.textContent = "清空筛选后可重新查看推荐工人。";
      return;
    }
    refs.bestWorker.textContent = best.name;
    refs.bestSuggestion.textContent = `${best.suggestion} 当前评分 ${best.score} 分，建议优先派发 ${best.taskTypes[0]}。`;
  }

  function renderState() {
    if (!refs.state) return;
    if (state.loading) {
      refs.state.className = "panel-state";
      refs.state.innerHTML = '<section class="state-inline"><span class="spinner" aria-hidden="true"></span><h3>加载中</h3></section><p>正在同步任务队列并计算热力。</p>';
      return;
    }
    if (state.error) {
      refs.state.className = "panel-state is-error";
      refs.state.innerHTML = `<section class="state-inline"><h3>网络错误</h3></section><p>${escapeHtml(state.error)}</p><button class="btn btn-primary" type="button" data-dispatch-retry>重试</button>`;
      refs.state.querySelector("[data-dispatch-retry]")?.addEventListener("click", loadDispatchData);
      return;
    }
    const filtered = getFilteredWorkers();
    if (!filtered.length) {
      refs.state.className = "panel-state";
      refs.state.innerHTML = '<section class="state-inline"><h3>暂无数据</h3></section><p>当前没有符合条件的工人，请清空筛选后再试。</p><button class="btn btn-primary" type="button" data-dispatch-retry>清空筛选</button>';
      refs.state.querySelector("[data-dispatch-retry]")?.addEventListener("click", handleResetFilters);
      return;
    }
    refs.state.className = "panel-state is-success";
    refs.state.innerHTML = `<section class="state-inline"><h3>已加载</h3></section><p>当前显示 ${filtered.length} 名工人，支持按中文关键字、热力范围与状态快速筛选。</p>`;
  }

  function renderGrid() {
    if (!refs.grid) return;
    const filtered = getFilteredWorkers();
    if (state.loading) {
      refs.grid.innerHTML = Array.from({ length: 3 }, () => renderSkeletonCard()).join("");
      return;
    }
    if (state.error) {
      refs.grid.innerHTML = renderEmptyCard("暂无数据", "接口暂不可用时会显示错误提示与重试按钮。", true);
      return;
    }
    if (!filtered.length) {
      refs.grid.innerHTML = renderEmptyCard("暂无数据", "当前没有符合筛选条件的工人。", true);
      return;
    }
    refs.grid.innerHTML = filtered.map(renderWorkerCard).join("");
    bindWorkerActions();
  }

  function renderWorkerCard(worker) {
    return `
      <article class="worker-card" data-heat="${escapeHtml(worker.heat)}">
        <header class="worker-card__head">
          <div>
            <h3>${escapeHtml(worker.name)}</h3>
            <p>${escapeHtml(worker.title)}</p>
          </div>
          <span class="heat-badge">${escapeHtml(worker.availability)}</span>
        </header>
        <p class="worker-card__hint">${escapeHtml(worker.suggestion)}</p>
        <p class="load-label"><strong>热力</strong><span>${worker.score}%</span></p>
        <div class="heatbar" aria-hidden="true" style="--load-width:${worker.score}%"><i></i></div>
        <dl class="worker-counts">
          <div><dt>待派发</dt><dd>${worker.assigned.length}</dd></div>
          <div><dt>运行中</dt><dd>${worker.running.length}</dd></div>
          <div><dt>阻塞</dt><dd>${worker.blocked.length}</dd></div>
        </dl>
        <div class="worker-card__actions">
          <button class="btn btn-primary" type="button" data-worker-select="${escapeHtml(worker.id)}">设为候选</button>
          <button class="btn btn-secondary" type="button" data-worker-focus="${escapeHtml(worker.id)}">查看理由</button>
        </div>
      </article>
    `;
  }

  function renderSkeletonCard() {
    return '<article class="panel-skeleton" aria-hidden="true"></article>';
  }

  function renderEmptyCard(title, description, includeRetry = false) {
    return `
      <article class="panel-empty">
        <h3>${escapeHtml(title)}</h3>
        <p>${escapeHtml(description)}</p>
        ${includeRetry ? '<button class="btn btn-primary" type="button" data-dispatch-empty-retry>重试加载</button>' : ""}
      </article>
    `;
  }

  function bindWorkerActions() {
    refs.grid.querySelectorAll("[data-worker-select]").forEach((button) => {
      button.addEventListener("click", () => {
        state.selectedWorker = button.dataset.workerSelect || state.selectedWorker;
        renderHeaderPreview();
      });
    });
    refs.grid.querySelectorAll("[data-worker-focus]").forEach((button) => {
      button.addEventListener("click", () => {
        const worker = state.workers.find((item) => item.id === button.dataset.workerFocus);
        if (!worker) return;
        refs.bestWorker.textContent = worker.name;
        refs.bestSuggestion.textContent = `${worker.suggestion} 当前评分 ${worker.score} 分。`;
      });
    });
    refs.grid.querySelectorAll("[data-dispatch-empty-retry]").forEach((button) => {
      button.addEventListener("click", state.error ? loadDispatchData : handleResetFilters);
    });
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
