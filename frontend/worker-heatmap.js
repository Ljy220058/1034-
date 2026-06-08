(()=>{
  "use strict";

  const API_BASE = "/api/v1";
  const TASK_ENDPOINT = "/api/v1/task-queue/tasks";
  const STORAGE_KEY = "1034.worker-heatmap.filters.v1";
  const AUTH_TOKEN_KEYS = ["access_token", "accessToken", "token", "authToken", "workerAccessToken"];
  const STATUS_KEYS = ["ready", "running", "blocked", "done", "archived"];
  const STATUS_LABELS = { ready: "ready", running: "running", blocked: "blocked", done: "done", archived: "archived" };
  const FALLBACK_PROFILES = ["frontend-dev", "backend-dev", "devops-engineer"];

  const state = { loading: true, error: "", workers: [], tasks: [], selectedWorker: "frontend-dev", workerScope: "all", updatedAt: 0 };
  const refs = {};
  document.addEventListener("DOMContentLoaded", initApp);

  function initApp() { cacheRefs(); bindEvents(); restoreState(); loadHeatmapData(); }
  function cacheRefs() {
    refs.summary = document.querySelector("[data-worker-summary]");
    refs.status = document.querySelector("[data-worker-status]");
    refs.freeCount = document.querySelector("[data-worker-free-count]");
    refs.runningCount = document.querySelector("[data-worker-running-count]");
    refs.todoCount = document.querySelector("[data-worker-blocked-count]");
    refs.ownerCount = document.querySelector("[data-worker-owner-count]");
    refs.list = document.querySelector("[data-worker-list]");
    refs.search = document.querySelector("[data-worker-search]");
    refs.refresh = Array.from(document.querySelectorAll("[data-worker-refresh]"));
    refs.scopes = Array.from(document.querySelectorAll("[data-worker-scope]"));
    refs.jump = Array.from(document.querySelectorAll("[data-worker-jump]"));
    refs.recoCount = document.querySelector("[data-reco-count]");
    refs.updated = document.querySelector("[data-worker-updated]");
    refs.suggestion = document.querySelector("[data-worker-suggestion]");
  }
  function bindEvents() {
    refs.refresh.forEach((button) => button.addEventListener("click", loadHeatmapData));
    refs.scopes.forEach((button) => button.addEventListener("click", handleScopeChange));
    refs.search?.addEventListener("input", handleFilterChange);
    refs.jump.forEach((button) => button.addEventListener("click", () => document.getElementById(button.dataset.workerJump || "数据接入")?.scrollIntoView({ behavior: "smooth", block: "start" })));
  }
  function restoreState() {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
      if (!saved) return;
      if (refs.search) refs.search.value = saved.search || "";
      state.workerScope = saved.workerScope || "all";
      state.selectedWorker = saved.selectedWorker || state.selectedWorker;
      setActiveScope(state.workerScope);
    } catch { state.error = "本地筛选记录恢复失败"; }
  }
  function saveState() { localStorage.setItem(STORAGE_KEY, JSON.stringify({ search: refs.search?.value || "", workerScope: state.workerScope, selectedWorker: state.selectedWorker })); }
  async function loadHeatmapData() {
    state.loading = true; state.error = ""; renderAll(); setRefreshDisabled(true);
    try {
      const tasks = await fetchTasks();
      state.tasks = tasks;
      state.workers = buildWorkerHeatmap(tasks);
      state.updatedAt = Date.now();
    } catch (error) {
      if (isAuthError(error)) {
        state.tasks = [];
        state.workers = buildWorkerHeatmap([]);
        state.error = "未登录或权限不足，无法读取任务队列数据。请先登录后重试。";
      } else {
        state.error = "任务队列接口暂时不可用，请检查后端服务后重试。";
        state.tasks = buildFallbackTasks();
        state.workers = buildWorkerHeatmap(state.tasks);
      }
      state.updatedAt = Date.now();
    } finally {
      state.loading = false;
      setRefreshDisabled(false);
      if (!state.workers.some((worker) => worker.id === state.selectedWorker)) state.selectedWorker = state.workers[0]?.id || "";
      renderAll(); saveState();
    }
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

  function fetchTasks() {
    return fetch(TASK_ENDPOINT, { headers: createAuthHeaders() }).then(async (response) => {
      if (!response.ok) {
        const error = new Error(`HTTP ${response.status}`);
        error.status = response.status;
        throw error;
      }
      return normalizeTaskList(await response.json());
    });
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
      { id: "t-front-running", title: "空闲热力图页面", description: "前端页面正在实现与验证。", assignee: "frontend-dev", status: "running", priority: "高", workspace: "dir" },
      { id: "t-front-done", title: "移动端筛选条", description: "已完成响应式筛选条。", assignee: "frontend-dev", status: "done", priority: "中", workspace: "dir" },
      { id: "t-back-todo", title: "任务队列字段确认", description: "待确认接口字段稳定性。", assignee: "backend-dev", status: "todo", priority: "中", workspace: "dir" },
      { id: "t-back-triage", title: "聚合接口评估", description: "等待分诊是否需要后端聚合。", assignee: "backend-dev", status: "triage", priority: "低", workspace: "dir" },
      { id: "t-devops-done", title: "预览服务检查", description: "静态服务可正常访问。", assignee: "devops-engineer", status: "done", priority: "低", workspace: "scratch" },
    ];
  }
  function buildWorkerHeatmap(tasks) {
    const names = new Set([...FALLBACK_PROFILES, ...tasks.map((task) => task.assignee).filter(Boolean)]);
    return Array.from(names).map((profile) => {
      const assigned = tasks.filter((task) => task.assignee === profile);
      const counts = STATUS_KEYS.reduce((acc, key) => ({ ...acc, [key]: assigned.filter((task) => task.status === key).length }), {});
      const load = calculateLoad(counts);
      return { id: profile, name: profile, title: profile === "未分配" ? "待认领 profile" : "Kanban profile", counts, assigned, load, loadState: getLoadState(load), heat: getHeatLevel(load), suggestion: buildSuggestion(profile, counts, load) };
    }).sort(sortWorkersByScope);
  }
  function calculateLoad(counts) { const active = counts.running * 2 + counts.ready + counts.blocked; const total = counts.done + counts.running + counts.ready + counts.blocked + counts.archived; return total ? Math.min(100, Math.round((active / Math.max(1, total + 1)) * 100)) : 0; }
  function getLoadState(load) { if (load >= 70) return "高负载"; if (load >= 35) return "中负载"; return "空闲"; }
  function getHeatLevel(load) { if (load >= 70) return "hot"; if (load >= 35) return "warm"; return "idle"; }
  function buildSuggestion(profile, counts, load) {
    if (load === 0) return `${profile} 当前无活跃任务，是新增任务的优先候选。`;
    if (counts.running) return `${profile} 正在处理 ${counts.running} 个任务，建议先观察 running 队列。`;
    if (counts.blocked) return `${profile} 有 ${counts.blocked} 个阻塞任务，建议优先清理依赖。`;
    if (counts.ready) return `${profile} 有 ${counts.ready} 个 ready 任务，适合直接领取推进。`;
    if (counts.archived) return `${profile} 近期有归档任务，可继续关注收尾结果。`;
    return `${profile} 近期以已完成任务为主，可承接轻量补充任务。`;
  }
  function sortWorkersByScope(a, b) {
    if (state.workerScope === "idle") return a.load - b.load;
    if (state.workerScope === "hot") return b.load - a.load || a.name.localeCompare(b.name);
    if (state.workerScope === "running") return b.counts.running - a.counts.running || b.load - a.load;
    if (state.workerScope === "ready") return b.counts.ready - a.counts.ready || b.load - a.load;
    if (state.workerScope === "blocked") return b.counts.blocked - a.counts.blocked || b.load - a.load;
    if (state.workerScope === "archived") return b.counts.archived - a.counts.archived || b.load - a.load;
    return a.load - b.load || a.name.localeCompare(b.name);
  }
  function renderAll() { renderSummary(); renderStatus(); renderSuggestion(); renderWorkerCards(); bindWorkerButtons(); }
  function renderSummary() {
    const idleWorkers = state.workers.filter((worker) => worker.load === 0);
    const runningTasks = state.tasks.filter((task) => task.status === "running");
    const readyTasks = state.tasks.filter((task) => task.status === "ready");
    const blockedTasks = state.tasks.filter((task) => task.status === "blocked");
    const archivedTasks = state.tasks.filter((task) => task.status === "archived");
    refs.summary.innerHTML = [`profile <strong>${state.workers.length}</strong>`, `空闲 <strong>${idleWorkers.length}</strong>`, `running <strong>${runningTasks.length}</strong>`, `ready <strong>${readyTasks.length}</strong>`, `blocked <strong>${blockedTasks.length}</strong>`, `archived <strong>${archivedTasks.length}</strong>`].map((item) => `<span class="summary-chip">${item}</span>`).join("");
    if (refs.freeCount) refs.freeCount.textContent = String(idleWorkers.length);
    if (refs.runningCount) refs.runningCount.textContent = String(runningTasks.length);
    if (refs.todoCount) refs.todoCount.textContent = String(readyTasks.length + blockedTasks.length + archivedTasks.length);
    if (refs.ownerCount) refs.ownerCount.textContent = String(state.tasks.length);
    if (refs.recoCount) refs.recoCount.textContent = `已接入 ${state.workers.length} 个 profile`;
    if (refs.updated) refs.updated.textContent = state.updatedAt ? `最后刷新 ${formatTime(state.updatedAt)}` : "最后刷新 --";
  }
  function renderStatus() {
    if (state.loading) { refs.status.innerHTML = `<span class="worker-panel__status-chip" data-state="加载中">加载中</span><span class="spinner" aria-hidden="true"></span><span class="worker-panel__status-text">正在读取 Kanban 数据并生成 profile 热力图。</span>`; return; }
    if (state.error) { refs.status.innerHTML = `<span class="worker-panel__status-chip" data-state="错误">网络错误</span><span class="worker-panel__status-text">${escapeHtml(state.error)}</span>`; return; }
    const best = state.workers[0];
    refs.status.innerHTML = `<span class="worker-panel__status-chip" data-state="${best?.loadState || "空闲"}">${escapeHtml(best?.loadState || "空闲")}</span><span class="worker-panel__status-text">当前最空闲 profile：${escapeHtml(best?.name || "暂无")}，负载 ${best?.load || 0}%。</span>`;
  }
  function renderSuggestion() { const selectedWorker = state.workers.find((worker) => worker.id === state.selectedWorker) || state.workers[0]; refs.suggestion.textContent = selectedWorker ? selectedWorker.suggestion : "暂无可用 profile。"; }
  function renderWorkerCards() {
    if (state.loading) { refs.list.innerHTML = Array.from({ length: 3 }, renderSkeletonCard).join(""); return; }
    if (state.error) { refs.list.innerHTML = `<article class="panel-error"><h3>加载失败</h3><p>${escapeHtml(state.error)}</p><div class="worker-panel__error-actions"><button class="btn btn-primary" type="button" data-worker-retry>重试</button></div></article>`; refs.list.querySelector("[data-worker-retry]")?.addEventListener("click", loadHeatmapData); return; }
    const filtered = getFilteredWorkers();
    refs.list.innerHTML = filtered.length ? filtered.map(renderWorkerCard).join("") : `<article class="panel-empty"><h3>暂无数据</h3><p>当前没有符合条件的 profile。</p></article>`;
  }
  function getFilteredWorkers() {
    const search = String(refs.search?.value || "").trim().toLowerCase();
    return state.workers.filter((worker) => {
      if (state.workerScope === "idle" && worker.load > 0) return false;
      const searchable = [worker.name, worker.title, worker.loadState, worker.suggestion].join(" ").toLowerCase();
      return !search || searchable.includes(search);
    }).sort(sortWorkersByScope);
  }
  function renderWorkerCard(worker) {
    return `
      <article class="worker-panel__card ${worker.id === state.selectedWorker ? "is-selected" : ""}" data-heat="${escapeHtml(worker.heat)}">
        <header class="worker-panel__card-head"><div><h3>${escapeHtml(worker.name)}</h3><p class="worker-panel__hint">${escapeHtml(worker.title)}</p></div><span class="worker-panel__badge" data-state="${escapeHtml(worker.loadState)}">${escapeHtml(worker.loadState)}</span></header>
        <p class="worker-panel__hint">${escapeHtml(worker.suggestion)}</p>
        <section aria-label="负载热力"><p class="worker-panel__load-label"><span>负载热力</span><strong>${worker.load}%</strong></p><div class="worker-panel__heatbar" aria-hidden="true"><i style="width:${worker.load}%"></i></div></section>
        <dl class="worker-panel__counts" aria-label="${escapeHtml(worker.name)} 状态统计">${STATUS_KEYS.map((key) => `<div><dt>${STATUS_LABELS[key]}</dt><dd>${worker.counts[key]}</dd></div>`).join("")}</dl>
        <section class="worker-panel__actions"><button class="btn btn-primary worker-panel__action" type="button" data-worker-select="${escapeHtml(worker.id)}">查看建议</button><a class="btn btn-secondary worker-panel__action" href="#数据接入">接入说明</a></section>
      </article>`;
  }
  function renderSkeletonCard() { return `<article class="panel-skeleton" aria-hidden="true"><span class="skeleton-line tall"></span><span class="skeleton-line mid"></span><span class="skeleton-line short"></span></article>`; }
  function bindWorkerButtons() { refs.list?.querySelectorAll("[data-worker-select]").forEach((button) => button.addEventListener("click", () => { state.selectedWorker = button.dataset.workerSelect || state.selectedWorker; renderAll(); saveState(); })); }
  function handleFilterChange() { saveState(); renderWorkerCards(); renderSuggestion(); bindWorkerButtons(); }
  function handleScopeChange(event) { state.workerScope = event.currentTarget?.dataset.workerScope || "all"; setActiveScope(state.workerScope); renderWorkerCards(); saveState(); bindWorkerButtons(); }
  function setActiveScope(scope) { refs.scopes.forEach((button) => { const active = (button.dataset.workerScope || "all") === scope; button.classList.toggle("is-active", active); button.setAttribute("aria-pressed", active ? "true" : "false"); }); }
  function setRefreshDisabled(disabled) { refs.refresh.forEach((button) => { button.disabled = disabled; button.textContent = disabled ? "刷新中..." : (button.classList.contains("btn-primary") ? "重新加载" : "一键刷新"); }); }
  function normalizeStatus(value) {
    const raw = String(value || "").toLowerCase();
    if (["running", "doing", "in_progress"].includes(raw)) return "running";
    if (["ready", "pending"].includes(raw)) return "ready";
    if (["blocked", "block"].includes(raw)) return "blocked";
    if (["archived", "archive"].includes(raw)) return "archived";
    if (["done", "completed", "complete"].includes(raw)) return "done";
    if (["todo", "triage", "new"].includes(raw)) return "ready";
    return "ready";
  }
  function formatTime(timestamp) {
    return new Intl.DateTimeFormat("zh-CN", { hour: "2-digit", minute: "2-digit", second: "2-digit" }).format(new Date(timestamp));
  }
  function escapeHtml(value) { return String(value).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#39;"); }
})();
