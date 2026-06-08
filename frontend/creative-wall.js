(()=>{
  "use strict";

  const STORAGE_KEY = "1034.creative-wall.filters.v2";

  const WORKER_PRESETS = [
    {
      id: "frontend-dev",
      name: "frontend-dev",
      title: "前端空闲 worker",
      type: "前端协作",
      statusText: "空闲",
      heat: "idle",
      capability: ["页面搭建", "交互补全", "移动端优化"],
      bio: "适合接轻量界面、卡片布局与状态补全类任务。",
    },
    {
      id: "backend-dev",
      name: "backend-dev",
      title: "后端协作 worker",
      type: "接口联调",
      statusText: "忙碌",
      heat: "warm",
      capability: ["字段对齐", "数据聚合", "接口排查"],
      bio: "适合补齐接口字段、整理列表响应与联调说明。",
    },
    {
      id: "reviewer",
      name: "reviewer",
      title: "评审支援 worker",
      type: "质量复核",
      statusText: "待命",
      heat: "idle",
      capability: ["文案校对", "状态走查", "交付复核"],
      bio: "适合处理交付前检查、文案统一与体验复核。",
    },
    {
      id: "devops-engineer",
      name: "devops-engineer",
      title: "运维调度 worker",
      type: "环境保障",
      statusText: "高负载",
      heat: "hot",
      capability: ["服务探活", "环境检查", "发布保障"],
      bio: "适合排查环境可用性、静态服务与部署链路问题。",
    },
  ];

  const FALLBACK_CARDS = [
    {
      id: "idea-ui-001",
      title: "整理看板空态文案",
      description: "补齐“暂无数据 / 重试 / 加载中”文案，让空闲 worker 接手时直接可交付。",
      workerType: "前端协作",
      assigneeHint: "frontend-dev",
      priority: "高优先级",
      status: "待承接",
      tone: "idle",
      tags: ["空态", "文案统一", "移动端"],
      reason: "适合用较少改动快速提升页面完成度。",
    },
    {
      id: "idea-api-002",
      title: "补齐接口字段映射说明",
      description: "梳理任务列表返回中的 title、assignee、status、workspace 字段映射，便于前后端对齐。",
      workerType: "接口联调",
      assigneeHint: "backend-dev",
      priority: "中优先级",
      status: "可排期",
      tone: "warm",
      tags: ["字段校验", "接口说明", "联调"],
      reason: "适合后端协作 worker 快速处理字段稳定性。",
    },
    {
      id: "idea-review-003",
      title: "走查按钮交互状态",
      description: "集中检查 hover、active、disabled、loading 四态，确保交付前体验一致。",
      workerType: "质量复核",
      assigneeHint: "reviewer",
      priority: "普通优先级",
      status: "待确认",
      tone: "idle",
      tags: ["状态检查", "交互", "验收"],
      reason: "适合评审支援 worker 做最后一轮中文体验复核。",
    },
    {
      id: "idea-ops-004",
      title: "确认静态预览服务可访问",
      description: "检查静态服务与后端联调链路是否可用，避免前端页面可见但接口不可达。",
      workerType: "环境保障",
      assigneeHint: "devops-engineer",
      priority: "普通优先级",
      status: "需环境确认",
      tone: "hot",
      tags: ["预览服务", "环境", "联调"],
      reason: "适合运维 worker 在高负载前做一次环境探活。",
    },
  ];

  const state = {
    loading: true,
    dispatchingId: "",
    error: "",
    workers: structuredClone(WORKER_PRESETS),
    cards: [],
    selectedType: "all",
    selectedWorkerId: "",
    source: "fallback",
    dispatchResult: null,
  };

  const refs = {};

  document.addEventListener("DOMContentLoaded", initCreativeWall);

  function initCreativeWall() {
    cacheRefs();
    if (!refs.panel) return;
    bindEvents();
    restoreState();
    loadCreativeWall();
  }

  function cacheRefs() {
    refs.panel = document.querySelector("[data-creative-wall]");
    refs.state = document.querySelector("[data-creative-state]");
    refs.summary = document.querySelector("[data-creative-summary]");
    refs.workerList = document.querySelector("[data-creative-workers]");
    refs.cardGrid = document.querySelector("[data-creative-cards]");
    refs.retryButtons = Array.from(document.querySelectorAll("[data-creative-refresh]"));
    refs.reset = document.querySelector("[data-creative-reset]");
    refs.typeButtons = Array.from(document.querySelectorAll("[data-creative-type]"));
    refs.highlightName = document.querySelector("[data-creative-highlight-name]");
    refs.highlightText = document.querySelector("[data-creative-highlight-text]");
    refs.highlightMeta = document.querySelector("[data-creative-highlight-meta]");
    refs.idleCount = document.querySelector("[data-creative-idle-count]");
    refs.cardCount = document.querySelector("[data-creative-card-count]");
  }

  function bindEvents() {
    refs.retryButtons.forEach((button) => button.addEventListener("click", loadCreativeWall));
    refs.reset?.addEventListener("click", handleResetCreativeWall);
    refs.typeButtons.forEach((button) => button.addEventListener("click", handleTypeChange));
  }

  function restoreState() {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
      if (!saved) return;
      state.selectedType = saved.selectedType || "all";
      state.selectedWorkerId = saved.selectedWorkerId || "";
    } catch {
      state.selectedType = "all";
      state.selectedWorkerId = "";
    }
    updateTypeButtons();
  }

  function saveState() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({
      selectedType: state.selectedType,
      selectedWorkerId: state.selectedWorkerId,
    }));
  }

  async function loadCreativeWall() {
    state.loading = true;
    state.error = "";
    state.dispatchResult = null;
    renderCreativeWall();
    try {
      const [tasks, workerDirectory] = await Promise.all([
        fetchTaskQueue(),
        fetchWorkerDirectory(),
      ]);
      state.workers = buildWorkers(tasks, workerDirectory);
      state.cards = buildCreativeCards(tasks, state.workers);
      state.source = "api";
    } catch (error) {
      state.error = buildErrorMessage(error);
      state.workers = buildWorkers([], []);
      state.cards = structuredClone(FALLBACK_CARDS);
      state.source = "fallback";
    } finally {
      if (!state.selectedWorkerId || !state.workers.some((worker) => worker.id === state.selectedWorkerId)) {
        state.selectedWorkerId = getPreferredWorkerId(state.workers);
      }
      state.loading = false;
      renderCreativeWall();
      saveState();
    }
  }

  function fetchTaskQueue() {
    return window.apiClient?.fetchTaskQueue?.({ auth: true }) || Promise.resolve([]);
  }

  function fetchWorkerDirectory() {
    return window.apiClient?.fetchWorkerDirectory?.({ auth: true }) || Promise.resolve([]);
  }

  function buildWorkers(tasks, workerDirectory) {
    const merged = mergeWorkerDirectory(workerDirectory);
    return merged.map((worker) => {
      const assigned = tasks.filter((task) => task.assignee === worker.id);
      const runningCount = assigned.filter((task) => normalizeStatus(task.status) === "进行中").length;
      const blockedCount = assigned.filter((task) => normalizeStatus(task.status) === "阻塞中").length;
      const doneCount = assigned.filter((task) => normalizeStatus(task.status) === "已完成").length;
      const pendingCount = assigned.filter((task) => normalizeStatus(task.status) === "待承接").length;
      const loadValue = clampLoad(worker.load || (runningCount * 26 + blockedCount * 30 + pendingCount * 12));
      const heat = resolveHeat(loadValue, runningCount, blockedCount);
      return {
        ...worker,
        taskCount: assigned.length,
        runningCount,
        blockedCount,
        pendingCount,
        doneCount,
        loadValue,
        heat,
        statusText: buildWorkerStatusText(heat, runningCount, blockedCount),
      };
    });
  }

  function mergeWorkerDirectory(workerDirectory) {
    if (!Array.isArray(workerDirectory) || !workerDirectory.length) {
      return structuredClone(WORKER_PRESETS);
    }
    const presetMap = new Map(WORKER_PRESETS.map((worker) => [worker.id, worker]));
    return workerDirectory.map((worker) => {
      const preset = presetMap.get(worker.id) || {};
      return {
        ...preset,
        ...worker,
        capability: worker.capability?.length ? worker.capability : (preset.capability || []),
        bio: worker.bio || preset.bio || "可承接当前创意分发任务。",
        type: worker.type || preset.type || guessWorkerType(worker.id),
        title: worker.title || preset.title || `${worker.name} worker`,
      };
    });
  }

  function buildCreativeCards(tasks, workers) {
    const recommendations = buildRecommendedCards(tasks, workers);
    return recommendations.length ? recommendations : structuredClone(FALLBACK_CARDS);
  }

  function buildRecommendedCards(tasks, workers) {
    const queueTasks = tasks
      .filter((task) => normalizeStatus(task.status) === "待承接")
      .slice(0, 12);
    return queueTasks.map((task, index) => {
      const recommendedWorker = findBestWorkerForTask(task, workers);
      const workerType = recommendedWorker?.type || guessWorkerType(task.assignee);
      return {
        id: task.id,
        title: task.title,
        description: task.summary,
        workerType,
        assigneeHint: recommendedWorker?.id || task.assignee || "frontend-dev",
        priority: normalizePriority(task.priority),
        status: normalizeStatus(task.status),
        tone: recommendedWorker?.heat || "idle",
        tags: [task.workspace || "dir", normalizeStatus(task.status), normalizePriority(task.priority)],
        reason: buildDispatchReason(task, recommendedWorker),
        payload: buildDispatchPayload(task, recommendedWorker, index),
      };
    });
  }

  function buildDispatchPayload(task, worker, index) {
    const fallbackTitle = task.title || `创意卡片 ${index + 1}`;
    return {
      title: fallbackTitle,
      summary: task.summary || "待补充说明",
      assignee: worker?.id || task.assignee || "frontend-dev",
      priority: normalizePriority(task.priority),
      workspace: task.workspace || "dir",
      source_task_id: task.id,
      worker_type: worker?.type || guessWorkerType(task.assignee),
    };
  }

  function findBestWorkerForTask(task, workers) {
    const preferredType = guessWorkerType(task.assignee);
    const sameType = workers.filter((worker) => worker.type === preferredType && worker.heat !== "hot");
    const candidatePool = sameType.length ? sameType : workers.filter((worker) => worker.heat !== "hot");
    return [...candidatePool].sort((a, b) => a.loadValue - b.loadValue || a.pendingCount - b.pendingCount)[0] || workers[0] || null;
  }

  function buildDispatchReason(task, worker) {
    if (!worker) {
      return "当前未识别到更合适的 worker，建议人工确认后再分发。";
    }
    return `建议分发给 ${worker.name}，当前负载 ${worker.loadValue}% ，更适合处理 ${worker.capability?.[0] || worker.type}。`;
  }

  function buildErrorMessage(error) {
    const status = Number(error?.status || 0);
    if (status === 401 || status === 403) {
      return "未登录或权限不足，当前展示本地创意占位卡片。";
    }
    return error?.message || "接口请求失败，当前展示本地创意占位卡片。";
  }

  function normalizeStatus(value) {
    const raw = String(value || "").toLowerCase();
    if (["running", "doing", "in_progress", "进行中"].includes(raw)) return "进行中";
    if (["blocked", "block", "阻塞中"].includes(raw)) return "阻塞中";
    if (["done", "completed", "已完成"].includes(raw)) return "已完成";
    return "待承接";
  }

  function normalizePriority(value) {
    const raw = String(value || "").toLowerCase();
    if (["p0", "p1", "high", "高", "高优先级", "40", "50"].includes(raw)) return "高优先级";
    if (["p3", "low", "低", "低优先级", "10", "0"].includes(raw)) return "低优先级";
    return "普通优先级";
  }

  function guessWorkerType(value) {
    const text = String(value || "").toLowerCase();
    if (text.includes("front")) return "前端协作";
    if (text.includes("back")) return "接口联调";
    if (text.includes("review")) return "质量复核";
    if (text.includes("devops") || text.includes("ops")) return "环境保障";
    return "前端协作";
  }

  function clampLoad(value) {
    return Math.max(0, Math.min(100, Number(value) || 0));
  }

  function resolveHeat(loadValue, runningCount, blockedCount) {
    if (blockedCount > 0 || loadValue >= 70) return "hot";
    if (runningCount > 0 || loadValue >= 36) return "warm";
    return "idle";
  }

  function buildWorkerStatusText(heat, runningCount, blockedCount) {
    if (heat === "hot") return blockedCount > 0 ? "阻塞中" : "高负载";
    if (heat === "warm") return runningCount > 0 ? "处理中" : "排队中";
    return "空闲";
  }

  function getFilteredCards() {
    return state.cards.filter((card) => {
      const matchesType = state.selectedType === "all" || card.workerType === state.selectedType;
      const matchesWorker = !state.selectedWorkerId || card.assigneeHint === state.selectedWorkerId || card.assigneeHint === "未分配";
      return matchesType && matchesWorker;
    });
  }

  function getPreferredWorkerId(workers) {
    const idleWorker = workers.find((worker) => worker.heat === "idle");
    return idleWorker?.id || workers[0]?.id || "";
  }

  function getSelectedWorker() {
    return state.workers.find((worker) => worker.id === state.selectedWorkerId) || state.workers[0] || null;
  }

  function handleTypeChange(event) {
    state.selectedType = event.currentTarget?.dataset.creativeType || "all";
    state.dispatchResult = null;
    updateTypeButtons();
    saveState();
    renderCreativeWall();
  }

  function handleResetCreativeWall() {
    state.selectedType = "all";
    state.selectedWorkerId = getPreferredWorkerId(state.workers);
    state.dispatchResult = null;
    updateTypeButtons();
    saveState();
    renderCreativeWall();
  }

  function updateTypeButtons() {
    refs.typeButtons.forEach((button) => {
      const active = (button.dataset.creativeType || "all") === state.selectedType;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-pressed", String(active));
    });
  }

  function renderCreativeWall() {
    if (!refs.panel) return;
    renderCreativeSummary();
    renderCreativeState();
    renderCreativeWorkers();
    renderCreativeCards();
    renderCreativeHighlight();
  }

  function renderCreativeSummary() {
    const cards = getFilteredCards();
    const idleCount = state.workers.filter((worker) => worker.heat === "idle").length;
    if (refs.summary) {
      refs.summary.innerHTML = [
        `worker 类型 <strong>${state.selectedType === "all" ? "全部" : escapeHtml(state.selectedType)}</strong>`,
        `空闲 worker <strong>${idleCount}</strong>`,
        `创意卡片 <strong>${cards.length}</strong>`,
        `数据源 <strong>${state.source === "api" ? "API" : "本地占位"}</strong>`,
      ].map((item) => `<span class="summary-chip">${item}</span>`).join("");
    }
    if (refs.idleCount) refs.idleCount.textContent = String(idleCount);
    if (refs.cardCount) refs.cardCount.textContent = String(cards.length);
  }

  function renderCreativeState() {
    if (!refs.state) return;
    if (state.loading) {
      refs.state.className = "panel-state";
      refs.state.innerHTML = '<section class="state-inline"><span class="spinner" aria-hidden="true"></span><h3>加载中</h3></section><p>正在同步空闲 worker 与创意卡片。</p>';
      return;
    }
    if (state.error) {
      refs.state.className = "panel-state is-error";
      refs.state.innerHTML = `<section class="state-inline"><h3>网络错误</h3></section><p>${escapeHtml(state.error)}</p><button class="btn btn-primary" type="button" data-creative-retry>重试</button>`;
      refs.state.querySelector("[data-creative-retry]")?.addEventListener("click", loadCreativeWall);
      return;
    }
    if (state.dispatchResult?.type === "success") {
      refs.state.className = "panel-state is-success";
      refs.state.innerHTML = `<section class="state-inline"><h3>分发成功</h3></section><p>${escapeHtml(state.dispatchResult.message)}</p><button class="btn btn-secondary" type="button" data-creative-retry>刷新列表</button>`;
      refs.state.querySelector("[data-creative-retry]")?.addEventListener("click", loadCreativeWall);
      return;
    }
    if (state.dispatchResult?.type === "error") {
      refs.state.className = "panel-state is-error";
      refs.state.innerHTML = `<section class="state-inline"><h3>分发失败</h3></section><p>${escapeHtml(state.dispatchResult.message)}</p><button class="btn btn-primary" type="button" data-creative-retry>重试刷新</button>`;
      refs.state.querySelector("[data-creative-retry]")?.addEventListener("click", loadCreativeWall);
      return;
    }
    const cards = getFilteredCards();
    if (!cards.length) {
      refs.state.className = "panel-state";
      refs.state.innerHTML = '<section class="state-inline"><h3>暂无数据</h3></section><p>当前筛选条件下没有可承接的创意卡片。</p><button class="btn btn-primary" type="button" data-creative-reset-inline>清空筛选</button>';
      refs.state.querySelector("[data-creative-reset-inline]")?.addEventListener("click", handleResetCreativeWall);
      return;
    }
    refs.state.className = "panel-state is-success";
    refs.state.innerHTML = `<section class="state-inline"><h3>已加载</h3></section><p>当前展示 ${cards.length} 张创意卡片，可按 worker 类型筛选并一键分发。</p>`;
  }

  function renderCreativeWorkers() {
    if (!refs.workerList) return;
    if (state.loading) {
      refs.workerList.innerHTML = Array.from({ length: 4 }, () => '<article class="panel-skeleton" aria-hidden="true"></article>').join("");
      return;
    }
    const workers = state.workers;
    if (!workers.length) {
      refs.workerList.innerHTML = '<article class="panel-empty"><h3>暂无数据</h3><p>当前没有可展示的 worker。</p></article>';
      return;
    }
    refs.workerList.innerHTML = workers.map(renderWorkerCard).join("");
    refs.workerList.querySelectorAll("[data-creative-worker]").forEach((button) => {
      button.addEventListener("click", () => {
        state.selectedWorkerId = button.dataset.creativeWorker || "";
        state.dispatchResult = null;
        saveState();
        renderCreativeWall();
      });
    });
  }

  function renderWorkerCard(worker) {
    const isSelected = worker.id === state.selectedWorkerId;
    const disabled = worker.heat === "hot" ? "disabled" : "";
    const disabledText = worker.heat === "hot" ? "暂不可选" : "设为焦点";
    return `
      <article class="worker-card ${isSelected ? "is-selected" : ""}" data-heat="${escapeHtml(worker.heat)}">
        <header class="worker-card__head">
          <div>
            <h3>${escapeHtml(worker.name)}</h3>
            <p>${escapeHtml(worker.title)}</p>
          </div>
          <span class="heat-badge">${escapeHtml(worker.statusText)}</span>
        </header>
        <p class="worker-card__hint">${escapeHtml(worker.bio)}</p>
        <p class="load-label"><strong>${escapeHtml(worker.type)}</strong><span>${worker.taskCount} 项</span></p>
        <div class="heatbar" aria-hidden="true" style="--load-width:${escapeHtml(String(Math.max(10, 100 - worker.loadValue)))}%"><i></i></div>
        <dl class="worker-counts">
          <div><dt>待承接</dt><dd>${worker.pendingCount}</dd></div>
          <div><dt>进行中</dt><dd>${worker.runningCount}</dd></div>
          <div><dt>阻塞</dt><dd>${worker.blockedCount}</dd></div>
        </dl>
        <div class="worker-card__actions">
          <button class="btn btn-primary" type="button" data-creative-worker="${escapeHtml(worker.id)}" ${disabled}>${disabledText}</button>
          <button class="btn btn-secondary" type="button" data-creative-worker="${escapeHtml(worker.id)}">查看卡片</button>
        </div>
      </article>
    `;
  }

  function renderCreativeCards() {
    if (!refs.cardGrid) return;
    if (state.loading) {
      refs.cardGrid.innerHTML = Array.from({ length: 3 }, () => '<article class="panel-skeleton" aria-hidden="true"></article>').join("");
      return;
    }
    const cards = getFilteredCards();
    if (!cards.length) {
      refs.cardGrid.innerHTML = '<article class="panel-empty creative-wall__empty"><h3>暂无数据</h3><p>当前没有符合筛选条件的创意卡片，建议清空筛选后重试。</p><button class="btn btn-primary" type="button" data-creative-reset-empty>清空筛选</button></article>';
      refs.cardGrid.querySelector("[data-creative-reset-empty]")?.addEventListener("click", handleResetCreativeWall);
      return;
    }
    refs.cardGrid.innerHTML = cards.map(renderCreativeCard).join("");
    refs.cardGrid.querySelectorAll("[data-creative-focus]").forEach((button) => {
      button.addEventListener("click", () => {
        state.selectedWorkerId = button.dataset.creativeFocus || state.selectedWorkerId;
        state.dispatchResult = null;
        saveState();
        renderCreativeWall();
      });
    });
    refs.cardGrid.querySelectorAll("[data-creative-dispatch]").forEach((button) => {
      button.addEventListener("click", handleDispatchCreativeCard);
    });
  }

  function renderCreativeCard(card) {
    const tags = card.tags.map((tag) => `<span class="summary-chip">${escapeHtml(tag)}</span>`).join("");
    const loading = state.dispatchingId === card.id;
    const disabled = loading || card.tone === "hot";
    const dispatchLabel = loading ? '<span class="spinner" aria-hidden="true"></span>分发中...' : (card.tone === "hot" ? "暂不可分发" : "一键分发");
    const helperLabel = card.priority === "高优先级" ? '<span class="summary-chip">优先处理</span>' : '<span class="summary-chip">可排期</span>';
    return `
      <article class="recommend-card creative-card" data-heat="${escapeHtml(card.tone)}">
        <header class="creative-card__head">
          <div>
            <h3>${escapeHtml(card.title)}</h3>
            <p>${escapeHtml(card.description)}</p>
          </div>
          ${helperLabel}
        </header>
        <section class="creative-card__meta">
          <span class="summary-chip">类型 <strong>${escapeHtml(card.workerType)}</strong></span>
          <span class="summary-chip">建议人 <strong>${escapeHtml(card.assigneeHint)}</strong></span>
          <span class="summary-chip">状态 <strong>${escapeHtml(card.status)}</strong></span>
        </section>
        <p class="creative-card__reason">${escapeHtml(card.reason)}</p>
        <section class="creative-card__tags">${tags}</section>
        <nav class="creative-card__actions" aria-label="创意卡片操作">
          <button class="btn btn-primary" type="button" data-creative-dispatch="${escapeHtml(card.id)}" ${disabled ? "disabled" : ""}>${dispatchLabel}</button>
          <button class="btn btn-secondary" type="button" data-creative-focus="${escapeHtml(card.assigneeHint)}">聚焦该 worker</button>
        </nav>
      </article>
    `;
  }

  async function handleDispatchCreativeCard(event) {
    const cardId = event.currentTarget?.dataset.creativeDispatch || "";
    const card = state.cards.find((item) => item.id === cardId);
    if (!card || !window.apiClient?.dispatchCreativeIdea) {
      return;
    }
    state.dispatchResult = null;
    state.dispatchingId = cardId;
    renderCreativeWall();
    try {
      const result = await window.apiClient.dispatchCreativeIdea(card.payload, { auth: true });
      const taskId = result?.id || result?.task_id || result?.data?.id || result?.data?.task_id || "已提交";
      state.dispatchResult = {
        type: "success",
        message: `${card.title} 已分发给 ${card.assigneeHint}，任务标识：${taskId}。`,
      };
      await loadCreativeWall();
    } catch (error) {
      state.dispatchResult = {
        type: "error",
        message: error?.message || "分发失败，请稍后重试。",
      };
    } finally {
      state.dispatchingId = "";
      renderCreativeWall();
    }
  }

  function renderCreativeHighlight() {
    const worker = getSelectedWorker();
    const cards = getFilteredCards();
    if (!refs.highlightName || !refs.highlightText || !refs.highlightMeta) return;
    if (state.loading) {
      refs.highlightName.textContent = "正在同步";
      refs.highlightText.textContent = "加载后会展示当前最空闲 worker 与可承接创意。";
      refs.highlightMeta.textContent = "等待刷新";
      return;
    }
    if (!worker) {
      refs.highlightName.textContent = "暂无数据";
      refs.highlightText.textContent = "当前没有可展示的空闲 worker。";
      refs.highlightMeta.textContent = "请稍后重试";
      return;
    }
    const matched = cards.find((card) => card.assigneeHint === worker.id) || cards[0];
    refs.highlightName.textContent = worker.name;
    refs.highlightText.textContent = matched ? `${matched.title}：${matched.reason}` : `${worker.bio}`;
    refs.highlightMeta.textContent = `${worker.type} · ${worker.capability.join(" / ") || "待补充能力"}`;
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
