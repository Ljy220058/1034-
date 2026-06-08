const WORKER_RECO_TASK_API = "/api/v1/task-queue/tasks";

const workerRecoState = {
  items: [],
  filteredItems: [],
  loading: true,
  error: "",
  search: "",
  type: "all",
  filter: "all",
  selectedId: "",
  statusMessage: "",
};

const workerRecoDom = {};

function escapeCreativeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

document.addEventListener("DOMContentLoaded", initWorkerSidebar);

function initWorkerSidebar() {
  bindWorkerRecoElements();
  if (!workerRecoDom.root) return;
  bindWorkerRecoEvents();
  fetchWorkerRecoTasks();
}

function bindWorkerRecoElements() {
  workerRecoDom.root = document.querySelector("[data-worker-reco]");
  workerRecoDom.list = document.querySelector("[data-worker-reco-list]");
  workerRecoDom.panel = document.querySelector("[data-worker-reco-panel]");
  workerRecoDom.state = document.querySelector("[data-worker-reco-state]");
  workerRecoDom.summary = document.querySelector("[data-worker-reco-summary]");
  workerRecoDom.quickFilters = document.querySelector("[data-worker-reco-quick-filters]");
  workerRecoDom.search = document.querySelector("[data-worker-reco-search]");
  workerRecoDom.type = document.querySelector("[data-worker-reco-type]");
  workerRecoDom.count = document.querySelector("[data-worker-reco-count]");
  workerRecoDom.idle = document.querySelector("[data-worker-reco-idle]");
  workerRecoDom.available = document.querySelector("[data-worker-reco-available]");
  workerRecoDom.chinese = document.querySelector("[data-worker-reco-chinese]");
}

function bindWorkerRecoEvents() {
  workerRecoDom.search?.addEventListener("input", handleWorkerRecoSearchChange);
  workerRecoDom.type?.addEventListener("change", handleWorkerRecoTypeChange);
  workerRecoDom.quickFilters?.addEventListener("click", handleWorkerRecoFilterClick);
  workerRecoDom.list?.addEventListener("click", handleWorkerRecoListClick);
}

async function fetchWorkerRecoTasks() {
  setWorkerRecoLoading(true);
  renderWorkerRecoPanel();
  try {
    const response = await fetch(WORKER_RECO_TASK_API, { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error("worker reco request failed");
    const payload = await response.json();
    workerRecoState.items = normalizeWorkerRecoTasks(payload);
    workerRecoState.error = "";
    if (!workerRecoState.selectedId && workerRecoState.items[0]) workerRecoState.selectedId = String(workerRecoState.items[0].id);
  } catch {
    workerRecoState.items = [];
    workerRecoState.error = "网络错误，无法读取 worker 推荐。";
  } finally {
    setWorkerRecoLoading(false);
    renderWorkerRecoPanel();
  }
}

function normalizeWorkerRecoTasks(payload) {
  const list = Array.isArray(payload) ? payload : Array.isArray(payload?.data) ? payload.data : Array.isArray(payload?.items) ? payload.items : Array.isArray(payload?.tasks) ? payload.tasks : [];
  return list.map((item, index) => {
    const text = [item.title, item.name, item.description, item.summary, item.assignee, item.owner].filter(Boolean).join(" ");
    return {
      id: item.id || item.task_id || `worker-${index + 1}`,
      title: item.title || item.name || `任务 ${index + 1}`,
      description: item.description || item.summary || item.body || "暂无描述",
      assignee: item.assignee || item.owner || "未分配",
      status: normalizeWorkerRecoStatus(item.status),
      priority: normalizeWorkerRecoPriority(item.priority ?? item.priority_level),
      tags: normalizeWorkerRecoTags(item, text),
      reason: item.reason || item.note || inferWorkerRecoReason(text),
      taskType: inferWorkerRecoType(text),
      recentDone: Number(item.recent_done ?? item.done_count ?? 0) || 0,
      canClaim: Boolean(item.can_claim ?? item.claimable ?? item.available ?? item.status === "running"),
    };
  });
}

function normalizeWorkerRecoStatus(value) {
  const raw = String(value || "").toLowerCase();
  if (["running", "doing", "busy", "working"].includes(raw)) return "busy";
  if (["blocked", "offline", "paused"].includes(raw)) return raw;
  if (["done", "completed", "complete"].includes(raw)) return "done";
  return "idle";
}

function normalizeWorkerRecoPriority(value) {
  const raw = String(value ?? "").toLowerCase();
  if (["urgent", "high", "medium", "low"].includes(raw)) return raw;
  if (["紧急", "最高"].includes(raw)) return "urgent";
  if (["高", "重要"].includes(raw)) return "high";
  if (["中", "普通", "0"].includes(raw)) return "medium";
  if (["低"].includes(raw)) return "low";
  return "medium";
}

function normalizeWorkerRecoTags(item, text) {
  const tags = Array.isArray(item.tags) ? item.tags : Array.isArray(item.labels) ? item.labels : [];
  const merged = [...tags];
  if (/前端|页面|UI|卡片/i.test(text) && !merged.includes("前端页面")) merged.push("前端页面");
  if (/接口|API|联调/i.test(text) && !merged.includes("接口联调")) merged.push("接口联调");
  if (/中文|创意|文案/i.test(text) && !merged.includes("中文创意")) merged.push("中文创意");
  if (/保障|运维|运行/i.test(text) && !merged.includes("运行保障")) merged.push("运行保障");
  return merged.slice(0, 4);
}

function inferWorkerRecoType(text) {
  if (/中文|创意|文案/i.test(text)) return "中文创意";
  if (/前端|页面|UI|卡片/i.test(text)) return "前端页面";
  if (/接口|API|联调/i.test(text)) return "接口联调";
  if (/保障|运维|运行/i.test(text)) return "运行保障";
  return "前端页面";
}

function inferWorkerRecoReason(text) {
  if (/中文|创意|文案/i.test(text)) return "适合中文创意与文案任务。";
  if (/前端|页面|UI|卡片/i.test(text)) return "适合前端页面与交互任务。";
  if (/接口|API|联调/i.test(text)) return "适合接口联调与数据接入。";
  return "适合运行保障与通用派发。";
}

function handleWorkerRecoSearchChange(event) {
  workerRecoState.search = String(event.target.value || "").trim().toLowerCase();
  renderWorkerRecoPanel();
}

function handleWorkerRecoTypeChange(event) {
  workerRecoState.type = String(event.target.value || "all");
  renderWorkerRecoPanel();
}

function handleWorkerRecoFilterClick(event) {
  const button = event.target.closest("[data-worker-reco-filter]");
  if (!button) return;
  workerRecoState.filter = String(button.dataset.workerRecoFilter || "all");
  workerRecoState.selectedId = "";
  renderWorkerRecoPanel();
}

function handleWorkerRecoListClick(event) {
  const button = event.target.closest("[data-worker-reco-item]");
  if (!button) return;
  workerRecoState.selectedId = String(button.dataset.workerRecoItem || "");
  renderWorkerRecoPanel();
}

function setWorkerRecoLoading(isLoading) {
  workerRecoState.loading = isLoading;
  [workerRecoDom.search, workerRecoDom.type].forEach((control) => {
    if (control) control.disabled = isLoading;
  });
  workerRecoDom.quickFilters?.querySelectorAll("button").forEach((button) => {
    button.disabled = isLoading;
  });
}

function renderWorkerRecoPanel() {
  renderWorkerRecoSummary();
  renderWorkerRecoState();
  renderWorkerRecoList();
  renderWorkerRecoDetail();
}

function renderWorkerRecoSummary() {
  const items = getWorkerRecoVisibleItems();
  workerRecoState.filteredItems = sortWorkerRecoItems(items);
  const idleCount = workerRecoState.items.filter((item) => item.status === "idle").length;
  const availableCount = workerRecoState.items.filter((item) => item.canClaim).length;
  const chineseCount = workerRecoState.items.filter((item) => item.taskType === "中文创意").length;
  if (workerRecoDom.count) workerRecoDom.count.textContent = String(workerRecoState.items.length);
  if (workerRecoDom.idle) workerRecoDom.idle.textContent = String(idleCount);
  if (workerRecoDom.available) workerRecoDom.available.textContent = String(availableCount);
  if (workerRecoDom.chinese) workerRecoDom.chinese.textContent = String(chineseCount);
  if (!workerRecoDom.summary) return;
  workerRecoDom.summary.innerHTML = [
    `当前 ${workerRecoState.filteredItems.length} 条`,
    `筛选：${getWorkerRecoFilterLabel(workerRecoState.filter)}`,
    `类型：${workerRecoState.type === "all" ? "全部类型" : workerRecoState.type}`,
  ].map((text) => `<span class="summary-chip">${escapeCreativeHtml(text)}</span>`).join("");
}

function renderWorkerRecoState() {
  if (!workerRecoDom.state) return;
  if (workerRecoState.loading) {
    workerRecoDom.state.className = "worker-sidebar__state";
    workerRecoDom.state.innerHTML = '<div class="activity-state__inline"><span class="spinner" aria-hidden="true"></span><h3>加载中</h3></div><p>正在读取任务队列并生成推荐。</p>';
    return;
  }
  if (workerRecoState.error) {
    workerRecoDom.state.className = "worker-sidebar__state is-error";
    workerRecoDom.state.innerHTML = `<div class="activity-state__inline"><h3>加载失败</h3></div><p>${escapeCreativeHtml(workerRecoState.error)}</p><button class="btn btn-primary" type="button" data-worker-reco-retry>重试</button>`;
    workerRecoDom.state.querySelector("[data-worker-reco-retry]")?.addEventListener("click", fetchWorkerRecoTasks);
    return;
  }
  workerRecoDom.state.className = "worker-sidebar__state";
  workerRecoDom.state.innerHTML = '<div class="activity-state__inline"><h3>可领取</h3></div><p>点击左侧条目查看详情，右侧面板展示负责人、状态与建议动作。</p>';
}

function renderWorkerRecoList() {
  if (!workerRecoDom.list) return;
  if (workerRecoState.loading) {
    workerRecoDom.list.innerHTML = '<article class="worker-sidebar__skeleton" aria-hidden="true"></article><article class="worker-sidebar__skeleton" aria-hidden="true"></article>';
    return;
  }
  if (!workerRecoState.filteredItems.length) {
    workerRecoDom.list.innerHTML = '<article class="worker-sidebar__empty"><h3>暂无数据</h3><p>当前筛选下没有可推荐的 worker，请切换筛选条件或等待新任务进入队列。</p><button class="btn btn-secondary" type="button" data-worker-reco-empty-reset>清空筛选</button></article>';
    workerRecoDom.list.querySelector("[data-worker-reco-empty-reset]")?.addEventListener("click", resetWorkerRecoFilters);
    return;
  }
  workerRecoDom.list.innerHTML = workerRecoState.filteredItems.map(renderWorkerRecoCard).join("");
}

function renderWorkerRecoCard(item) {
  const active = String(item.id) === String(workerRecoState.selectedId || workerRecoState.filteredItems[0]?.id || "");
  return `<article class="worker-sidebar__card" data-worker-reco-item="${escapeCreativeHtml(item.id)}" tabindex="0" role="button" aria-pressed="${active ? "true" : "false"}">
    <header class="worker-sidebar__card-head">
      <div>
        <h3>${escapeCreativeHtml(item.title)}</h3>
        <p>${escapeCreativeHtml(item.description)}</p>
      </div>
      <span class="worker-reco__badge">${escapeCreativeHtml(getWorkerRecoStatusLabel(item.status))}</span>
    </header>
    <dl class="worker-sidebar__meta">
      <div><dt>负责人</dt><dd>${escapeCreativeHtml(item.assignee)}</dd></div>
      <div><dt>优先级</dt><dd>${escapeCreativeHtml(getWorkerRecoPriorityLabel(item.priority))}</dd></div>
      <div><dt>任务类型</dt><dd>${escapeCreativeHtml(item.taskType)}</dd></div>
      <div><dt>最近完成</dt><dd>${escapeCreativeHtml(String(item.recentDone))}</dd></div>
    </dl>
    <nav class="worker-sidebar__tags" aria-label="推荐标签">${item.tags.map((tag) => `<span>${escapeCreativeHtml(tag)}</span>`).join("")}</nav>
    <div class="worker-sidebar__actions">
      <button class="btn btn-secondary ${active ? "is-active" : ""}" type="button">查看详情</button>
      <a class="btn btn-primary" href="#数据接入">一键筛选</a>
    </div>
  </article>`;
}

function renderWorkerRecoDetail() {
  if (!workerRecoDom.panel) return;
  const item = workerRecoState.filteredItems.find((entry) => String(entry.id) === String(workerRecoState.selectedId)) || workerRecoState.filteredItems[0];
  if (!item) {
    workerRecoDom.panel.innerHTML = '<article class="worker-sidebar__empty"><h3>暂无数据</h3><p>请选择左侧条目查看推荐详情。</p></article>';
    return;
  }
  workerRecoDom.panel.innerHTML = `
    <article class="worker-sidebar__card">
      <header class="worker-sidebar__card-head">
        <div>
          <h3>${escapeCreativeHtml(item.title)}</h3>
          <p>${escapeCreativeHtml(item.reason)}</p>
        </div>
        <span class="worker-reco__badge">${escapeCreativeHtml(getWorkerRecoStatusLabel(item.status))}</span>
      </header>
      <dl class="worker-sidebar__meta">
        <div><dt>负责人</dt><dd>${escapeCreativeHtml(item.assignee)}</dd></div>
        <div><dt>类型</dt><dd>${escapeCreativeHtml(item.taskType)}</dd></div>
        <div><dt>可领取</dt><dd>${item.canClaim ? "是" : "否"}</dd></div>
        <div><dt>最近完成</dt><dd>${escapeCreativeHtml(String(item.recentDone))}</dd></div>
      </dl>
      <p>${escapeCreativeHtml(item.description)}</p>
      <div class="worker-sidebar__actions">
        <button class="btn btn-primary" type="button" data-worker-reco-claim ${item.canClaim ? "" : "disabled"}>领取任务</button>
        <button class="btn btn-secondary" type="button" data-worker-reco-focus>聚焦筛选</button>
      </div>
    </article>`;
  workerRecoDom.panel.querySelector("[data-worker-reco-claim]")?.addEventListener("click", () => {
    workerRecoState.statusMessage = `${item.title} 已进入领取流程`;
    renderWorkerRecoPanel();
  });
  workerRecoDom.panel.querySelector("[data-worker-reco-focus]")?.addEventListener("click", () => {
    workerRecoState.selectedId = String(item.id);
    renderWorkerRecoPanel();
  });
}

function getWorkerRecoVisibleItems() {
  return workerRecoState.items.filter((item) => {
    const searchText = [item.title, item.description, item.assignee, item.taskType, item.reason, item.tags.join(" ")].join(" ").toLowerCase();
    const matchesSearch = !workerRecoState.search || searchText.includes(workerRecoState.search);
    const matchesType = workerRecoState.type === "all" || item.taskType === workerRecoState.type;
    const matchesFilter = workerRecoState.filter === "all"
      || (workerRecoState.filter === "idle" && item.status === "idle")
      || (workerRecoState.filter === "available" && item.canClaim)
      || (workerRecoState.filter === "busy" && item.status === "busy");
    return matchesSearch && matchesType && matchesFilter;
  });
}

function sortWorkerRecoItems(items) {
  const statusWeight = { idle: 4, available: 3, busy: 2, paused: 1, offline: 0, blocked: 0, done: 0 };
  return [...items].sort((a, b) => (statusWeight[b.status] || 0) - (statusWeight[a.status] || 0) || b.recentDone - a.recentDone);
}

function resetWorkerRecoFilters() {
  workerRecoState.search = "";
  workerRecoState.type = "all";
  workerRecoState.filter = "all";
  if (workerRecoDom.search) workerRecoDom.search.value = "";
  if (workerRecoDom.type) workerRecoDom.type.value = "all";
  workerRecoDom.quickFilters?.querySelectorAll("button").forEach((button) => {
    const active = button.dataset.workerRecoFilter === "all";
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-pressed", active ? "true" : "false");
  });
  renderWorkerRecoPanel();
}

function getWorkerRecoStatusLabel(status) {
  const labels = { idle: "空闲", available: "可领取", busy: "繁忙", paused: "暂停", offline: "离线", blocked: "阻塞", done: "完成" };
  return labels[status] || "未知";
}

function getWorkerRecoPriorityLabel(priority) {
  const labels = { urgent: "紧急", high: "高", medium: "中", low: "低" };
  return labels[priority] || "中";
}

function getWorkerRecoFilterLabel(filter) {
  const labels = { all: "全部", idle: "空闲", available: "可领取", busy: "繁忙" };
  return labels[filter] || "全部";
}
