(()=>{
  "use strict";

  const API_BASE = "/api/v1";
  const TASK_ENDPOINT = "/api/v1/task-queue/tasks";
  const STORAGE_KEY = "1034.worker-recommendation-modal.v1";
  const AUTH_TOKEN_KEYS = ["access_token", "accessToken", "token", "authToken", "workerAccessToken"];
  const STATUS_LABELS = {
    ready: "待处理",
    running: "运行中",
    blocked: "阻塞",
    done: "已完成",
    archived: "已归档",
  };

  const state = {
    loading: true,
    error: "",
    workers: [],
    tasks: [],
    selectedWorker: "frontend-dev",
    scope: "all",
    lastUpdated: 0,
  };

  const refs = {};

  document.addEventListener("DOMContentLoaded", initApp);

  function initApp() {
    cacheRefs();
    bindEvents();
    restoreState();
    loadRecommendationData();
  }

  function cacheRefs() {
    refs.summary = document.querySelector("[data-worker-summary]");
    refs.state = document.querySelector("[data-worker-state]");
    refs.list = document.querySelector("[data-worker-list]");
    refs.panel = document.querySelector("[data-worker-panel]");
    refs.freeCount = document.querySelector("[data-worker-free-count]");
    refs.runningCount = document.querySelector("[data-worker-running-count]");
    refs.blockedCount = document.querySelector("[data-worker-blocked-count]");
    refs.ownerCount = document.querySelector("[data-worker-owner-count]");
    refs.status = document.querySelector("[data-worker-status]");
    refs.suggestion = document.querySelector("[data-worker-suggestion]");
    refs.refresh = Array.from(document.querySelectorAll("[data-worker-refresh]"));
    refs.scopes = Array.from(document.querySelectorAll("[data-worker-scope]"));
    refs.jump = Array.from(document.querySelectorAll("[data-worker-jump]"));
  }

  function bindEvents() {
    refs.refresh.forEach((button) => button.addEventListener("click", loadRecommendationData));
    refs.scopes.forEach((button) => button.addEventListener("click", handleScopeChange));
    refs.jump.forEach((button) => button.addEventListener("click", handleJumpClick));
  }

  function handleJumpClick(event) {
    const targetId = event.currentTarget?.dataset.workerJump || "任务创建入口";
    document.getElementById(targetId)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function restoreState() {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
      if (!saved) return;
      state.scope = saved.scope || state.scope;
      state.selectedWorker = saved.selectedWorker || state.selectedWorker;
      setActiveScope(state.scope);
    } catch {
      state.error = "本地推荐状态恢复失败";
    }
  }

  function saveState() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({
      scope: state.scope,
      selectedWorker: state.selectedWorker,
    }));
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
    const status = Number(error?.status || error?.response?.status || 0);
    return status === 401 || status === 403;
  }

  async function loadRecommendationData() {
    state.loading = true;
    state.error = "";
    renderAll();
    try {
      const tasks = await fetchTasks();
      state.tasks = tasks;
      state.workers = buildWorkers(tasks);
    } catch (error) {
      if (isAuthError(error)) {
        state.tasks = [];
        state.workers = buildWorkers([]);
        state.error = "未登录或权限不足，无法读取任务队列数据。请先登录后重试。";
      } else {
        state.tasks = buildFallbackTasks();
        state.workers = buildWorkers(state.tasks);
        state.error = "任务队列接口暂时不可用，请检查后端服务后重试。";
      }
    } finally {
      state.loading = false;
      if (!state.workers.some((worker) => worker.id === state.selectedWorker)) {
        state.selectedWorker = state.workers[0]?.id || "frontend-dev";
      }
      state.lastUpdated = Date.now();
      renderAll();
      saveState();
    }
  }

  async function fetchTasks() {
    const response = await fetch(TASK_ENDPOINT, { headers: createAuthHeaders() });
    if (!response.ok) {
      const error = new Error(response.status === 401 || response.status === 403 ? "未登录或权限不足" : "fetch failed");
      error.status = response.status;
      throw error;
    }
    return normalizeTaskList(await response.json());
  }

  function normalizeTaskList(payload) {
    const list = Array.isArray(payload) ? payload : payload?.data || payload?.tasks || [];
    return list.map((item, index) => ({
      id: item.id || item.task_id || `task-${index + 1}`,
      title: item.title || item.name || `任务 ${index + 1}`,
      description: item.description || item.body || "暂无描述",
      assignee: item.assignee || item.profile || item.owner || "未分配",
      status: normalizeStatus(item.status),
      priority: item.priority || item.priority_level || "中",
      workspace: item.workspace || item.workspace_kind || "dir",
    }));
  }

  function buildFallbackTasks() {
    return [
      { id: "t-front-running", title: "空闲 worker 推荐弹层", description: "前端页面正在实现与验证。", assignee: "frontend-dev", status: "running", priority: "高", workspace: "dir" },
      { id: "t-front-done", title: "移动端筛选条", description: "已完成响应式筛选条。", assignee: "frontend-dev", status: "done", priority: "中", workspace: "dir" },
      { id: "t-back-ready", title: "任务队列字段确认", description: "待确认接口字段稳定性。", assignee: "backend-dev", status: "ready", priority: "中", workspace: "dir" },
      { id: "t-back-blocked", title: "聚合接口评估", description: "等待分诊是否需要后端聚合。", assignee: "backend-dev", status: "blocked", priority: "低", workspace: "dir" },
      { id: "t-devops-done", title: "预览服务检查", description: "静态服务可正常访问。", assignee: "devops-engineer", status: "done", priority: "低", workspace: "scratch" },
    ];
  }

  function buildWorkers(tasks) {
    const profiles = Array.from(new Set(["frontend-dev", "backend-dev", "devops-engineer", ...tasks.map((task) => task.assignee).filter(Boolean)]));
    return profiles.map((profile) => {
      const assigned = tasks.filter((task) => task.assignee === profile);
      const running = assigned.filter((task) => task.status === "running");
      const blocked = assigned.filter((task) => task.status === "blocked");
      const ready = assigned.filter((task) => task.status === "ready");
      const done = assigned.filter((task) => task.status === "done");
      const activeCount = running.length + blocked.length + ready.length;
      const load = calculateLoad({ running: running.length, blocked: blocked.length, ready: ready.length, done: done.length });
      return {
        id: profile,
        name: profile,
        title: getWorkerTitle(profile),
        assigned,
        running,
        blocked,
        ready,
        done,
        load,
        status: getLoadState(load),
        suggestion: buildSuggestion(profile, { running: running.length, blocked: blocked.length, ready: ready.length, done: done.length }, load),
        taskTypes: getWorkerTaskTypes(profile),
        reason: buildReason(profile, activeCount, load),
      };
    }).sort(sortWorkers);
  }

  function getWorkerTitle(profile) {
    if (profile === "frontend-dev") return "前端空闲 worker";
    if (profile === "backend-dev") return "后端空闲 worker";
    if (profile === "devops-engineer") return "运维调度 worker";
    return "待分配 worker";
  }

  function getWorkerTaskTypes(profile) {
    if (profile === "frontend-dev") return ["页面搭建", "响应式布局", "交互补全", "状态处理"];
    if (profile === "backend-dev") return ["接口对齐", "字段校验", "数据聚合", "持久化"];
    if (profile === "devops-engineer") return ["部署检查", "服务探活", "日志巡检", "环境配置"];
    return ["任务接手", "快速补位", "轻量修复"];
  }

  function calculateLoad(counts) {
    const active = counts.running * 2 + counts.blocked + counts.ready;
    const total = counts.done + counts.running + counts.ready + counts.blocked;
    return total ? Math.min(100, Math.round((active / Math.max(1, total + 1)) * 100)) : 0;
  }

  function getLoadState(load) {
    if (load >= 70) return "高负载";
    if (load >= 35) return "中负载";
    return "空闲";
  }

  function buildSuggestion(profile, counts, load) {
    if (load === 0) return `${profile} 当前无活跃任务，是新增任务的优先候选。`;
    if (counts.running) return `${profile} 正在处理 ${counts.running} 个任务，建议先观察 running 队列。`;
    if (counts.blocked) return `${profile} 有 ${counts.blocked} 个阻塞任务，建议优先清理依赖。`;
    if (counts.ready) return `${profile} 有 ${counts.ready} 个待处理任务，适合直接领取推进。`;
    if (counts.done) return `${profile} 近期以已完成任务为主，可承接轻量补充任务。`;
    return `${profile} 当前适合作为临时接单对象。`;
  }

  function buildReason(profile, activeCount, load) {
    if (load === 0) return `${profile} 空闲且没有排队任务，适合立刻接单。`;
    if (activeCount <= 1) return `${profile} 任务较少，推荐优先分配。`;
    if (load < 50) return `${profile} 负载适中，可作为次优推荐。`;
    return `${profile} 当前负载较高，建议仅在紧急时分配。`;
  }

  function sortWorkers(a, b) {
    if (state.scope === "idle") return a.load - b.load || a.name.localeCompare(b.name);
    if (state.scope === "running") return b.running.length - a.running.length || a.load - b.load;
    if (state.scope === "blocked") return b.blocked.length - a.blocked.length || a.load - b.load;
    return a.load - b.load || a.name.localeCompare(b.name);
  }

  function renderAll() {
    renderSummary();
    renderState();
    renderWorkerList();
    renderDetailPanel();
  }

  function renderSummary() {
    const idleWorkers = state.workers.filter((worker) => worker.load === 0);
    const runningTasks = state.tasks.filter((task) => task.status === "running");
    const blockedTasks = state.tasks.filter((task) => task.status === "blocked");
    const readyTasks = state.tasks.filter((task) => task.status === "ready");
    refs.summary.innerHTML = [
      `空闲 <strong>${idleWorkers.length}</strong>`,
      `运行中 <strong>${runningTasks.length}</strong>`,
      `待处理 <strong>${readyTasks.length}</strong>`,
      `阻塞 <strong>${blockedTasks.length}</strong>`,
    ].map((item) => `<span class="summary-chip">${item}</span>`).join("");
    if (refs.freeCount) refs.freeCount.textContent = String(idleWorkers.length);
    if (refs.runningCount) refs.runningCount.textContent = String(runningTasks.length);
    if (refs.blockedCount) refs.blockedCount.textContent = String(blockedTasks.length);
    if (refs.ownerCount) refs.ownerCount.textContent = String(state.workers.length);
  }

  function renderState() {
    if (!refs.state) return;
    if (state.loading) {
      refs.state.innerHTML = `<div><h3>加载中</h3><p>正在读取任务队列并整理推荐结果。</p></div><span class="spinner" aria-hidden="true"></span>`;
      return;
    }
    if (state.error) {
      refs.state.classList.add("is-error");
      refs.state.innerHTML = `<div><h3>加载失败</h3><p>${escapeHtml(state.error)}</p></div><button class="btn btn-primary" type="button" data-worker-refresh>重试</button>`;
      return;
    }
    refs.state.classList.remove("is-error");
    refs.state.innerHTML = `<div><h3>推荐状态</h3><p>${escapeHtml(state.workers[0]?.reason || "当前暂无可用 worker。")}</p></div><button class="btn btn-secondary" type="button" data-worker-refresh>刷新推荐</button>`;
    refs.state.querySelectorAll("[data-worker-refresh]").forEach((button) => button.addEventListener("click", loadRecommendationData));
  }

  function renderWorkerList() {
    if (!refs.list) return;
    if (state.loading) {
      refs.list.innerHTML = Array.from({ length: 3 }, () => renderSkeletonCard()).join("");
      return;
    }
    if (state.error && !state.workers.length) {
      refs.list.innerHTML = renderErrorCard();
      bindRetryButton(refs.list);
      return;
    }
    const filtered = getFilteredWorkers();
    if (!filtered.length) {
      refs.list.innerHTML = renderEmptyState("暂无数据", "当前没有符合条件的 worker。");
      return;
    }
    refs.list.innerHTML = filtered.map(renderWorkerCard).join("");
    bindWorkerButtons();
  }

  function renderDetailPanel() {
    if (!refs.panel) return;
    const selectedWorker = state.workers.find((worker) => worker.id === state.selectedWorker) || state.workers[0];
    if (!selectedWorker) {
      refs.panel.innerHTML = renderEmptyState("暂无数据", "当前没有可展示的 worker 推荐。");
      return;
    }
    refs.panel.innerHTML = `
      <div class="import-permission__card-head">
        <div>
          <h3>${escapeHtml(selectedWorker.name)}</h3>
          <p>${escapeHtml(selectedWorker.title)}</p>
        </div>
        <span class="idle-filter-demo__badge">AI</span>
      </div>
      <div class="import-permission__notice">
        <strong>当前聚焦</strong>
        <p>${escapeHtml(selectedWorker.status)}</p>
      </div>
      <div class="import-permission__notice">
        <strong>推荐理由</strong>
        <p>${escapeHtml(selectedWorker.reason)}</p>
      </div>
      <div class="import-permission__notice">
        <strong>可接任务</strong>
        <p>${escapeHtml(selectedWorker.taskTypes.join("、"))}</p>
      </div>
      <div class="import-permission__link-list">
        <a class="btn btn-primary" href="#任务创建入口" data-worker-jump="任务创建入口">跳转到任务创建入口</a>
        <button class="btn btn-secondary" type="button" data-worker-refresh>刷新推荐</button>
      </div>
    `;
    refs.panel.querySelectorAll("[data-worker-refresh]").forEach((button) => button.addEventListener("click", loadRecommendationData));
    refs.suggestion.textContent = selectedWorker.suggestion;
    if (refs.status) refs.status.textContent = `${selectedWorker.status} · 负载 ${selectedWorker.load}%`;
  }

  function getFilteredWorkers() {
    return state.workers.filter((worker) => {
      if (state.scope === "idle" && worker.load > 0) return false;
      if (state.scope === "running" && !worker.running.length) return false;
      if (state.scope === "blocked" && !worker.blocked.length) return false;
      return true;
    });
  }

  function renderWorkerCard(worker) {
    return `
      <article class="import-permission__card ${worker.id === state.selectedWorker ? "is-selected" : ""}">
        <header class="import-permission__card-head">
          <div>
            <h3>${escapeHtml(worker.name)}</h3>
            <p>${escapeHtml(worker.title)}</p>
          </div>
          <span class="worker-panel__badge" data-state="${escapeHtml(worker.status)}">${escapeHtml(worker.status)}</span>
        </header>
        <p class="import-permission__notice">${escapeHtml(worker.suggestion)}</p>
        <div class="idle-filter-demo__meter" aria-hidden="true"><i style="width:${worker.load}%"></i></div>
        <dl class="idle-filter-demo__meta">
          <div><dt>评分</dt><dd>${worker.load}</dd></div>
          <div><dt>负载</dt><dd>${worker.load}%</dd></div>
        </dl>
        <div class="idle-filter-demo__tags">
          ${worker.taskTypes.map((tag) => `<span class="idle-filter-demo__tag">${escapeHtml(tag)}</span>`).join("")}
        </div>
        <div class="import-permission__link-list">
          <button class="btn btn-primary" type="button" data-worker-select="${escapeHtml(worker.id)}">查看建议</button>
          <a class="btn btn-secondary" href="#任务创建入口">前往创建入口</a>
        </div>
      </article>
    `;
  }

  function renderSkeletonCard() {
    return `<article class="import-permission__skeleton" aria-hidden="true"></article>`;
  }

  function renderEmptyState(title, description) {
    return `<article class="import-permission__empty"><h4>${escapeHtml(title)}</h4><p>${escapeHtml(description)}</p></article>`;
  }

  function renderErrorCard() {
    return `
      <article class="import-permission__error-card is-error">
        <h4>加载失败</h4>
        <p>${escapeHtml(state.error)}</p>
        <button class="btn btn-primary" type="button" data-worker-retry>重试</button>
      </article>
    `;
  }

  function bindWorkerButtons() {
    refs.list?.querySelectorAll("[data-worker-select]").forEach((button) => {
      button.addEventListener("click", () => {
        state.selectedWorker = button.dataset.workerSelect || state.selectedWorker;
        renderDetailPanel();
        saveState();
      });
    });
  }

  function bindRetryButton(root) {
    root?.querySelectorAll("[data-worker-retry]").forEach((button) => button.addEventListener("click", loadRecommendationData));
  }

  function handleScopeChange(event) {
    state.scope = event.currentTarget?.dataset.workerScope || "all";
    setActiveScope(state.scope);
    renderWorkerList();
    saveState();
  }

  function setActiveScope(scope) {
    refs.scopes.forEach((button) => {
      const active = (button.dataset.workerScope || "all") === scope;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-pressed", active ? "true" : "false");
    });
  }

  function normalizeStatus(value) {
    const raw = String(value || "").toLowerCase();
    if (["running", "doing", "in_progress"].includes(raw)) return "running";
    if (["ready", "pending", "todo", "triage"].includes(raw)) return "ready";
    if (["blocked", "block"].includes(raw)) return "blocked";
    if (["archived", "archive"].includes(raw)) return "archived";
    if (["done", "completed", "complete"].includes(raw)) return "done";
    return "ready";
  }

  function handleWorkerSelect(event) {
    const workerId = event.currentTarget?.dataset.workerSelect;
    if (!workerId) return;
    state.selectedWorker = workerId;
    renderDetailPanel();
    saveState();
  }

  function handleWorkerRetry() {
    loadRecommendationData();
  }

  function bindWorkerButtons() {
    refs.list?.querySelectorAll("[data-worker-select]").forEach((button) => {
      button.addEventListener("click", handleWorkerSelect);
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
