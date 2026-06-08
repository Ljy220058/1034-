const leaderboardState = {
  mode: 'total',
  loading: true,
  retrying: false,
  error: '',
  rows: [],
};

const leaderboardRefs = {};

if (typeof document !== 'undefined') {
  document.addEventListener('DOMContentLoaded', initLeaderboard);
}

function initLeaderboard() {
  leaderboardRefs.root = document.querySelector('[data-leaderboard-panel]');
  if (!leaderboardRefs.root) return;
  leaderboardRefs.summary = leaderboardRefs.root.querySelector('[data-leaderboard-summary]');
  leaderboardRefs.shell = leaderboardRefs.root.querySelector('[data-leaderboard-shell]');
  leaderboardRefs.retry = leaderboardRefs.root.querySelector('[data-leaderboard-retry]');
  leaderboardRefs.tabs = Array.from(leaderboardRefs.root.querySelectorAll('[data-leaderboard-tab]'));
  bindLeaderboardEvents();
  renderLeaderboardLoading();
  fetchLeaderboardData();
}

function bindLeaderboardEvents() {
  leaderboardRefs.tabs.forEach((button) => {
    button.addEventListener('click', handleLeaderboardTabClick);
  });
  leaderboardRefs.retry?.addEventListener('click', handleLeaderboardRetryClick);
}

function handleLeaderboardTabClick(event) {
  const nextMode = event.currentTarget.dataset.mode || 'total';
  if (leaderboardState.mode === nextMode || leaderboardState.loading) return;
  leaderboardState.mode = nextMode;
  fetchLeaderboardData();
}

function handleLeaderboardRetryClick() {
  if (leaderboardState.loading || leaderboardState.retrying) return;
  leaderboardState.retrying = true;
  fetchLeaderboardData();
}

async function fetchLeaderboardData() {
  leaderboardState.loading = true;
  leaderboardState.error = '';
  renderLeaderboardLoading();
  try {
    const apiClient = window.apiClient;
    if (!apiClient?.fetchLeaderboard) {
      throw new Error('排行榜接口尚未接入');
    }
    const rows = await apiClient.fetchLeaderboard({ mode: leaderboardState.mode });
    leaderboardState.rows = Array.isArray(rows) ? rows : [];
    leaderboardState.loading = false;
    leaderboardState.retrying = false;
    renderLeaderboard();
  } catch (error) {
    leaderboardState.loading = false;
    leaderboardState.retrying = false;
    leaderboardState.error = error instanceof Error ? error.message : '加载失败，请稍后重试';
    leaderboardState.rows = [];
    renderLeaderboard();
  }
}

function renderLeaderboardLoading() {
  syncLeaderboardControls();
  if (leaderboardRefs.summary) {
    leaderboardRefs.summary.innerHTML = '<span class="summary-chip">加载中</span><span class="summary-chip">正在同步跑量数据</span>';
  }
  if (leaderboardRefs.shell) {
    leaderboardRefs.shell.innerHTML = `
      <section class="leaderboard-state">
        <div class="state-inline"><span class="spinner" aria-hidden="true"></span><h3>排行榜加载中</h3></div>
        <p>正在读取成员跑量、月度里程与打卡天数。</p>
      </section>
      <section class="leaderboard-podium" aria-hidden="true">
        <article class="leaderboard-skeleton"></article>
        <article class="leaderboard-skeleton"></article>
        <article class="leaderboard-skeleton"></article>
      </section>
      <section class="leaderboard-list" aria-hidden="true">
        <article class="leaderboard-skeleton"></article>
        <article class="leaderboard-skeleton"></article>
      </section>`;
  }
}

function renderLeaderboard() {
  syncLeaderboardControls();
  renderLeaderboardSummary();
  if (!leaderboardRefs.shell) return;
  if (leaderboardState.error) {
    leaderboardRefs.shell.innerHTML = `
      <section class="leaderboard-state is-error">
        <div>
          <h3>排行榜加载失败</h3>
          <p>${escapeLeaderboardHtml(leaderboardState.error)}</p>
        </div>
        <button class="btn btn-primary" type="button" data-leaderboard-inline-retry>重试</button>
      </section>`;
    leaderboardRefs.shell.querySelector('[data-leaderboard-inline-retry]')?.addEventListener('click', handleLeaderboardRetryClick);
    return;
  }
  if (!leaderboardState.rows.length) {
    leaderboardRefs.shell.innerHTML = `
      <section class="leaderboard-empty">
        <div>
          <h3>暂无数据</h3>
          <p>当前榜单还没有跑量记录，等成员打卡后这里会自动更新。</p>
        </div>
      </section>`;
    return;
  }
  const podiumRows = leaderboardState.rows.slice(0, 3);
  const listRows = leaderboardState.rows.slice(3);
  leaderboardRefs.shell.innerHTML = `
    <section class="leaderboard-podium" aria-label="前三名">
      ${podiumRows.map((item, index) => renderLeaderboardCard(item, index, true)).join('')}
    </section>
    <section class="leaderboard-list" aria-label="完整榜单">
      ${listRows.map((item, index) => renderLeaderboardCard(item, index + 3, false)).join('')}
    </section>`;
}

function renderLeaderboardSummary() {
  if (!leaderboardRefs.summary) return;
  const totalMembers = leaderboardState.rows.length;
  const modeLabel = leaderboardState.mode === 'monthly' ? '月榜' : '总榜';
  const leader = leaderboardState.rows[0];
  const leaderText = leader ? `${leader.name} ${formatDistance(leaderboardState.mode === 'monthly' ? leader.monthlyDistanceKm : leader.totalDistanceKm)}` : '等待刷新';
  leaderboardRefs.summary.innerHTML = `
    <span class="summary-chip"><strong>${escapeLeaderboardHtml(modeLabel)}</strong></span>
    <span class="summary-chip">成员数 ${escapeLeaderboardHtml(String(totalMembers))}</span>
    <span class="summary-chip">榜首 ${escapeLeaderboardHtml(leaderText)}</span>`;
}

function renderLeaderboardCard(item, index, highlightTop) {
  const rank = Number(item.rank || index + 1) || index + 1;
  const topClass = rank === 1 ? ' is-top-1' : rank === 2 ? ' is-top-2' : rank === 3 ? ' is-top-3' : '';
  const badgeText = rank <= 3 ? ['金牌冲线', '银牌跟跑', '铜牌稳住'][rank - 1] : `第 ${rank} 名`;
  return `
    <article class="leaderboard-card${highlightTop ? topClass : ''}">
      <div class="leaderboard-rank" aria-label="第 ${rank} 名">${rank}</div>
      <div class="leaderboard-card__main">
        <div class="leaderboard-avatar" aria-hidden="true">${escapeLeaderboardHtml(String(item.avatarText || '跑').slice(0, 1))}</div>
        <section class="leaderboard-card__meta">
          <h3 class="leaderboard-card__name">${escapeLeaderboardHtml(item.name || '未命名成员')}</h3>
          <span class="leaderboard-card__badge">${escapeLeaderboardHtml(badgeText)}</span>
          <p>${leaderboardState.mode === 'monthly' ? '本月冲刺榜' : '累计坚持榜'}</p>
        </section>
      </div>
      <dl class="leaderboard-card__stats">
        <div>
          <span>总跑量</span>
          <strong>${escapeLeaderboardHtml(formatDistance(item.totalDistanceKm))}</strong>
        </div>
        <div>
          <span>本月跑量</span>
          <strong>${escapeLeaderboardHtml(formatDistance(item.monthlyDistanceKm))}</strong>
        </div>
        <div>
          <span>打卡天数</span>
          <strong>${escapeLeaderboardHtml(formatDays(item.checkInDays))}</strong>
        </div>
      </dl>
    </article>`;
}

function syncLeaderboardControls() {
  leaderboardRefs.tabs.forEach((button) => {
    const active = button.dataset.mode === leaderboardState.mode;
    button.classList.toggle('is-active', active);
    button.setAttribute('aria-pressed', active ? 'true' : 'false');
    button.disabled = leaderboardState.loading;
  });
  if (leaderboardRefs.retry) {
    leaderboardRefs.retry.disabled = leaderboardState.loading;
    leaderboardRefs.retry.textContent = leaderboardState.retrying || leaderboardState.loading ? '加载中' : '重新加载';
  }
}

function formatDistance(value) {
  return `${Number(value || 0).toFixed(1)} km`;
}

function formatDays(value) {
  return `${Math.max(0, Number(value || 0))} 天`;
}

function escapeLeaderboardHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}
