(() => {
  "use strict";

  const API_BASE = "/api/v1";
  const TASK_QUEUE_PATH = `${API_BASE}/task-queue/tasks`;
  const WORKER_ENDPOINTS = ["frontend-dev", "backend-dev", "devops-engineer", "reviewer"];
  const WORKER_LABELS = {
    "frontend-dev": "前端空闲 worker",
    "backend-dev": "后端协作 worker",
    "devops-engineer": "运维保障 worker",
    reviewer: "验收复核 worker",
  };
  const WORKER_SKILLS = {
    "frontend-dev": ["页面搭建", "响应式布局", "交互补全"],
    "backend-dev": ["接口对齐", "字段校验", "数据聚合"],
    "devops-engineer": ["部署检查", "服务探活", "环境配置"],
    reviewer: ["验收复核", "交互检查", "回归测试"],
  };
  const WORKER_REASONS = {
    "frontend-dev": "前端 worker 当前最适合承接新建页面、表单布局和移动端细节任务。",
    "backend-dev": "后端 worker 适合接收字段格式、接口返回和持久化相关任务。",
    "devops-engineer": "运维 worker 适合接收需要环境检查、服务探活的任务。",
    reviewer: "reviewer 适合接收验收、回归和交互检查任务。",
  };
  const PRIORITY_OPTIONS = [
    { value: "urgent", label: "紧急" },
    { value: "high", label: "高" },
    { value: "medium", label: "中" },
    { value: "low", label: "低" },
  ];
  const STATUS_OPTIONS = [
    { value: "ready", label: "待领取" },
    { value: "running", label: "进行中" },
    { value: "blocked", label: "阻塞" },
    { value: "done", label: "已完成" },
  ];

  const state = {
    loading: true,
    error: "",
    tasks: [],
    selectedWorker: "frontend-dev",
    workspace: "dir",
  };

  const refs = {};

  document.addEventListener("DOMContentLoaded", initTaskCreateQuickForm);

  function initTaskCreateQuickForm() {
    cacheElements();
    if (!refs.root) return;
    bindEvents();
    renderOptions();
    fetchTasks();
  }

  function cacheElements() {
    refs.root = document.querySelector("[data-task-create-quick]");
    refs.form = document.querySelector("[data-task-create-form]");
    refs.state = document.querySelector("[data-task-create-state]");
    refs.summary = document.querySelector("[data-task-create-summary]");
    refs.suggestions = document.querySelector("[data-task-create-suggestions]");
    refs.workerList = document.querySelector("[data-task-create-worker-list]");
    refs.title = document.querySelector("[data-task-create-title]");
    refs.description = document.querySelector("[data-task-create-description]");
    refs.assignee = document.querySelector("[data-task-create-assignee]");
    refs.priority = document.querySelector("[data-task-create-priority]");
    refs.status = document.querySelector("[data-task-create-status]");
    refs.workspace = document.querySelector("[data-task-create-workspace]");
    refs.dependencies = document.querySelector("[data-task-create-dependencies]");
    refs.submit = document.querySelector("[data-task-create-submit]");
    refs.reset = document.querySelector("[data-task-create-reset]");
    refs.refresh = document.querySelector("[data-task-create-refresh]");
    refs.retry = document.querySelector("[data-task-create-retry]");
    refs.result = document.querySelector("[data-task-create-result]");
    refs.count = document.querySelector("[data-task-create-count]");
  }

  function bindEvents() {
    refs.form?.addEventListener("submit", handleSubmit);
    refs.reset?.addEventListener("click", handleReset);
    refs.refresh?.addEventListener("click", fetchTasks);
    refs.retry?.addEventListener("click", fetchTasks);
    refs.workerList?.addEventListener("click", handleWorkerPick);
    refs.title?.addEventListener("input", renderPreview);
    refs.description?.addEventListener("input", renderPreview);
    refs.assignee?.addEventListener("change", renderPreview);
    refs.priority?.addEventListener("change", renderPreview);
    refs.status?.addEventListener("change", renderPreview);
    refs.workspace?.addEventListener("change", renderPreview);
  }

  function renderOptions() {
    if (refs.priority && !refs.priority.options.length) {
      refs.priority.innerHTML = PRIORITY_OPTIONS.map((option) => `<option value="${option.value}">${option.label}</option>`).join("");
    }
    if (refs.status && !refs.status.options.length) {
      refs.status.innerHTML = STATUS_OPTIONS.map((option) => `<option value="${option.value}">${option.label}</option>`).join("");
    }
  }

  async function fetchTasks() {
    setState("loading", "正在读取任务队列与空闲 worker。", true);
    try {
      const response = await fetch(TASK_QUEUE_PATH, { headers: { Accept: "application/json" } });
      if (!response.ok) throw new Error(`任务队列请求失败：${response.status}`);
      const payload = await response.json();
      state.tasks = normalizeTasks(payload);
      state.error = "";
      state.loading = false;
      renderAll();
    } catch (error) {
      state.loading = false;
      state.error = "网络错误，已显示本地示例推荐。";
      state.tasks = buildFallbackTasks();
      renderAll();
    }
  }

  function normalizeTasks(payload) {
    const list = Array.isArray(payload) ? payload : Array.isArray(payload?.items) ? payload.items : Array.isArray(payload?.data) ? payload.data : Array.isArray(payload?.tasks) ? payload.tasks : [];
    return list.map((task, index) => ({
      id: task.id || task.task_id || `task-${index + 1}`,
      title: task.title || task.name || "未命名任务",
      assignee: task.assignee || task.owner || task.profile || "未分配",
      status: String(task.status || "ready").toLowerCase(),
      workspace: task.workspace_kind || task.workspace || task.workspaceType || "dir",
      description: task.description || task.summary || "",
      priority: task.priority || task.priority_level || "medium",
    }));
  }

  function buildFallbackTasks() {
    return [
      { id: "task-1", title: "补齐任务创建页交互状态", assignee: "frontend-dev", status: "running", workspace: "dir", description: "在 375px 宽度下补齐按钮三态与错误态。", priority: "high" },
      { id: "task-2", title: "校验任务队列字段", assignee: "backend-dev", status: "ready", workspace: "dir", description: "确保接口返回 title、assignee、workspace 与 status。", priority: "medium" },
      { id: "task-3", title: "预览服务探活", assignee: "devops-engineer", status: "blocked", workspace: "worktree", description: "检查本地静态服务与后端 API 的连通性。", priority: "low" },
      { id: "task-4", title: "验收任务创建流程", assignee: "reviewer", status: "done", workspace: "dir", description: "确认中文表单与推荐建议都可用。", priority: "high" },
    ];
  }

  function renderAll() {
    renderState();
    renderSummary();
    renderWorkerList();
    renderPreview();
  }

  function setState(message, errorMessage, canRetry) {
    if (!refs.state) return;
    refs.state.innerHTML = `
      <div class="task-create__status ${state.loading ? "is-loading" : state.error ? "is-error" : "is-ready"}">
        <div class="activity-state__inline">
          ${state.loading ? '<span class="spinner" aria-hidden="true"></span>' : ""}
          <h3>${state.loading ? "加载中" : state.error ? "加载失败" : "已就绪"}</h3>
        </div>
        <p>${escapeHtml(message || errorMessage || "")}</p>
        ${canRetry ? '<button class="btn btn-primary" type="button" data-task-create-retry>重试</button>' : ""}
      </div>
    `;
    refs.state.querySelector("[data-task-create-retry]")?.addEventListener("click", fetchTasks);
  }

  function renderState() {
    const message = state.loading ? "正在读取任务队列并生成推荐对象。" : state.error || "任务队列已同步完成，可直接创建任务。";
    setState(message, message, state.error ? true : false);
    if (refs.count) refs.count.textContent = state.loading ? "同步中" : `推荐 ${state.tasks.length ? Math.min(2, buildRecommendedWorkers().length) : 2} 个对象`;
  }

  function renderSummary() {
    if (!refs.summary) return;
    const recommended = buildRecommendedWorkers().slice(0, 2);
    const chips = [
      `任务数 ${state.tasks.length}`,
      `首选 ${recommended[0]?.id || "frontend-dev"}`,
      `备选 ${recommended[1]?.id || "backend-dev"}`,
      state.error ? "本地推荐模式" : "实时接口模式",
    ];
    refs.summary.innerHTML = chips.map((text) => `<span class="summary-chip">${escapeHtml(text)}</span>`).join("");
  }

  function renderWorkerList() {
    if (!refs.workerList) return;
    const recommended = buildRecommendedWorkers().slice(0, 2);
    refs.workerList.innerHTML = recommended.map((worker, index) => `
      <button class="task-create__worker ${worker.id === state.selectedWorker ? "is-active" : ""}" type="button" data-task-create-worker="${escapeHtml(worker.id)}">
        <strong>${escapeHtml(worker.label)}</strong>
        <span>${escapeHtml(worker.reason)}</span>
        <small>${escapeHtml(worker.skills.join(" · "))}</small>
        <small>推荐等级 ${index === 0 ? "#1" : "#2"}</small>
      </button>
    `).join("");
  }

  function renderPreview() {
    if (!refs.suggestions) return;
    const title = getTitle();
    const assignee = getAssignee();
    const workspace = getWorkspace();
    const priority = getPriority();
    refs.suggestions.innerHTML = `
      <h4>自动建议</h4>
      <ol>
        <li>推荐创建给 <strong>${escapeHtml(assignee)}</strong>，因为当前空闲 worker 中它最适合接手这类任务。</li>
        <li>工作区建议选择 <strong>${escapeHtml(workspace)}</strong>，适合直接在当前仓库落地前端页面。</li>
        <li>建议优先级设为 <strong>${escapeHtml(priority)}</strong>，并保持标题简洁明确。</li>
      </ol>
    `;
    if (refs.result) {
      refs.result.innerHTML = `
        <span class="summary-chip">标题：${escapeHtml(title || "待填写")}</span>
        <span class="summary-chip">负责人：${escapeHtml(assignee)}</span>
        <span class="summary-chip">工作区：${escapeHtml(workspace)}</span>
        <span class="summary-chip">优先级：${escapeHtml(priority)}</span>
      `;
    }
  }

  function handleWorkerPick(event) {
    const button = event.target.closest("[data-task-create-worker]");
    if (!button) return;
    state.selectedWorker = button.dataset.taskCreateWorker || "frontend-dev";
    if (refs.assignee) refs.assignee.value = state.selectedWorker;
    renderWorkerList();
    renderPreview();
  }

  function handleReset() {
    refs.form?.reset();
    state.selectedWorker = "frontend-dev";
    if (refs.assignee) refs.assignee.value = state.selectedWorker;
    if (refs.workspace) refs.workspace.value = "dir";
    renderWorkerList();
    renderPreview();
    setFeedback("已清空表单，可重新填写。", "");
  }

  function handleSubmit(event) {
    event.preventDefault();
    const errors = validate();
    if (errors.length) {
      setFeedback("请先修正表单错误。", errors.join("；"), true);
      return;
    }
    const payload = buildPayload();
    setFeedback("表单已校验完成，已准备提交。", `标题：${payload.title}；负责人：${payload.assignee}；工作区：${payload.workspace}`, false);
  }

  function validate() {
    const errors = [];
    if (!getTitle()) errors.push("请输入任务标题");
    if (!getDescription()) errors.push("请输入任务描述");
    if (!getAssignee()) errors.push("请选择负责人");
    if (!getWorkspace()) errors.push("请选择工作区");
    return errors;
  }

  function buildPayload() {
    return {
      title: getTitle(),
      description: getDescription(),
      assignee: getAssignee(),
      workspace: getWorkspace(),
      priority: getPriority(),
      status: getStatus(),
      dependencies: String(refs.dependencies?.value || "").trim(),
    };
  }

  function getTitle() {
    return String(refs.title?.value || "").trim();
  }

  function getDescription() {
    return String(refs.description?.value || "").trim();
  }

  function getAssignee() {
    return String(refs.assignee?.value || state.selectedWorker || "frontend-dev").trim();
  }

  function getPriority() {
    return String(refs.priority?.value || "high");
  }

  function getStatus() {
    return String(refs.status?.value || "ready");
  }

  function getWorkspace() {
    return String(refs.workspace?.value || state.workspace || "dir");
  }

  function buildRecommendedWorkers() {
    const scored = WORKER_ENDPOINTS.map((id) => {
      const assigneeCount = state.tasks.filter((task) => task.assignee === id && task.status !== "done").length;
      const doneCount = state.tasks.filter((task) => task.assignee === id && task.status === "done").length;
      return {
        id,
        label: WORKER_LABELS[id],
        reason: WORKER_REASONS[id],
        skills: WORKER_SKILLS[id],
        score: (doneCount * 2) - assigneeCount,
      };
    });
    return scored.sort((a, b) => b.score - a.score || a.id.localeCompare(b.id, "zh-CN"));
  }

  function setFeedback(title, message, isError) {
    if (!refs.result) return;
    refs.result.innerHTML = `
      <span class="summary-chip">${escapeHtml(title)}</span>
      <span class="summary-chip ${isError ? "task-create__feedback is-error" : "task-create__feedback is-success"}">${escapeHtml(message)}</span>
    `;
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
