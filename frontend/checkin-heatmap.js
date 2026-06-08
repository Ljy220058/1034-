const checkinHeatmapState = {
  loading: true,
  error: '',
  rows: [],
  summary: null,
};

const checkinHeatmapRefs = {};

if (typeof document !== 'undefined') {
  document.addEventListener('DOMContentLoaded', initCheckinHeatmap);
}

function initCheckinHeatmap() {
  checkinHeatmapRefs.root = document.querySelector('[data-checkin-heatmap-panel]');
  if (!checkinHeatmapRefs.root) return;
  checkinHeatmapRefs.shell = checkinHeatmapRefs.root.querySelector('[data-checkin-heatmap-shell]');
  checkinHeatmapRefs.summary = checkinHeatmapRefs.root.querySelector('[data-checkin-heatmap-summary]');
  checkinHeatmapRefs.retry = checkinHeatmapRefs.root.querySelector('[data-checkin-heatmap-retry]');
  checkinHeatmapRefs.range = checkinHeatmapRefs.root.querySelector('[data-checkin-range]');
  checkinHeatmapRefs.member = checkinHeatmapRefs.root.querySelector('[data-checkin-member]');
  checkinHeatmapRefs.refresh = checkinHeatmapRefs.root.querySelector('[data-checkin-refresh]');
  checkinHeatmapRefs.year = checkinHeatmapRefs.root.querySelector('[data-checkin-year]');
  bindCheckinHeatmapEvents();
  renderCheckinHeatmapLoading();
  fetchCheckinHeatmapData();
}

function bindCheckinHeatmapEvents() {
  checkinHeatmapRefs.refresh?.addEventListener('click', handleCheckinHeatmapRefreshClick);
  checkinHeatmapRefs.retry?.addEventListener('click', handleCheckinHeatmapRetryClick);
  checkinHeatmapRefs.range?.addEventListener('change', handleCheckinHeatmapFilterChange);
  checkinHeatmapRefs.member?.addEventListener('change', handleCheckinHeatmapFilterChange);
}

function handleCheckinHeatmapRefreshClick() {
  if (checkinHeatmapState.loading) return;
  fetchCheckinHeatmapData();
}

function handleCheckinHeatmapRetryClick() {
  if (checkinHeatmapState.loading) return;
  fetchCheckinHeatmapData();
}

function handleCheckinHeatmapFilterChange() {
  if (checkinHeatmapState.loading) return;
  fetchCheckinHeatmapData();
}

async function fetchCheckinHeatmapData() {
  checkinHeatmapState.loading = true;
  checkinHeatmapState.error = '';
  renderCheckinHeatmapLoading();
  try {
    const apiClient = window.apiClient;
    if (!apiClient?.fetchCheckinStats) {
      throw new Error('打卡热力图接口尚未接入');
    }
    const payload = await apiClient.fetchCheckinStats({
      year: checkinHeatmapRefs.year?.value || '',
      range: checkinHeatmapRefs.range?.value || '365',
      memberId: checkinHeatmapRefs.member?.value || 'all',
    });
    const normalized = normalizeCheckinHeatmapPayload(payload);
    checkinHeatmapState.rows = normalized.rows;
    checkinHeatmapState.summary = normalized.summary;
    checkinHeatmapState.loading = false;
    renderCheckinHeatmap();
  } catch (error) {
    checkinHeatmapState.loading = false;
    checkinHeatmapState.error = error instanceof Error ? error.message : '加载失败，请稍后重试';
    checkinHeatmapState.rows = [];
    checkinHeatmapState.summary = null;
    renderCheckinHeatmap();
  }
}

function renderCheckinHeatmapLoading() {
  syncCheckinHeatmapControls();
  if (!checkinHeatmapRefs.shell) return;
  checkinHeatmapRefs.shell.innerHTML = `
    <section class="checkin-state">
      <div class="state-inline"><span class="spinner" aria-hidden="true"></span><h3>热力图加载中</h3></div>
      <p>正在同步 365 天打卡数据。</p>
    </section>
    <section class="checkin-skeleton" aria-hidden="true">
      <article></article><article></article><article></article><article></article>
    </section>`;
}

function renderCheckinHeatmap() {
  syncCheckinHeatmapControls();
  renderCheckinHeatmapSummary();
  if (!checkinHeatmapRefs.shell) return;
  if (checkinHeatmapState.error) {
    checkinHeatmapRefs.shell.innerHTML = `
      <section class="checkin-state is-error">
        <div>
          <h3>热力图加载失败</h3>
          <p>${escapeCheckinHeatmapHtml(checkinHeatmapState.error)}</p>
        </div>
        <button class="btn btn-primary" type="button" data-checkin-inline-retry>重试</button>
      </section>`;
    checkinHeatmapRefs.shell.querySelector('[data-checkin-inline-retry]')?.addEventListener('click', handleCheckinHeatmapRetryClick);
    return;
  }
  if (!checkinHeatmapState.rows.length) {
    checkinHeatmapRefs.shell.innerHTML = `
      <section class="checkin-empty">
        <div>
          <h3>暂无数据</h3>
          <p>当前没有可展示的打卡记录，等成员完成打卡后这里会自动更新。</p>
        </div>
      </section>`;
    return;
  }
  const weeks = groupCheckinHeatmapWeeks(checkinHeatmapState.rows);
  const legend = getCheckinHeatmapLegend(checkinHeatmapState.rows);
  checkinHeatmapRefs.shell.innerHTML = `
    <section class="checkin-heatmap" aria-label="打卡热力图">
      <header class="checkin-heatmap__legend">
        ${legend.map((item) => `<span><i data-tone="${item.tone}"></i>${escapeCheckinHeatmapHtml(item.label)}</span>`).join('')}
      </header>
      <section class="checkin-grid" aria-label="365 天打卡网格">
        ${weeks.map(renderCheckinHeatmapWeek).join('')}
      </section>
    </section>`;
}

function renderCheckinHeatmapSummary() {
  if (!checkinHeatmapRefs.summary) return;
  const summary = checkinHeatmapState.summary || {};
  const maxStreak = Number(summary.maxStreak ?? 0);
  const currentStreak = Number(summary.currentStreak ?? 0);
  const monthDays = Number(summary.monthDays ?? 0);
  checkinHeatmapRefs.summary.innerHTML = `
    <span class="summary-chip"><strong>${escapeCheckinHeatmapHtml(checkinHeatmapHeatLabel(currentStreak))}</strong></span>
    <span class="summary-chip">连续打卡 ${escapeCheckinHeatmapHtml(String(currentStreak))} 天</span>
    <span class="summary-chip">最长记录 ${escapeCheckinHeatmapHtml(String(maxStreak))} 天</span>
    <span class="summary-chip">本月 ${escapeCheckinHeatmapHtml(String(monthDays))} 天</span>`;
}

function syncCheckinHeatmapControls() {
  const loading = checkinHeatmapState.loading;
  [checkinHeatmapRefs.refresh, checkinHeatmapRefs.retry, checkinHeatmapRefs.range, checkinHeatmapRefs.member].forEach((element) => {
    if (!element) return;
    element.disabled = loading;
  });
  if (checkinHeatmapRefs.refresh) checkinHeatmapRefs.refresh.textContent = loading ? '加载中' : '刷新热力';
  if (checkinHeatmapRefs.retry) checkinHeatmapRefs.retry.textContent = loading ? '加载中' : '重试';
}

function normalizeCheckinHeatmapPayload(payload) {
  const rows = Array.isArray(payload) ? payload : payload?.data || payload?.days || payload?.items || [];
  return {
    rows: rows.map((item, index) => ({
      date: item.date || item.day || item.record_date || `day-${index + 1}`,
      count: Number(item.count ?? item.times ?? item.checkins ?? item.value ?? 0),
      label: item.label || item.member || item.name || '',
    })),
    summary: payload?.summary || payload?.stats || payload?.data?.summary || payload?.meta || null,
  };
}

function groupCheckinHeatmapWeeks(rows) {
  const padded = Array.from({ length: 365 }, (_, index) => rows[index] || { date: `day-${index + 1}`, count: 0, label: '' });
  const weeks = [];
  for (let index = 0; index < padded.length; index += 7) {
    weeks.push(padded.slice(index, index + 7));
  }
  return weeks;
}

function renderCheckinHeatmapWeek(week, weekIndex) {
  return `<article class="checkin-week" aria-label="第 ${weekIndex + 1} 周">${week.map((item, dayIndex) => renderCheckinHeatmapDay(item, weekIndex * 7 + dayIndex)).join('')}</article>`;
}

function renderCheckinHeatmapDay(item, index) {
  const tone = getCheckinHeatmapTone(item.count);
  const title = `${item.date} · ${item.count} 次打卡`;
  return `<button class="checkin-day" type="button" data-tone="${tone}" title="${escapeCheckinHeatmapHtml(title)}" aria-label="${escapeCheckinHeatmapHtml(title)}"><span>${escapeCheckinHeatmapHtml(String(item.count))}</span></button>`;
}

function getCheckinHeatmapTone(count) {
  if (count >= 4) return 'hot';
  if (count >= 2) return 'warm';
  if (count >= 1) return 'idle';
  return 'none';
}

function getCheckinHeatmapLegend(rows) {
  const counts = rows.map((item) => Number(item.count || 0));
  const max = Math.max(0, ...counts);
  return [
    { label: '无打卡', tone: 'none' },
    { label: '低频', tone: 'idle' },
    { label: '中频', tone: 'warm' },
    { label: `高频（最高 ${max} 次）`, tone: 'hot' },
  ];
}

function checkinHeatmapHeatLabel(value) {
  if (value >= 60) return '状态火热';
  if (value >= 20) return '持续活跃';
  if (value >= 7) return '稳步坚持';
  return '刚刚开始';
}

function escapeCheckinHeatmapHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}
