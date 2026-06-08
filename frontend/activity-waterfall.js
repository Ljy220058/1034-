const API_URL = "/api/v1/activities";

const sampleActivities = [
  {
    id: "a-001",
    title: "校园夜跑接力",
    type: "campus",
    coverLabel: "夜跑 · 深技大",
    distanceKm: 8.4,
    pace: "5'18\"/km",
    runner: "阿柠",
    completed: 18,
    reasoning: "夜间路线安全、补给清晰，适合快速组织同学参加",
    likes: 42,
    comments: 11,
    tags: ["夜跑", "操场", "新手友好"],
    coverTone: "campus",
    coverSize: "medium",
    campus: "西丽湖",
    month: "06"
  },
  {
    id: "a-002",
    title: "周末速度课",
    type: "speed",
    coverLabel: "速度 · PB 向",
    distanceKm: 12.2,
    pace: "4'26\"/km",
    runner: "跑团教练",
    completed: 9,
    reasoning: "节奏明确、训练目标单一，适合安排给想提升配速的成员",
    likes: 31,
    comments: 7,
    tags: ["间歇", "配速", "PB"],
    coverTone: "speed",
    coverSize: "tall",
    campus: "官龙山",
    month: "05"
  },
  {
    id: "a-003",
    title: "社交慢跑见面会",
    type: "social",
    coverLabel: "社交 · 轻松聊跑",
    distanceKm: 5.5,
    pace: "6'42\"/km",
    runner: "星星",
    completed: 24,
    reasoning: "路线轻松、话题丰富，适合拉新和跨院系联动",
    likes: 56,
    comments: 15,
    tags: ["拉新", "跨院系", "轻松"],
    coverTone: "social",
    coverSize: "short",
    campus: "北区",
    month: "04"
  },
  {
    id: "a-004",
    title: "晨曦节奏跑",
    type: "campus",
    coverLabel: "晨跑 · 清爽开局",
    distanceKm: 10.0,
    pace: "5'00\"/km",
    runner: "芝士",
    completed: 13,
    reasoning: "清晨气温更稳，适合把训练和校园景观结合起来",
    likes: 38,
    comments: 9,
    tags: ["晨跑", "节奏", "风景"],
    coverTone: "campus",
    coverSize: "medium",
    campus: "西丽湖",
    month: "03"
  }
];

const state = {
  items: [],
  filteredItems: [],
  likedIds: new Set(),
  loading: true,
  error: "",
  query: "",
  sort: "hot",
  filters: {
    distance: "all",
    pace: "all",
    campus: "all",
    month: "all"
  }
};

const dom = {};

if (typeof document !== "undefined") {
  document.addEventListener("DOMContentLoaded", initActivityWaterfall);
}

function initActivityWaterfall() {
  bindElements();
  if (!hasActivityWaterfallRoot()) return;
  bindEvents();
  fetchActivities();
}

function hasActivityWaterfallRoot() {
  return Boolean(dom.list && dom.state && dom.summary);
}

function bindElements() {
  dom.list = document.querySelector("[data-activity-list]");
  dom.state = document.querySelector("[data-activity-state]");
  dom.summary = document.querySelector("[data-activity-summary]");
  dom.search = document.querySelector("[data-activity-search]");
  dom.sort = document.querySelector("[data-activity-sort]");
  dom.refresh = document.querySelector("[data-activity-refresh]");
  dom.filters = Array.from(document.querySelectorAll("[data-activity-filter]"));
  dom.heatmap = document.querySelector("[data-activity-heatmap]");
  dom.heatmapGrid = document.querySelector("[data-activity-heatmap-grid]");
  dom.heatmapCount = document.querySelector("[data-activity-heatmap-count]");
  dom.heroTotal = document.querySelector("[data-hero-total]");
  dom.heroDistance = document.querySelector("[data-hero-distance]");
  dom.heroRunners = document.querySelector("[data-hero-runners]");
  dom.heroSocial = document.querySelector("[data-hero-social]");
}

function bindEvents() {
  dom.search?.addEventListener("input", handleSearchInput);
  dom.sort?.addEventListener("change", handleSortChange);
  dom.refresh?.addEventListener("click", handleRefreshClick);
  dom.filters.forEach((button) => button.addEventListener("click", handleFilterClick));
}

async function fetchActivities() {
  setLoading(true);
  renderActivityBoard();
  try {
    const response = await fetch(API_URL, { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error(`请求失败：${response.status}`);
    const payload = await response.json();
    const items = normalizeActivities(payload);
    state.items = items;
    state.error = "";
    setLoading(false);
    renderActivityBoard();
  } catch (error) {
    state.error = "网络错误，无法读取活动列表。";
    state.items = [];
    setLoading(false);
    renderActivityBoard();
  }
}

function normalizeActivities(payload) {
  const list = Array.isArray(payload) ? payload : Array.isArray(payload?.data) ? payload.data : Array.isArray(payload?.items) ? payload.items : [];
  return list.map((item, index) => {
    const distanceKm = Number(item.distanceKm ?? item.distance_km ?? item.distance ?? 0);
    const pace = item.pace ?? item.avg_pace ?? "--";
    const month = normalizeMonth(item.month ?? item.activity_month ?? item.date ?? item.started_at ?? item.created_at);
    const campus = normalizeCampus(item.campus ?? item.campus_name ?? item.location ?? item.route_area ?? item.place);
    return {
      id: item.id ?? `activity-${index}`,
      title: item.title ?? item.name ?? "未命名活动",
      type: item.type ?? item.category ?? inferTypeFromPace(pace),
      coverLabel: item.coverLabel ?? item.cover_label ?? "精选活动",
      distanceKm,
      pace,
      runner: item.runner ?? item.nickname ?? item.host ?? "匿名成员",
      completed: Number(item.completed ?? item.completed_count ?? item.done_count ?? 0),
      reasoning: item.reasoning ?? item.reason ?? item.suggestion ?? "推荐原因未返回，默认按热度展示。",
      likes: Number(item.likes ?? item.like_count ?? 0),
      comments: Number(item.comments ?? item.comment_count ?? 0),
      tags: Array.isArray(item.tags) ? item.tags : Array.isArray(item.labels) ? item.labels : [],
      coverTone: item.coverTone ?? item.cover_tone ?? item.type ?? "social",
      coverSize: item.coverSize ?? item.cover_size ?? ["short", "medium", "tall"][index % 3],
      coverUrl: item.coverUrl ?? item.cover_url ?? item.cover ?? "",
      campus,
      month,
      distanceBucket: getDistanceBucket(distanceKm),
      paceBucket: getPaceBucket(pace)
    };
  });
}

function handleSearchInput(event) {
  state.query = event.target.value.trim();
  renderActivityBoard();
}

function handleSortChange(event) {
  state.sort = event.target.value;
  renderActivityBoard();
}

function handleFilterClick(event) {
  const group = event.currentTarget.dataset.activityFilterGroup || "distance";
  const value = event.currentTarget.dataset.activityFilter || "all";
  state.filters[group] = value;
  dom.filters
    .filter((button) => (button.dataset.activityFilterGroup || "distance") === group)
    .forEach((button) => {
      const active = button === event.currentTarget;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-pressed", active ? "true" : "false");
    });
  renderActivityBoard();
}

function handleRefreshClick() {
  fetchActivities();
}

function handleClearSearchClick() {
  state.query = "";
  state.filters = { distance: "all", pace: "all", campus: "all", month: "all" };
  if (dom.search) dom.search.value = "";
  dom.filters.forEach((button) => {
    const active = (button.dataset.activityFilter || "all") === "all";
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-pressed", active ? "true" : "false");
  });
  renderActivityBoard();
}

function setLoading(isLoading) {
  state.loading = isLoading;
  if (dom.refresh) dom.refresh.disabled = isLoading;
  if (dom.search) dom.search.disabled = isLoading;
  if (dom.sort) dom.sort.disabled = isLoading;
  dom.filters.forEach((button) => (button.disabled = isLoading));
}

function renderActivityBoard() {
  const filtered = getFilteredActivities();
  state.filteredItems = sortActivities(filtered);
  renderHeroStats();
  renderHeatmapSummary();
  renderSummary();
  renderState();
  renderList();
}

function getFilteredActivities() {
  return filterActivities(state.items, state.query, state.filters);
}

function filterActivities(items, query, filters) {
  const current = filters || {};
  return items.filter((item) => {
    const searchableText = [item.title, item.runner, item.reasoning, item.campus, getMonthLabel(item.month), ...(item.tags || [])].join(" ").toLowerCase();
    const matchesQuery = query ? searchableText.includes(String(query).toLowerCase()) : true;
    const matchesDistance = current.distance === "all" || !current.distance ? true : item.distanceBucket === current.distance;
    const matchesPace = current.pace === "all" || !current.pace ? true : item.paceBucket === current.pace;
    const matchesCampus = current.campus === "all" || !current.campus ? true : item.campus === current.campus;
    const matchesMonth = current.month === "all" || !current.month ? true : item.month === current.month;
    return matchesQuery && matchesDistance && matchesPace && matchesCampus && matchesMonth;
  });
}

function sortActivities(items) {
  const sorted = [...items];
  sorted.sort((a, b) => {
    if (state.sort === "distance") return b.distanceKm - a.distanceKm;
    if (state.sort === "pace") return paceToSeconds(a.pace) - paceToSeconds(b.pace);
    return getActivityHeat(b) - getActivityHeat(a);
  });
  return sorted;
}

function paceToSeconds(pace) {
  const match = /^(\d+)'(\d+)"/.exec(String(pace));
  if (!match) return Number.MAX_SAFE_INTEGER;
  return Number(match[1]) * 60 + Number(match[2]);
}

function renderHeroStats() {
  const total = state.items.length;
  const averageDistance = total ? (state.items.reduce((sum, item) => sum + item.distanceKm, 0) / total).toFixed(1) : "0.0";
  const activeRunners = new Set(state.items.map((item) => item.runner)).size;
  const totalSocial = state.items.reduce((sum, item) => sum + item.likes + item.comments, 0);

  if (dom.heroTotal) dom.heroTotal.textContent = total;
  if (dom.heroDistance) dom.heroDistance.textContent = `${averageDistance}K`;
  if (dom.heroRunners) dom.heroRunners.textContent = activeRunners;
  if (dom.heroSocial) dom.heroSocial.textContent = totalSocial;
}

function renderHeatmapSummary() {
  if (!dom.heatmapGrid) return;
  if (state.loading) {
    dom.heatmapGrid.innerHTML = '<article class="activity-heatmap__item"><span>热门校区</span><strong>加载中</strong></article><article class="activity-heatmap__item"><span>高热月份</span><strong>加载中</strong></article><article class="activity-heatmap__item"><span>最长路线</span><strong>加载中</strong></article><article class="activity-heatmap__item"><span>最快配速</span><strong>加载中</strong></article>';
    if (dom.heatmapCount) dom.heatmapCount.textContent = "同步中";
    return;
  }
  const summary = buildHeatmapSummary(state.filteredItems);
  if (dom.heatmapCount) dom.heatmapCount.textContent = state.error ? "接口异常" : `当前 ${state.filteredItems.length} 条`;
  dom.heatmapGrid.innerHTML = `
    <article class="activity-heatmap__item"><span>热门校区</span><strong>${escapeHtml(summary.topCampus)}</strong></article>
    <article class="activity-heatmap__item"><span>高热月份</span><strong>${escapeHtml(summary.topMonth)}</strong></article>
    <article class="activity-heatmap__item"><span>最长路线</span><strong>${escapeHtml(summary.longestDistance)}</strong></article>
    <article class="activity-heatmap__item"><span>最快配速</span><strong>${escapeHtml(summary.fastestPace)}</strong></article>
  `;
}

function buildHeatmapSummary(items) {
  if (!items.length) {
    return { topCampus: "暂无数据", topMonth: "暂无数据", longestDistance: "暂无数据", fastestPace: "暂无数据" };
  }
  const topCampus = getTopByHeat(items, "campus");
  const topMonth = getTopByHeat(items, "month");
  const longest = items.reduce((winner, item) => item.distanceKm > winner.distanceKm ? item : winner, items[0]);
  const fastest = items.reduce((winner, item) => paceToSeconds(item.pace) < paceToSeconds(winner.pace) ? item : winner, items[0]);
  return {
    topCampus: `${topCampus.label} · 热度 ${topCampus.heat}`,
    topMonth: `${getMonthLabel(topMonth.label)} · 热度 ${topMonth.heat}`,
    longestDistance: `${longest.distanceKm.toFixed(1)}K · ${longest.title}`,
    fastestPace: `${fastest.pace} · ${fastest.title}`
  };
}

function getTopByHeat(items, key) {
  const bucket = new Map();
  items.forEach((item) => {
    const label = item[key] || "未标注";
    const current = bucket.get(label) || 0;
    bucket.set(label, current + getActivityHeat(item));
  });
  return Array.from(bucket.entries()).reduce((winner, entry) => {
    const candidate = { label: entry[0], heat: entry[1] };
    return candidate.heat > winner.heat ? candidate : winner;
  }, { label: "未标注", heat: 0 });
}

function getActivityHeat(item) {
  return Number(item.likes || 0) + Number(item.comments || 0) + Number(item.completed || 0);
}

function renderSummary() {
  const chips = [
    `共 ${state.filteredItems.length} 条`,
    `距离：${getDistanceLabel(state.filters.distance)}`,
    `配速：${getPaceLabel(state.filters.pace)}`,
    `校区：${state.filters.campus === "all" ? "全部" : state.filters.campus}`,
    `月份：${getMonthLabel(state.filters.month)}`,
    state.query ? `关键词：${state.query}` : "未输入关键词",
    `排序：${getSortLabel(state.sort)}`
  ];
  dom.summary.innerHTML = chips.map((text) => `<span class="summary-chip">${escapeHtml(text)}</span>`).join("");
}

function renderState() {
  if (state.loading) {
    dom.state.className = "activity-state";
    dom.state.innerHTML = '<div class="activity-state__inline"><span class="spinner" aria-hidden="true"></span><h3>加载中</h3></div><p>正在读取活动列表。</p>';
    return;
  }
  if (state.error) {
    dom.state.className = "activity-state is-error";
    dom.state.innerHTML = `<div class="activity-state__inline"><h3>网络错误</h3></div><p>${escapeHtml(state.error)}</p><button class="btn btn-primary" type="button" data-retry>重试</button>`;
    dom.state.querySelector("[data-retry]").addEventListener("click", handleRefreshClick);
    return;
  }
  if (!state.filteredItems.length) {
    dom.state.className = "activity-state";
    const emptyTitle = state.items.length ? "筛选无结果" : "暂无数据";
    const emptyMessage = state.items.length ? "当前距离、配速、校区或月份组合下没有活动卡片，试试横向滑动筛选芯片并切换条件。" : "活动列表为空，创建第一条活动后即可在瀑布流展示。";
    dom.state.innerHTML = `<div class="activity-state__inline"><h3>${emptyTitle}</h3></div><p>${emptyMessage}</p>`;
    return;
  }
  dom.state.className = "activity-state";
  dom.state.innerHTML = `<div class="activity-state__inline"><h3>已加载</h3></div><p>当前展示 ${state.filteredItems.length} 条活动卡片。</p>`;
}

function renderList() {
  if (state.loading) {
    dom.list.innerHTML = '<article class="skeleton-card" aria-hidden="true"></article><article class="skeleton-card" aria-hidden="true"></article><article class="skeleton-card" aria-hidden="true"></article>';
    return;
  }
  if (!state.filteredItems.length) {
    const isSearchEmpty = Boolean(state.items.length);
    const emptyOptions = isSearchEmpty
      ? { kind: "search", actionType: "button" }
      : { kind: "list" };
    dom.list.innerHTML = `<article class="activity-empty-shell">${window.renderEmptyState ? window.renderEmptyState(emptyOptions) : "<section class=\"panel-empty\"><h3>暂无数据</h3><p>当前没有可展示的活动。</p></section>"}</article>`;
    dom.list.querySelector('[data-empty-action="search"]')?.addEventListener("click", handleClearSearchClick);
    return;
  }
  dom.list.innerHTML = state.filteredItems.map(renderActivityCard).join("");
  dom.list.querySelectorAll("[data-card-action]").forEach((button) => button.addEventListener("click", handleCardAction));
}

function renderActivityCard(item) {
  const toneClass = item.coverTone === "speed" ? "activity-badge--green" : item.coverTone === "campus" ? "activity-badge--blue" : "";
  const liked = state.likedIds.has(String(item.id));
  const likeLabel = liked ? `已赞 ${item.likes}` : `点赞 ${item.likes}`;
  return `
    <article class="activity-card">
      <header class="activity-card__cover" style="${escapeHtml(getCoverStyle(item))}">
        <div class="activity-card__cover-text">
          <span>${escapeHtml(item.coverLabel)}</span>
          <strong>${escapeHtml(item.title)}</strong>
        </div>
      </header>
      <div class="activity-card__body">
        <div class="activity-card__meta">
          <span class="activity-badge ${toneClass}">${escapeHtml(getTypeLabel(item.type))}</span>
          <span class="activity-badge">${escapeHtml(item.distanceKm.toFixed(1))}K</span>
          <span class="activity-badge">${escapeHtml(item.pace)}</span>
          <span class="activity-badge">${escapeHtml(item.campus)}</span>
          <span class="activity-badge">${escapeHtml(getMonthLabel(item.month))}</span>
        </div>
        <h3>${escapeHtml(item.title)}</h3>
        <p class="activity-card__desc">${escapeHtml(item.reasoning)}</p>
        <div class="activity-card__runner">
          <span class="avatar" aria-hidden="true">${escapeHtml(getAvatarText(item.runner))}</span>
          <div>
            <div>${escapeHtml(item.runner)}</div>
            <div>${escapeHtml(`最近完成 ${item.completed} 次`)}</div>
          </div>
        </div>
        <div class="activity-card__tags">${item.tags.map((tag) => `<span class="activity-tag">${escapeHtml(tag)}</span>`).join("")}</div>
        <div class="activity-card__actions">
          <button class="activity-action activity-action--primary ${liked ? "is-liked" : ""}" type="button" data-card-action="like" data-card-id="${escapeHtml(item.id)}">${escapeHtml(likeLabel)}</button>
          <button class="activity-action activity-action--ghost" type="button" data-card-action="comment" data-card-id="${escapeHtml(item.id)}">评论 ${escapeHtml(item.comments)}</button>
        </div>
      </div>
    </article>`;
}

function getCoverStyle(item) {
  const sizeMap = { short: "var(--cover-short)", medium: "var(--cover-medium)", tall: "var(--cover-tall)" };
  const styles = [`--cover-height: ${sizeMap[item.coverSize] || "var(--cover-default)"}`];
  if (item.coverUrl) styles.push(`--cover-image: url('${encodeCssUrl(item.coverUrl)}')`);
  return styles.join("; ");
}

function encodeCssUrl(value) {
  return String(value).replaceAll("\\", "").replaceAll("'", "%27").replaceAll('"', "%22").replaceAll(")", "%29");
}

function handleCardAction(event) {
  const { cardId, action } = event.currentTarget.dataset;
  const item = state.filteredItems.find((entry) => String(entry.id) === String(cardId));
  if (!item) return;
  if (action === "like") {
    const key = String(item.id);
    const liked = state.likedIds.has(key);
    if (liked) {
      state.likedIds.delete(key);
      item.likes = Math.max(0, item.likes - 1);
    } else {
      state.likedIds.add(key);
      item.likes += 1;
    }
    renderActivityBoard();
    return;
  }
  dom.state.className = "activity-state";
  dom.state.innerHTML = `<div class="activity-state__inline"><h3>评论入口</h3></div><p>${escapeHtml(item.title)} 当前有 ${escapeHtml(item.comments)} 条评论，后续可接入活动评论详情页。</p>`;
}

function normalizeMonth(value) {
  const raw = String(value || "").trim();
  if (!raw) return "未标注";
  const matched = raw.match(/(?:^|[-/年\s])(0?[1-9]|1[0-2])(?:月|[-/\s]|$)/);
  const direct = raw.match(/^(0?[1-9]|1[0-2])$/);
  const month = matched?.[1] || direct?.[1] || "";
  return month ? month.padStart(2, "0") : "未标注";
}

function normalizeCampus(value) {
  const raw = String(value || "").trim();
  if (!raw) return "未标注";
  if (raw.includes("西丽")) return "西丽湖";
  if (raw.includes("官龙")) return "官龙山";
  if (raw.includes("北")) return "北区";
  return raw;
}

function getDistanceBucket(distanceKm) {
  if (!Number.isFinite(distanceKm) || distanceKm <= 0) return "unknown";
  if (distanceKm < 5) return "short";
  if (distanceKm <= 10) return "middle";
  return "long";
}

function getPaceBucket(pace) {
  const seconds = paceToSeconds(pace);
  if (!Number.isFinite(seconds) || seconds === Number.MAX_SAFE_INTEGER) return "unknown";
  if (seconds <= 290) return "speed";
  if (seconds <= 360) return "tempo";
  return "easy";
}

function inferTypeFromPace(pace) {
  const bucket = getPaceBucket(pace);
  if (bucket === "speed") return "speed";
  if (bucket === "tempo") return "campus";
  return "social";
}

function getTypeLabel(type) {
  const labels = { campus: "校园感", speed: "速度训练", social: "社交约跑" };
  return labels[type] || "综合推荐";
}

function getDistanceLabel(value) {
  const labels = { all: "全部", short: "5K 内", middle: "5-10K", long: "10K+", unknown: "未标注" };
  return labels[value] || "全部";
}

function getPaceLabel(value) {
  const labels = { all: "全部", easy: "轻松跑", tempo: "节奏跑", speed: "速度课", unknown: "未标注" };
  return labels[value] || "全部";
}

function getMonthLabel(value) {
  if (!value || value === "all") return "全部";
  if (value === "未标注") return "未标注";
  return `${Number(value)} 月`;
}

function getSortLabel(sort) {
  const labels = { hot: "互动热度优先", distance: "距离优先", pace: "配速优先" };
  return labels[sort] || "互动热度优先";
}

function getAvatarText(name) {
  return String(name || "匿名").slice(0, 1).toUpperCase();
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

if (typeof module !== "undefined") {
  module.exports = {
    normalizeActivities,
    filterActivities,
    buildHeatmapSummary,
    paceToSeconds,
    getDistanceBucket,
    getPaceBucket,
    normalizeMonth,
    normalizeCampus
  };
}
