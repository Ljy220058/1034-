(()=>{
  "use strict";

  const STORAGE_KEY = "1034.creative-wall.filters.v3";

  const WORKER_PRESETS = [
    { id: "frontend-dev", name: "frontend-dev", title: "前端空闲 worker", type: "前端协作", statusText: "空闲", heat: "idle", capability: ["页面搭建", "交互补全", "移动端优化"], bio: "适合接轻量界面、卡片布局与状态补全类任务。" },
    { id: "backend-dev", name: "backend-dev", title: "后端协作 worker", type: "接口联调", statusText: "忙碌", heat: "warm", capability: ["字段对齐", "数据聚合", "接口排查"], bio: "适合补齐接口字段、整理列表响应与联调说明。" },
    { id: "reviewer", name: "reviewer", title: "评审支援 worker", type: "质量复核", statusText: "待命", heat: "idle", capability: ["文案校对", "状态走查", "交付复核"], bio: "适合处理交付前检查、文案统一与体验复核。" },
    { id: "devops-engineer", name: "devops-engineer", title: "运维调度 worker", type: "环境保障", statusText: "高负载", heat: "hot", capability: ["服务探活", "环境检查", "发布保障"], bio: "适合排查环境可用性、静态服务与部署链路问题。" },
  ];

  const FALLBACK_CARDS = [
    { id: "idea-ui-001", title: "整理看板空态文案", description: "补齐“暂无数据 / 重试 / 加载中”文案，让空闲 worker 接手时直接可交付。", workerType: "前端协作", assigneeHint: "frontend-dev", priority: "高优先级", status: "待承接", tone: "idle", actionLabel: "补齐页面交互", reason: "适合用较少改动快速提升页面完成度。" },
    { id: "idea-api-002", title: "补齐接口字段映射说明", description: "梳理任务列表返回中的 title、assignee、status、workspace 字段映射，便于前后端对齐。", workerType: "接口联调", assigneeHint: "backend-dev", priority: "中优先级", status: "可排期", tone: "warm", actionLabel: "同步接口字段", reason: "适合后端协作 worker 快速处理字段稳定性。" },
    { id: "idea-review-003", title: "走查按钮交互状态", description: "集中检查 hover、active、disabled、loading 四态，确保交付前体验一致。", workerType: "质量复核", assigneeHint: "reviewer", priority: "普通优先级", status: "待确认", tone: "idle", actionLabel: "安排体验复核", reason: "适合评审支援 worker 做最后一轮中文体验复核。" },
    { id: "idea-ops-004", title: "确认静态预览服务可访问", description: "检查静态服务与后端联调链路是否可用，避免前端页面可见但接口不可达。", workerType: "环境保障", assigneeHint: "devops-engineer", priority: "普通优先级", status: "需环境确认", tone: "hot", actionLabel: "触发环境检查", reason: "适合运维 worker 在高负载前做一次环境探活。" },
  ];

  const state = { loading: true, dispatchingId: "", error: "", workers: structuredClone(WORKER_PRESETS), cards: [], selectedType: "all", selectedWorkerId: "", source: "fallback", dispatchResult: null };
  const refs = {};

  document.addEventListener("DOMContentLoaded", initCreativeWall);

  function initCreativeWall() { cacheRefs(); if (!refs.panel) return; bindEvents(); restoreState(); loadCreativeWall(); }
  function cacheRefs() { refs.panel=document.querySelector("[data-creative-wall]"); refs.state=document.querySelector("[data-creative-state]"); refs.summary=document.querySelector("[data-creative-summary]"); refs.workerList=document.querySelector("[data-creative-workers]"); refs.cardGrid=document.querySelector("[data-creative-cards]"); refs.retryButtons=Array.from(document.querySelectorAll("[data-creative-refresh]")); refs.reset=document.querySelector("[data-creative-reset]"); refs.typeButtons=Array.from(document.querySelectorAll("[data-creative-type]")); refs.highlightName=document.querySelector("[data-creative-highlight-name]"); refs.highlightText=document.querySelector("[data-creative-highlight-text]"); refs.highlightMeta=document.querySelector("[data-creative-highlight-meta]"); refs.idleCount=document.querySelector("[data-creative-idle-count]"); refs.cardCount=document.querySelector("[data-creative-card-count]"); }
  function bindEvents() { refs.retryButtons.forEach((button)=>button.addEventListener("click", loadCreativeWall)); refs.reset?.addEventListener("click", handleResetCreativeWall); refs.typeButtons.forEach((button)=>button.addEventListener("click", handleTypeChange)); }
  function restoreState() { try { const saved=JSON.parse(localStorage.getItem(STORAGE_KEY)||"null"); if (saved) { state.selectedType=saved.selectedType||"all"; state.selectedWorkerId=saved.selectedWorkerId||""; } } catch {} updateTypeButtons(); }
  function saveState() { localStorage.setItem(STORAGE_KEY, JSON.stringify({ selectedType: state.selectedType, selectedWorkerId: state.selectedWorkerId })); }

  async function loadCreativeWall() {
    state.loading = true; state.error = ""; state.dispatchResult = null; renderCreativeWall();
    try {
      const [tasks, workerDirectory] = await Promise.all([fetchTaskQueue(), fetchWorkerDirectory()]);
      state.workers = buildWorkers(tasks, workerDirectory);
      state.cards = buildCreativeCards(tasks, state.workers);
      state.source = "api";
    } catch (error) {
      state.error = buildErrorMessage(error);
      state.workers = buildWorkers([], []);
      state.cards = structuredClone(FALLBACK_CARDS);
      state.source = "fallback";
    } finally {
      if (!state.selectedWorkerId || !state.workers.some((worker) => worker.id === state.selectedWorkerId)) state.selectedWorkerId = getPreferredWorkerId(state.workers);
      state.loading = false;
      renderCreativeWall();
      saveState();
    }
  }

  function fetchTaskQueue() { return window.apiClient?.fetchTaskQueue?.({ auth: true }) || Promise.resolve([]); }
  function fetchWorkerDirectory() { return window.apiClient?.fetchWorkerDirectory?.({ auth: true }) || Promise.resolve([]); }
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
      return { ...worker, taskCount: assigned.length, runningCount, blockedCount, pendingCount, doneCount, loadValue, heat, statusText: buildWorkerStatusText(heat, runningCount, blockedCount) };
    });
  }
  function mergeWorkerDirectory(workerDirectory) {
    if (!Array.isArray(workerDirectory) || !workerDirectory.length) return structuredClone(WORKER_PRESETS);
    const presetMap = new Map(WORKER_PRESETS.map((worker) => [worker.id, worker]));
    return workerDirectory.map((worker) => { const preset = presetMap.get(worker.id) || {}; return { ...preset, ...worker, capability: worker.capability?.length ? worker.capability : (preset.capability || []), bio: worker.bio || preset.bio || "可承接当前创意分发任务。", type: worker.type || preset.type || guessWorkerType(worker.id), title: worker.title || preset.title || `${worker.name} worker` }; });
  }
  function buildCreativeCards(tasks, workers) { const recommendations = buildRecommendedCards(tasks, workers); return recommendations.length ? recommendations : structuredClone(FALLBACK_CARDS); }
  function buildRecommendedCards(tasks, workers) {
    return tasks.filter((task) => normalizeStatus(task.status) === "待承接").slice(0, 12).map((task, index) => {
      const recommendedWorker = findBestWorkerForTask(task, workers);
      const workerType = recommendedWorker?.type || guessWorkerType(task.assignee);
      return { id: task.id, title: task.title, description: task.summary, workerType, assigneeHint: recommendedWorker?.id || task.assignee || "frontend-dev", priority: normalizePriority(task.priority), status: normalizeStatus(task.status), tone: recommendedWorker?.heat || "idle", reason: buildDispatchReason(task, recommendedWorker), actionLabel: buildActionLabel(task, recommendedWorker), payload: buildDispatchPayload(task, recommendedWorker, index) };
    });
  }
  function buildDispatchPayload(task, worker, index) { const fallbackTitle = task.title || `创意卡片 ${index + 1}`; return { title: fallbackTitle, summary: task.summary || "待补充说明", assignee: worker?.id || task.assignee || "frontend-dev", priority: normalizePriority(task.priority), workspace: task.workspace || "dir", source_task_id: task.id, worker_type: worker?.type || guessWorkerType(task.assignee) }; }
  function findBestWorkerForTask(task, workers) { const preferredType = guessWorkerType(task.assignee); const sameType = workers.filter((worker) => worker.type === preferredType && worker.heat !== "hot"); const candidatePool = sameType.length ? sameType : workers.filter((worker) => worker.heat !== "hot"); return [...candidatePool].sort((a, b) => a.loadValue - b.loadValue || a.pendingCount - b.pendingCount)[0] || workers[0] || null; }
  function buildActionLabel(task, worker) { if (worker?.type === "接口联调") return "同步接口字段"; if (worker?.type === "质量复核") return "安排体验复核"; if (worker?.type === "环境保障") return "触发环境检查"; return "补齐页面交互"; }
  function buildDispatchReason(task, worker) { if (!worker) return "当前未识别到更合适的 worker，建议人工确认后再分发。"; return `建议分发给 ${worker.name}，当前负载 ${worker.loadValue}% ，更适合处理 ${worker.capability?.[0] || worker.type}。`; }
  function buildErrorMessage(error) { const status = Number(error?.status || 0); if (status === 401 || status === 403) return "当前接口访问受限，已展示本地创意占位卡片。"; return error?.message || "接口请求失败，当前展示本地创意占位卡片。"; }
  function normalizeStatus(value) { const raw = String(value || "").toLowerCase(); if (["running", "doing", "in_progress", "进行中"].includes(raw)) return "进行中"; if (["blocked", "block", "阻塞中"].includes(raw)) return "阻塞中"; if (["done", "completed", "已完成"].includes(raw)) return "已完成"; return "待承接"; }
  function normalizePriority(value) { const raw = String(value || "").toLowerCase(); if (["p0", "p1", "high", "高", "高优先级", "40", "50"].includes(raw)) return "高优先级"; if (["p3", "low", "低", "低优先级", "10", "0"].includes(raw)) return "低优先级"; return "普通优先级"; }
  function guessWorkerType(value) { const text = String(value || "").toLowerCase(); if (text.includes("front")) return "前端协作"; if (text.includes("back")) return "接口联调"; if (text.includes("review")) return "质量复核"; if (text.includes("devops") || text.includes("ops")) return "环境保障"; return "前端协作"; }
  function clampLoad(value) { return Math.max(0, Math.min(100, Number(value) || 0)); }
  function resolveHeat(loadValue, runningCount, blockedCount) { if (blockedCount > 0 || loadValue >= 70) return "hot"; if (runningCount > 0 || loadValue >= 36) return "warm"; return "idle"; }
  function buildWorkerStatusText(heat, runningCount, blockedCount) { if (heat === "hot") return blockedCount > 0 ? "阻塞中" : "高负载"; if (heat === "warm") return runningCount > 0 ? "处理中" : "排队中"; return "空闲"; }
  function getFilteredCards() { return state.cards.filter((card) => { const matchesType = state.selectedType === "all" || card.workerType === state.selectedType; const matchesWorker = !state.selectedWorkerId || card.assigneeHint === state.selectedWorkerId || card.assigneeHint === "未分配"; return matchesType && matchesWorker; }); }
  function getVisibleWorkers() { return state.workers.filter((worker) => state.selectedType === "all" || worker.type === state.selectedType); }
  function getGroupedCards(cards) { const groups = new Map(); cards.forEach((card) => { if (!groups.has(card.workerType)) groups.set(card.workerType, []); groups.get(card.workerType).push(card); }); return Array.from(groups.entries()).map(([type, items]) => ({ type, items })); }
  function getPreferredWorkerId(workers) { const idleWorker = workers.find((worker) => worker.heat === "idle"); return idleWorker?.id || workers[0]?.id || ""; }
  function getSelectedWorker() { return state.workers.find((worker) => worker.id === state.selectedWorkerId) || state.workers[0] || null; }
  function handleTypeChange(event) { state.selectedType = event.currentTarget?.dataset.creativeType || "all"; state.dispatchResult = null; updateTypeButtons(); saveState(); renderCreativeWall(); }
  function handleResetCreativeWall() { state.selectedType = "all"; state.selectedWorkerId = getPreferredWorkerId(state.workers); state.dispatchResult = null; updateTypeButtons(); saveState(); renderCreativeWall(); }
  function updateTypeButtons() { refs.typeButtons.forEach((button) => { const isActive = button.dataset.creativeType === state.selectedType; button.classList.toggle("is-active", isActive); button.setAttribute("aria-pressed", String(isActive)); }); }

  async function handleDispatchIdea(cardId) {
    const card = state.cards.find((item) => item.id === cardId);
    if (!card || !card.payload || !window.apiClient?.dispatchCreativeIdea) return;
    state.dispatchingId = cardId; state.dispatchResult = null; renderCreativeWall();
    try {
      await window.apiClient.dispatchCreativeIdea(card.payload, { auth: true });
      state.dispatchResult = { tone: "success", text: `已提交：${card.title}` };
    } catch (error) {
      state.dispatchResult = { tone: "error", text: buildErrorMessage(error) };
    } finally {
      state.dispatchingId = ""; renderCreativeWall();
    }
  }

  function handleSelectWorker(workerId) { state.selectedWorkerId = workerId; state.dispatchResult = null; saveState(); renderCreativeWall(); }

  function renderCreativeWall() {
    if (!refs.panel) return;
    const visibleWorkers = getVisibleWorkers();
    const filteredCards = getFilteredCards();
    renderSummary(visibleWorkers, filteredCards);
    renderHighlight(visibleWorkers, filteredCards);
    renderState(filteredCards);
    renderWorkers(visibleWorkers);
    renderCards(filteredCards);
    refs.idleCount.textContent = String(visibleWorkers.filter((worker) => worker.heat === "idle").length);
    refs.cardCount.textContent = String(filteredCards.length);
  }

  function renderSummary(visibleWorkers, filteredCards) {
    const chips = [
      `<span class="summary-chip"><strong>${visibleWorkers.length}</strong> 个 worker</span>`,
      `<span class="summary-chip"><strong>${filteredCards.length}</strong> 张创意卡片</span>`,
      `<span class="summary-chip">数据源：${state.source === "api" ? "接口" : "本地回退"}</span>`,
    ];
    refs.summary.innerHTML = chips.join("");
  }

  function renderHighlight(visibleWorkers, filteredCards) {
    const worker = getSelectedWorker() || visibleWorkers[0] || null;
    if (!worker) { refs.highlightName.textContent = "暂无可用 worker"; refs.highlightText.textContent = "当前没有可展示的空闲 worker，请稍后刷新。"; refs.highlightMeta.textContent = "等待刷新"; return; }
    refs.highlightName.textContent = `${worker.title} · ${worker.name}`;
    refs.highlightText.textContent = worker.bio || "可承接当前创意卡片。";
    const matched = filteredCards.filter((card) => card.assigneeHint === worker.id).length;
    refs.highlightMeta.textContent = `${worker.type} · 负载 ${worker.loadValue}% · 匹配卡片 ${matched}`;
  }

  function renderState(filteredCards) {
    if (state.loading) { refs.state.className = "panel-state"; refs.state.innerHTML = `<section class="state-inline"><span class="spinner" aria-hidden="true"></span><section><h3>正在同步创意墙</h3><p>正在读取空闲 worker 与创意卡片。</p></section></section><button class="btn btn-secondary" type="button" disabled>同步中</button>`; return; }
    if (state.error) { refs.state.className = "panel-state is-error"; refs.state.innerHTML = `<section><h3>接口读取失败</h3><p>${escapeHtml(state.error)}</p></section><button class="btn btn-secondary" type="button" data-creative-refresh>重试</button>`; refs.state.querySelector("[data-creative-refresh]")?.addEventListener("click", loadCreativeWall); return; }
    if (!filteredCards.length) { refs.state.className = "panel-state is-success"; refs.state.innerHTML = `<section><h3>暂无数据</h3><p>当前筛选条件下没有可展示的创意卡片，可切换 worker 类型或清空筛选后重试。</p></section><button class="btn btn-secondary" type="button" data-creative-reset-inline>清空筛选</button>`; refs.state.querySelector("[data-creative-reset-inline]")?.addEventListener("click", handleResetCreativeWall); return; }
    const dispatchHtml = state.dispatchResult ? `<span class="summary-chip">${escapeHtml(state.dispatchResult.text)}</span>` : `<span class="summary-chip">已按 worker 类型分组展示创意卡片</span>`;
    refs.state.className = `panel-state ${state.dispatchResult?.tone === "error" ? "is-error" : "is-success"}`.trim();
    refs.state.innerHTML = `<section><h3>创意墙已就绪</h3><p>当前展示 ${filteredCards.length} 张创意卡片，可直接按类型筛选或点击建议动作。</p></section>${dispatchHtml}`;
  }

  function renderWorkers(workers) {
    if (!refs.workerList) return;
    if (!workers.length) { refs.workerList.innerHTML = `<article class="worker-card"><h3>暂无 worker</h3><p class="worker-card__hint">当前筛选结果为空，请切换类型后重试。</p></article>`; return; }
    refs.workerList.innerHTML = workers.map((worker) => {
      const isSelected = worker.id === state.selectedWorkerId;
      const capability = worker.capability?.length ? worker.capability.map((item) => `<span class="summary-chip">${escapeHtml(item)}</span>`).join("") : `<span class="summary-chip">待补充能力</span>`;
      return `<article class="worker-card ${isSelected ? "is-selected" : ""}" data-heat="${escapeHtml(worker.heat)}"><header class="worker-card__head"><section><h3>${escapeHtml(worker.title)}</h3><p>${escapeHtml(worker.name)} · ${escapeHtml(worker.type)}</p></section><span class="heat-badge">${escapeHtml(worker.statusText)}</span></header><section><p class="load-label"><span>当前负载</span><strong>${worker.loadValue}%</strong></p><div class="heatbar" style="--load-width:${worker.loadValue}%"><i></i></div></section><dl class="worker-counts"><div><dt>待承接</dt><dd>${worker.pendingCount}</dd></div><div><dt>进行中</dt><dd>${worker.runningCount}</dd></div><div><dt>已完成</dt><dd>${worker.doneCount}</dd></div></dl><p class="worker-card__hint">${escapeHtml(worker.bio || "可承接当前创意卡片。")}</p><section class="sidebar-panel__summary">${capability}</section><nav class="worker-card__actions"><button class="btn btn-secondary" type="button" data-select-worker="${escapeHtml(worker.id)}">查看匹配创意</button></nav></article>`;
    }).join("");
    refs.workerList.querySelectorAll("[data-select-worker]").forEach((button) => button.addEventListener("click", (event) => handleSelectWorker(event.currentTarget.dataset.selectWorker || "")));
  }

  function renderCards(cards) {
    if (!refs.cardGrid) return;
    if (!cards.length) { refs.cardGrid.innerHTML = ""; return; }
    const groups = getGroupedCards(cards);
    refs.cardGrid.innerHTML = groups.map((group) => {
      const selectedCount = group.items.filter((card) => card.assigneeHint === state.selectedWorkerId).length;
      return `<section class="creative-group" aria-labelledby="creative-group-${escapeAttr(group.type)}"><header class="creative-group__header"><section><h3 id="creative-group-${escapeAttr(group.type)}">${escapeHtml(group.type)}</h3><p>${group.items.length} 张创意卡片${selectedCount ? ` · 当前 worker 命中 ${selectedCount} 张` : ""}</p></section><span class="summary-chip">按 worker 类型分组</span></header><section class="creative-group__grid">${group.items.map(renderCardArticle).join("")}</section></section>`;
    }).join("");
    refs.cardGrid.querySelectorAll("[data-dispatch-idea]").forEach((button) => button.addEventListener("click", (event) => handleDispatchIdea(event.currentTarget.dataset.dispatchIdea || "")));
  }

  function renderCardArticle(card) {
    const isLoading = state.dispatchingId === card.id;
    const buttonLabel = isLoading ? "提交中" : card.actionLabel || "立即处理";
    const tags = [card.priority, card.status, card.assigneeHint].map((item) => `<span class="summary-chip">${escapeHtml(item)}</span>`).join("");
    return `<article class="creative-card" data-tone="${escapeHtml(card.tone || "idle")}"><header class="creative-card__header"><section><h3>${escapeHtml(card.title)}</h3><p>${escapeHtml(card.description || "待补充说明")}</p></section><span class="heat-badge">${escapeHtml(card.priority)}</span></header><section class="sidebar-panel__summary">${tags}</section><p class="creative-card__reason">${escapeHtml(card.reason || "建议尽快承接。")}</p><nav class="worker-card__actions"><button class="btn btn-primary" type="button" data-dispatch-idea="${escapeHtml(card.id)}" ${isLoading ? "disabled" : ""}>${isLoading ? '<span class="spinner" aria-hidden="true"></span>' : ''}${escapeHtml(buttonLabel)}</button></nav></article>`;
  }

  function escapeHtml(value) { return String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#39;"); }
  function escapeAttr(value) { return String(value ?? "group").replace(/[^a-zA-Z0-9_-]+/g, "-"); }
})();
