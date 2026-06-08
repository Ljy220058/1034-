(()=>{
  "use strict";

  const API_BASE = "/api/v1";
  const STORAGE_KEY = "1034.worker-panel.filters.v1";
  const EXPORT_STORAGE_KEY = "1034.worker-panel.export.v1";
  const AUTH_TOKEN_KEYS = ["access_token", "accessToken", "token", "authToken", "workerAccessToken"];
  const WORKERS = [
    {
      id: "frontend-dev",
      name: "frontend-dev",
      title: "前端空闲 worker",
      status: "空闲",
      availability: "空闲",
      priority: "高",
      score: 96,
      load: 18,
      taskTypes: ["页面搭建", "响应式布局", "交互补全", "状态处理"],
      suggestion: "适合承担卡片布局、筛选联动和移动端细节优化。",
      endpoint: "/api/v1/workspaces/task-queue/tasks?assignee=frontend-dev",
    },
    {
      id: "backend-dev",
      name: "backend-dev",
      title: "后端空闲 worker",
      status: "忙碌",
      availability: "忙碌",
      priority: "中",
      score: 74,
      load: 42,
      taskTypes: ["接口对齐", "字段校验", "数据聚合", "持久化"],
      suggestion: "适合处理接口返回格式、聚合字段与数据一致性。",
      endpoint: "/api/v1/workspaces/task-queue/tasks?assignee=backend-dev",
    },
    {
      id: "devops-engineer",
      name: "devops-engineer",
      title: "运维调度 worker",
      status: "离线",
      availability: "离线",
      priority: "低",
      score: 58,
      load: 68,
      taskTypes: ["部署检查", "服务探活", "日志巡检", "环境配置"],
      suggestion: "适合接收需要环境检查与发布保障的任务。",
      endpoint: "/api/v1/workspaces/task-queue/tasks?assignee=devops-engineer",
    },
  ];

  const TASK_TEMPLATES = {
    frontend: [
      { title: "补齐任务卡悬停与禁用态", description: "为任务板卡片补充 hover/active/disabled/loading 交互细节，保持暗色主题统一。", priority: "高" },
      { title: "优化手机端任务筛选栏", description: "在 375px 宽度下整理任务筛选控件顺序与间距，避免横向滚动。", priority: "中" },
    ],
    backend: [
      { title: "校验任务队列返回字段", description: "确认 /api/v1/workspaces/task-queue/tasks 返回 assignee、workspace 和 status 的稳定结构。", priority: "高" },
      { title: "补充任务详情聚合字段", description: "为任务分配视图补充可直接渲染的优先级和负责人统计字段。", priority: "中" },
    ],
  };

  const state = {
    loading: true,
    error: "",
    workers: structuredClone(WORKERS),
    tasks: [],
    selectedWorker: "frontend-dev",
    selectedPriority: "高",
    workerScope: "all",
  };

  const refs = {};

  document.addEventListener("DOMContentLoaded", initApp);

  function initApp() {
    cacheRefs();
    bindEvents();
    restoreState();
    loadAssignmentData();
  }

  function cacheRefs() {
    refs.summary = document.querySelector("[data-assignment-summary]");
    refs.state = document.querySelector("[data-assignment-state]");
    refs.idleWorkers = document.querySelector("[data-idle-workers]");
    refs.activeAssignments = document.querySelector("[data-active-assignments]");
    refs.workerPanel = document.querySelector("[data-worker-panel]");
    refs.workerSummary = document.querySelector("[data-worker-summary]");
    refs.workerFreeCount = document.querySelector("[data-worker-free-count]");
    refs.workerRunningCount = document.querySelector("[data-worker-running-count]");
    refs.workerBlockedCount = document.querySelector("[data-worker-blocked-count]");
    refs.workerOwnerCount = document.querySelector("[data-worker-owner-count]");
    refs.workerStatus = document.querySelector("[data-worker-status]");
    refs.workerQuickSummary = document.querySelector("[data-worker-quick-summary]");
    refs.workerList = document.querySelector("[data-worker-list]");
    refs.workerTags = document.querySelector("[data-worker-tags]");
    refs.workerSuggestion = document.querySelector("[data-worker-suggestion]");
    refs.workerEmpty = document.querySelector("[data-worker-empty]");
    refs.frontendCard = document.querySelector("[data-frontend-card]");
    refs.backendCard = document.querySelector("[data-backend-card]");
    refs.frontendScore = document.querySelector("[data-frontend-score]");
    refs.backendScore = document.querySelector("[data-backend-score]");
    refs.frontendStatus = document.querySelector("[data-frontend-status]");
    refs.backendStatus = document.querySelector("[data-backend-status]");
    refs.frontendAvailability = document.querySelector("[data-frontend-availability]");
    refs.backendAvailability = document.querySelector("[data-backend-availability]");
    refs.bulkSummary = document.querySelector("[data-bulk-summary]");
    refs.bulkRefresh = document.querySelector("[data-bulk-refresh]");
    refs.assignmentRefresh = document.querySelector("[data-assignment-refresh]");
    refs.taskList = document.querySelector("[data-task-list]");
    refs.taskState = document.querySelector("[data-task-state]");
    refs.taskSummary = document.querySelector("[data-task-summary]");
    refs.taskReset = document.querySelector("[data-task-reset]");
    refs.taskRefresh = document.querySelector("[data-task-refresh]");
    refs.workerRefresh = Array.from(document.querySelectorAll("[data-worker-refresh]"));
    refs.workerScopes = Array.from(document.querySelectorAll("[data-worker-scope]"));
    refs.taskSearch = document.querySelector("[data-task-filter=search]");
    refs.taskAssignee = document.querySelector("[data-task-filter=assignee]");
    refs.taskWorkspace = document.querySelector("[data-task-filter=workspace]");
    refs.taskToday = document.querySelector("[data-task-today]");
    refs.statusButtons = Array.from(document.querySelectorAll("[data-task-status]"));
  }

  function bindEvents() {
    refs.bulkRefresh?.addEventListener("click", loadAssignmentData);
    refs.assignmentRefresh?.addEventListener("click", loadAssignmentData);
    refs.taskRefresh?.addEventListener("click", loadTasks);
    refs.taskReset?.addEventListener("click", handleResetFilters);
    refs.taskSearch?.addEventListener("input", handleFilterChange);
    refs.taskAssignee?.addEventListener("change", handleFilterChange);
    refs.taskWorkspace?.addEventListener("change", handleFilterChange);
    refs.taskToday?.addEventListener("change", handleFilterChange);
    refs.statusButtons.forEach((button) => button.addEventListener("click", handleStatusClick));
    refs.workerRefresh.forEach((button) => button.addEventListener("click", loadWorkerPanel));
    refs.workerScopes.forEach((button) => button.addEventListener("click", handleWorkerScopeChange));
    document.querySelectorAll("[data-worker-jump='任务板']").forEach((button) => {
      button.addEventListener("click", () => document.getElementById("任务板")?.scrollIntoView({ behavior: "smooth", block: "start" }));
    });
  }

  function restoreState() {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
      if (!saved) return;
      if (refs.taskSearch) refs.taskSearch.value = saved.search || "";
      if (refs.taskAssignee) refs.taskAssignee.value = saved.assignee || "";
      if (refs.taskWorkspace) refs.taskWorkspace.value = saved.workspace || "";
      if (refs.taskToday) refs.taskToday.checked = !!saved.todayOnly;
      state.workerScope = saved.workerScope || state.workerScope;
      setActiveStatus(saved.status || "");
      setActiveWorkerScope(state.workerScope);
    } catch {
      state.error = "本地草稿恢复失败";
    }
  }

  function saveState() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({
      search: refs.taskSearch?.value || "",
      assignee: refs.taskAssignee?.value || "",
      workspace: refs.taskWorkspace?.value || "",
      todayOnly: !!refs.taskToday?.checked,
      status: getActiveStatus(),
      workerScope: state.workerScope,
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

  function buildAuthErrorMessage(error) {
    return isAuthError(error) ? "未登录或权限不足，无法读取任务队列数据。请先登录后重试。" : (error?.message || "任务队列暂时不可用，已切换到本地占位数据。");
  }

  async function loadAssignmentData() {
    state.loading = true;
    state.error = "";
    renderAll();
    try {
      const tasks = await fetchTasks();
      state.tasks = tasks;
      state.workers = buildWorkerSnapshots(state.tasks);
    } catch (error) {
      state.error = buildAuthErrorMessage(error);
      state.tasks = isAuthError(error) ? [] : buildFallbackTasks();
      state.workers = buildWorkerSnapshots(state.tasks.length ? state.tasks : buildFallbackTasks());
    } finally {
      state.loading = false;
      renderAll();
      saveState();
    }
  }

  async function loadTasks() {
    state.loading = true;
    state.error = "";
    renderTasks();
    try {
      const tasks = await fetchTasks();
      state.tasks = tasks;
      state.workers = buildWorkerSnapshots(state.tasks);
    } catch (error) {
      state.error = buildAuthErrorMessage(error);
      state.tasks = isAuthError(error) ? [] : buildFallbackTasks();
      state.workers = buildWorkerSnapshots(state.tasks.length ? state.tasks : buildFallbackTasks());
    } finally {
      state.loading = false;
      renderAll();
      saveState();
    }
  }

  async function fetchTasks() {
    const response = await fetch(`${API_BASE}/workspaces/task-queue/tasks`, { headers: createAuthHeaders() });
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
      id: item.id || item.task_id || `local-${index + 1}`,
      title: item.title || item.name || `任务 ${index + 1}`,
      description: item.description || item.body || "暂无描述",
      assignee: item.assignee || "未分配",
      status: normalizeStatus(item.status),
      priority: item.priority || item.priority_level || "中",
      workspace: item.workspace || item.workspace_kind || "dir",
      createdAt: item.created_at || item.createdAt || Date.now(),
      updatedAt: item.updated_at || item.updatedAt || Date.now(),
      today: Boolean(item.today || item.is_today || false),
      detailUrl: item.detail_url || item.url || "#",
    }));
  }

  function buildFallbackTasks() {
    return [
      { id: "t-ui-assign-01", title: "补齐空闲 worker 状态卡", description: "展示空闲 worker、可接任务类型、建议优先级与一键派发入口。", assignee: "frontend-dev", status: "running", priority: "高", workspace: "dir", createdAt: Date.now(), updatedAt: Date.now(), today: true },
      { id: "t-api-assign-02", title: "核对任务列表字段", description: "确认 task-queue 的返回包含 assignee、status、workspace 和 priority。", assignee: "backend-dev", status: "blocked", priority: "中", workspace: "dir", createdAt: Date.now() - 86400000, updatedAt: Date.now() - 3600000, today: false },
      { id: "t-deploy-03", title: "检查本地预览服务", description: "确认静态页面可通过本地 http.server 打开并稳定访问。", assignee: "devops-engineer", status: "done", priority: "低", workspace: "scratch", createdAt: Date.now() - 172800000, updatedAt: Date.now() - 86400000, today: false },
    ];
  }

  function buildWorkerSnapshots(tasks) {
    return WORKERS.map((worker) => {
      const assigned = tasks.filter((task) => task.assignee === worker.id);
      const active = assigned.filter((task) => task.status === "running" || task.status === "blocked");
      const idle = assigned.length === 0;
      return {
        ...worker,
        status: idle ? "空闲" : worker.status,
        availability: idle ? "空闲" : worker.availability,
        score: Math.max(42, worker.score - active.length * 6 + assigned.length * 2),
        assigned,
        active,
      };
    });
  }

  function renderAll() {
    renderAssignmentView();
    renderBulkAssignment();
    renderWorkerPanel();
    renderTasks();
  }

  function renderAssignmentView() {
    if (!refs.summary || !refs.idleWorkers || !refs.activeAssignments || !refs.state) return;
    const idleWorkers = state.workers.filter((worker) => worker.assigned.length === 0);
    const activeAssignments = state.tasks.filter((task) => task.status === "running" || task.status === "blocked");
    refs.summary.innerHTML = [
      `空闲 worker <strong>${idleWorkers.length}</strong>`,
      `分配中 <strong>${activeAssignments.length}</strong>`,
      `总 worker <strong>${state.workers.length}</strong>`,
    ].map((item) => `<span class="summary-chip">${item}</span>`).join("");
    refs.state.innerHTML = state.loading
      ? renderLoadingState("正在加载任务分配视图")
      : state.error
        ? renderErrorState(state.error)
        : `<article class="task-board__notice"><strong>视图已更新</strong><span>当前展示 ${idleWorkers.length} 名空闲 worker 和 ${activeAssignments.length} 条活跃任务。</span></article>`;
    refs.idleWorkers.innerHTML = idleWorkers.length ? idleWorkers.map(renderWorkerCard).join("") : renderEmptyState("暂无空闲 worker", "所有 worker 当前都有分配中的任务。");
    refs.activeAssignments.innerHTML = activeAssignments.length ? activeAssignments.map(renderAssignmentCard).join("") : renderEmptyState("暂无数据", "当前没有分配中的任务。");
    bindRetryActions();
  }

  function renderBulkAssignment() {
    if (!refs.frontendCard || !refs.backendCard) return;
    const frontend = state.workers.find((worker) => worker.id === "frontend-dev") || WORKERS[0];
    const backend = state.workers.find((worker) => worker.id === "backend-dev") || WORKERS[1];
    if (refs.frontendScore) refs.frontendScore.style.width = `${frontend.score}%`;
    if (refs.backendScore) refs.backendScore.style.width = `${backend.score}%`;
    if (refs.frontendStatus) refs.frontendStatus.textContent = `${frontend.active.length ? "忙碌" : "空闲"} · ${frontend.score} 分`;
    if (refs.backendStatus) refs.backendStatus.textContent = `${backend.active.length ? "忙碌" : "空闲"} · ${backend.score} 分`;
    if (refs.frontendAvailability) refs.frontendAvailability.textContent = `可接：${frontend.taskTypes.join("、")}`;
    if (refs.backendAvailability) refs.backendAvailability.textContent = `可接：${backend.taskTypes.join("、")}`;
    if (refs.bulkSummary) {
      refs.bulkSummary.innerHTML = state.loading
        ? renderLoadingState("正在生成推荐")
        : state.error
          ? renderErrorState(state.error)
          : `<strong>推荐完成</strong><span>前端优先派发给 ${frontend.name}，后端优先派发给 ${backend.name}。</span>`;
    }
    refs.frontendCard.innerHTML = state.loading ? renderSkeletonCard() : renderRecommendationCard(frontend, TASK_TEMPLATES.frontend);
    refs.backendCard.innerHTML = state.loading ? renderSkeletonCard() : renderRecommendationCard(backend, TASK_TEMPLATES.backend);
    bindRetryActions();
  }

  function renderWorkerPanel() {
    if (!refs.workerSummary || !refs.workerStatus || !refs.workerList || !refs.workerTags || !refs.workerSuggestion) return;
    const idleWorkers = state.workers.filter((worker) => worker.assigned.length === 0);
    const runningTasks = state.tasks.filter((task) => task.status === "running");
    const blockedTasks = state.tasks.filter((task) => task.status === "blocked");
    const selectedWorker = state.workers.find((worker) => worker.id === state.selectedWorker) || state.workers[0] || WORKERS[0];
    refs.workerSummary.innerHTML = [
      `空闲 worker <strong>${idleWorkers.length}</strong>`,
      `运行中 <strong>${runningTasks.length}</strong>`,
      `阻塞 <strong>${blockedTasks.length}</strong>`,
      `负责人 <strong>${state.workers.length}</strong>`,
    ].map((item) => `<span class="summary-chip">${item}</span>`).join("");
    if (refs.workerQuickSummary) {
      refs.workerQuickSummary.textContent = `当前共 ${state.workers.length} 名 worker，空闲 ${idleWorkers.length} 名，建议优先分配给空闲且评分更高的人选。`;
    }
    if (refs.workerFreeCount) refs.workerFreeCount.textContent = String(idleWorkers.length);
    if (refs.workerRunningCount) refs.workerRunningCount.textContent = String(runningTasks.length);
    if (refs.workerBlockedCount) refs.workerBlockedCount.textContent = String(blockedTasks.length);
    if (refs.workerOwnerCount) refs.workerOwnerCount.textContent = String(state.workers.length);
    refs.workerStatus.innerHTML = state.loading
      ? renderLoadingState("正在统计空闲 worker 与任务分布")
      : state.error
        ? renderErrorState(state.error)
        : `<span class="worker-panel__status-chip" data-state="${idleWorkers.length ? "空闲" : "忙碌"}">${escapeHtml(idleWorkers.length ? "空闲" : "忙碌")}</span><span class="worker-panel__status-text">当前共有 ${idleWorkers.length} 名空闲 worker，可优先分配到当前任务板。</span>`;
    refs.workerTags.innerHTML = state.workers.map((worker) => `
      <button class="worker-panel__chip ${worker.id === state.selectedWorker ? "is-active" : ""}" type="button" data-worker-tag="${escapeHtml(worker.id)}" aria-pressed="${worker.id === state.selectedWorker ? "true" : "false"}">
        ${escapeHtml(worker.name)} <strong>${worker.assigned.length}</strong>
      </button>
    `).join("");
    refs.workerSuggestion.textContent = selectedWorker
      ? `${selectedWorker.name} 当前 ${selectedWorker.assigned.length ? "有分配任务" : "处于空闲状态"}，建议优先处理 ${selectedWorker.taskTypes[0]}。`
      : "暂无可用 worker。";
    const filteredWorkers = getFilteredWorkers();
    refs.workerList.innerHTML = state.loading
      ? Array.from({ length: 2 }, () => renderWorkerSkeleton()).join("")
      : filteredWorkers.length
        ? filteredWorkers.map(renderWorkerCard).join("")
        : renderWorkerEmpty();
    bindWorkerButtons();
  }

  function loadWorkerPanel() { renderWorkerPanel(); }

  function getFilteredWorkers() {
    return state.workers.filter((worker) => {
      const idle = worker.assigned.length === 0;
      if (state.workerScope === "idle" && !idle) return false;
      if (state.workerScope === "running" && !worker.active.length) return false;
      if (state.workerScope === "blocked" && !worker.assigned.some((task) => task.status === "blocked")) return false;
      return true;
    });
  }

  function renderTasks() {
    if (!refs.taskList || !refs.taskState || !refs.taskSummary) return;
    const filtered = getFilteredTasks();
    refs.taskSummary.innerHTML = [
      `总计 <strong>${filtered.length}</strong>`,
      `运行中 <strong>${filtered.filter((task) => task.status === "running").length}</strong>`,
      `阻塞 <strong>${filtered.filter((task) => task.status === "blocked").length}</strong>`,
      `已完成 <strong>${filtered.filter((task) => task.status === "done").length}</strong>`,
      `今日新增 <strong>${filtered.filter((task) => task.today).length}</strong>`,
    ].map((item) => `<span class="summary-chip">${item}</span>`).join("");
    refs.taskState.classList.toggle("is-loading", state.loading);
    refs.taskState.classList.toggle("is-error", Boolean(state.error));
    refs.taskState.classList.toggle("is-empty", !state.loading && !state.error && filtered.length === 0);
    refs.taskState.innerHTML = state.loading
      ? renderLoadingState("正在获取任务板数据")
      : state.error
        ? renderErrorState(state.error)
        : `<article class="task-board__notice"><strong>筛选结果</strong><span>当前显示 ${filtered.length} 条任务，支持按负责人、工作区、状态和关键词即时筛选。</span></article>`;
    refs.taskList.innerHTML = state.loading
      ? Array.from({ length: 3 }, () => renderTaskSkeleton()).join("")
      : filtered.length
        ? filtered.map(renderTaskCard).join("")
        : renderEmptyState("暂无数据", "当前没有符合筛选条件的任务。", true);
    bindRetryActions();
  }

  function getFilteredTasks() {
    const assignee = String(refs.taskAssignee?.value || "").trim().toLowerCase();
    const workspace = String(refs.taskWorkspace?.value || "").trim().toLowerCase();
    const search = String(refs.taskSearch?.value || "").trim().toLowerCase();
    const todayOnly = Boolean(refs.taskToday?.checked);
    const status = getActiveStatus();
    return state.tasks.filter((task) => {
      const searchable = [task.id, task.title, task.description, task.assignee, task.status, task.workspace, task.priority]
        .filter(Boolean).join(" ").toLowerCase();
      return (!assignee || String(task.assignee || "").toLowerCase().includes(assignee))
        && (!workspace || String(task.workspace || "").toLowerCase().includes(workspace))
        && (!search || searchable.includes(search))
        && (!todayOnly || task.today)
        && (!status || task.status === status);
    });
  }

  function renderWorkerCard(worker) {
    return `
      <article class="worker-panel__card ${worker.id === state.selectedWorker ? "is-selected" : ""}">
        <div class="worker-panel__card-head">
          <div>
            <h3>${escapeHtml(worker.name)}</h3>
            <p>${escapeHtml(worker.title)}</p>
          </div>
          <span class="worker-panel__badge" data-state="${escapeHtml(worker.availability)}">${escapeHtml(worker.availability)}</span>
        </div>
        <p class="worker-panel__hint">${escapeHtml(worker.suggestion)}</p>
        <div class="worker-panel__bar" aria-hidden="true"><i style="width:${worker.score}%"></i></div>
        <dl class="worker-panel__meta">
          <div><dt>评分</dt><dd>${worker.score}</dd></div>
          <div><dt>负载</dt><dd>${worker.load}%</dd></div>
        </dl>
        <div class="worker-panel__skills">${worker.taskTypes.map((tag) => `<span class="worker-panel__tag">${escapeHtml(tag)}</span>`).join("")}</div>
        <div class="worker-panel__actions">
          <button class="btn btn-primary worker-panel__action" type="button" data-worker-select="${escapeHtml(worker.id)}">查看建议</button>
          <a class="btn btn-secondary worker-panel__action" href="#任务板">联动任务板</a>
        </div>
      </article>
    `;
  }

  function renderAssignmentCard(worker) {
    return `
      <article class="assignment-card">
        <div class="assignment-card__head">
          <div>
            <h4>${escapeHtml(worker.name)}</h4>
            <p>${escapeHtml(worker.taskTypes.join(" · "))}</p>
          </div>
          <span class="task-badge task-badge--muted">${escapeHtml(worker.availability)}</span>
        </div>
        <div class="assignment-card__meta">
          <span class="summary-chip">任务 ${worker.assigned.length}</span>
          <span class="summary-chip">建议 ${worker.taskTypes[0]}</span>
        </div>
        <div class="assignment-card__progress"><i style="width:${worker.score}%"></i></div>
      </article>
    `;
  }

  function renderRecommendationCard(worker, templates) {
    return `
      <article>
        <header class="worker-panel__card-head">
          <div>
            <h3>${escapeHtml(worker.name)}</h3>
            <p>${escapeHtml(worker.title)}</p>
          </div>
          <span class="worker-panel__badge" data-state="${escapeHtml(worker.availability)}">${escapeHtml(worker.availability)}</span>
        </header>
        <p class="worker-panel__hint">${escapeHtml(worker.suggestion)}</p>
        <div class="worker-panel__recommend-list">
          ${templates.map((item) => `
            <article class="worker-panel__recommend-item">
              <strong>${escapeHtml(item.title)}<span class="worker-panel__recommend-pill">${escapeHtml(item.priority)}</span></strong>
              <p>${escapeHtml(item.description)}</p>
            </article>
          `).join("")}
        </div>
      </article>
    `;
  }

  function renderLoadingState(message) {
    return `<div class="task-state loading"><div class="task-state__inline"><span class="spinner" aria-hidden="true"></span><h3>加载中</h3></div><p>${escapeHtml(message)}</p></div>`;
  }

  function renderErrorState(message) {
    const hint = isAuthError({ status: 401 }) ? "请先登录后重试。" : "请点击重试按钮。";
    return `<div class="task-state error"><div class="task-state__inline"><h3>加载失败</h3></div><p>${escapeHtml(message || hint)}</p><button class="btn btn-primary" type="button" data-task-retry>重试</button></div>`;
  }

  function renderEmptyState(title, description, includeReset = false) {
    return `<article class="task-empty-state" aria-label="${escapeHtml(title)}"><h3>${escapeHtml(title)}</h3><p>${escapeHtml(description)}</p>${includeReset ? '<div class="task-board__error-actions"><button class="btn btn-primary" type="button" data-task-retry>重试</button><button class="btn btn-secondary" type="button" data-task-reset-inline>重置筛选</button></div>' : ''}</article>`;
  }

  function renderWorkerEmpty() {
    return `<article class="worker-panel__empty" data-worker-empty><h3>暂无数据</h3><p>当前没有符合条件的 worker。</p></article>`;
  }

  function renderWorkerSkeleton() { return `<article class="worker-panel__skeleton"></article>`; }
  function renderTaskSkeleton() { return `<article class="worker-panel__skeleton"></article>`; }
  function renderSkeletonCard() { return `<article class="worker-panel__skeleton"></article>`; }

  function bindWorkerButtons() {
    refs.workerList?.querySelectorAll('[data-worker-select]').forEach((button) => button.addEventListener('click', () => {
      state.selectedWorker = button.dataset.workerSelect || state.selectedWorker;
      renderWorkerPanel();
      saveState();
    }));
    refs.workerTags?.querySelectorAll('[data-worker-tag]').forEach((button) => button.addEventListener('click', () => {
      state.selectedWorker = button.dataset.workerTag || state.selectedWorker;
      renderWorkerPanel();
      saveState();
    }));
  }

  function bindRetryActions() {
    document.querySelectorAll('[data-task-retry]').forEach((button) => button.addEventListener('click', loadTasks));
    document.querySelectorAll('[data-task-reset-inline]').forEach((button) => button.addEventListener('click', handleResetFilters));
  }

  function handleFilterChange() {
    saveState();
    renderTasks();
  }

  function handleResetFilters() {
    if (refs.taskSearch) refs.taskSearch.value = "";
    if (refs.taskAssignee) refs.taskAssignee.value = "";
    if (refs.taskWorkspace) refs.taskWorkspace.value = "";
    if (refs.taskToday) refs.taskToday.checked = false;
    setActiveStatus("");
    saveState();
    renderTasks();
  }

  function handleStatusClick(event) {
    const status = event.currentTarget?.dataset.taskStatus || "";
    setActiveStatus(getActiveStatus() === status ? "" : status);
    saveState();
    renderTasks();
  }

  function setActiveStatus(status) {
    refs.statusButtons.forEach((button) => {
      const active = button.dataset.taskStatus === status;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-pressed", active ? "true" : "false");
    });
    state.status = status;
  }

  function getActiveStatus() {
    return state.status || "";
  }

  function handleWorkerScopeChange(event) {
    state.workerScope = event.currentTarget?.dataset.workerScope || "all";
    setActiveWorkerScope(state.workerScope);
    renderWorkerPanel();
    saveState();
  }

  function setActiveWorkerScope(scope) {
    refs.workerScopes.forEach((button) => {
      const active = (button.dataset.workerScope || "all") === scope;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-pressed", active ? "true" : "false");
    });
  }

  function normalizeStatus(value) {
    const raw = String(value || "").toLowerCase();
    if (["running", "doing"].includes(raw)) return "running";
    if (["blocked", "block"].includes(raw)) return "blocked";
    if (["done", "completed"].includes(raw)) return "done";
    return raw || "running";
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
