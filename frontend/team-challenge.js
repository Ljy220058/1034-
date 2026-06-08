const teamChallengeState = {
  loading: true,
  error: '',
  retrying: false,
  lastUpdated: '',
  selectedTeamId: '',
  filters: {
    keyword: '',
    scope: 'all',
  },
  data: {
    title: '团队挑战赛',
    subtitle: '查看队伍排行、成员贡献和倒计时状态',
    teams: [],
    countdown: null,
  },
};

if (typeof document !== 'undefined') {
  document.addEventListener('DOMContentLoaded', initTeamChallenge);
}

function initTeamChallenge() {
  const root = document.querySelector('[data-team-challenge]');
  if (!root || !window.apiClient) return;
  const dom = bindTeamChallengeDom(root);
  bindTeamChallengeEvents(dom);
  renderTeamChallengeLoading(dom);
  fetchAndRenderTeamChallenge(dom);
}

function bindTeamChallengeDom(root) {
  return {
    root,
    title: root.querySelector('[data-team-challenge-title]'),
    subtitle: root.querySelector('[data-team-challenge-subtitle]'),
    meta: root.querySelector('[data-team-challenge-meta]'),
    summary: root.querySelector('[data-team-challenge-summary]'),
    filters: Array.from(root.querySelectorAll('[data-team-filter]')),
    keywordInput: root.querySelector('[data-team-keyword]'),
    refreshButton: root.querySelector('[data-team-refresh]'),
    retryButton: root.querySelector('[data-team-retry]'),
    board: root.querySelector('[data-team-board]'),
    roster: root.querySelector('[data-team-roster]'),
    countdown: root.querySelector('[data-team-countdown]'),
    empty: root.querySelector('[data-team-empty]'),
  };
}

function bindTeamChallengeEvents(dom) {
  dom.filters.forEach((button) => button.addEventListener('click', handleTeamFilterClick));
  dom.keywordInput?.addEventListener('input', handleTeamKeywordInput);
  dom.refreshButton?.addEventListener('click', handleTeamRefreshClick);
  dom.retryButton?.addEventListener('click', handleTeamRetryClick);
}

function handleTeamFilterClick(event) {
  const scope = String(event.currentTarget.dataset.teamFilter || 'all');
  teamChallengeState.filters.scope = scope;
  renderTeamChallengeFromActiveRoot();
}

function handleTeamKeywordInput(event) {
  teamChallengeState.filters.keyword = String(event.currentTarget.value || '').trim();
  renderTeamChallengeFromActiveRoot();
}

async function handleTeamRefreshClick() {
  const root = document.querySelector('[data-team-challenge]');
  if (!root) return;
  const dom = bindTeamChallengeDom(root);
  await fetchAndRenderTeamChallenge(dom, { force: true });
}

async function handleTeamRetryClick() {
  teamChallengeState.retrying = true;
  const root = document.querySelector('[data-team-challenge]');
  if (!root) return;
  const dom = bindTeamChallengeDom(root);
  renderTeamChallengeError(dom);
  await fetchAndRenderTeamChallenge(dom, { force: true });
}

async function fetchAndRenderTeamChallenge(dom, { force = false } = {}) {
  if (!force && !teamChallengeState.loading && teamChallengeState.data.teams.length) {
    renderTeamChallenge(dom);
    return;
  }
  try {
    teamChallengeState.loading = true;
    teamChallengeState.error = '';
    renderTeamChallengeLoading(dom);
    const payload = await window.apiClient.fetchTeamChallengeOverview({ login_verification: false });
    teamChallengeState.data = normalizeTeamChallenge(payload);
    teamChallengeState.lastUpdated = formatTeamChallengeTime(new Date());
    teamChallengeState.selectedTeamId = teamChallengeState.selectedTeamId || teamChallengeState.data.teams[0]?.id || '';
    teamChallengeState.loading = false;
    teamChallengeState.retrying = false;
    renderTeamChallenge(dom);
  } catch (error) {
    teamChallengeState.loading = false;
    teamChallengeState.retrying = false;
    teamChallengeState.error = error?.message || '加载团队挑战赛失败';
    renderTeamChallengeError(dom);
  }
}

function normalizeTeamChallenge(payload) {
  const source = payload?.data || payload || {};
  const teams = Array.isArray(source.teams) ? source.teams : Array.isArray(source.items) ? source.items : [];
  const countdown = source.countdown || source.timer || source.deadline || null;
  return {
    title: source.title || '团队挑战赛',
    subtitle: source.subtitle || '查看队伍排行、成员贡献和倒计时状态',
    teams: teams.map((item, index) => ({
      id: item.id || item.team_id || `team-${index + 1}`,
      name: item.name || item.team_name || `第 ${index + 1} 队`,
      progress: clampTeamPercent(item.progress ?? item.rate ?? item.completed_ratio ?? 0),
      completed: Number(item.completed ?? item.completed_count ?? item.score ?? 0),
      total: Number(item.total ?? item.total_count ?? item.goal ?? 100),
      rank: Number(item.rank ?? item.position ?? index + 1),
      trend: item.trend || item.change || 'stable',
      members: normalizeTeamMembers(item.members),
    })),
    countdown: countdown ? normalizeCountdown(countdown) : buildFallbackCountdown(),
  };
}

function normalizeTeamMembers(members) {
  const list = Array.isArray(members) ? members : [];
  return list.map((member, index) => ({
    id: member.id || member.member_id || `member-${index + 1}`,
    name: member.name || member.nickname || `成员 ${index + 1}`,
    avatar: member.avatar || member.avatar_url || member.initials || member.name?.slice(0, 1) || '队',
    contribution: Number(member.contribution ?? member.mileage ?? member.score ?? 0),
  }));
}

function normalizeCountdown(countdown) {
  if (typeof countdown === 'string') {
    return { label: '截止时间', value: countdown, remaining: countdown };
  }
  return {
    label: countdown.label || '剩余时间',
    value: countdown.value || countdown.text || countdown.remaining || '--',
    remaining: countdown.remaining || countdown.value || countdown.text || '--',
  };
}

function buildFallbackCountdown() {
  return { label: '剩余时间', value: '03:12:48', remaining: '03:12:48' };
}

function clampTeamPercent(value) {
  const percent = Number(value);
  if (!Number.isFinite(percent)) return 0;
  return Math.max(0, Math.min(100, percent));
}

function renderTeamChallengeFromActiveRoot() {
  const root = document.querySelector('[data-team-challenge]');
  if (!root) return;
  renderTeamChallenge(bindTeamChallengeDom(root));
}

function renderTeamChallengeLoading(dom) {
  setTeamControlsDisabled(dom, true);
  dom.board.innerHTML = `
    <section class="team-challenge-skeleton" aria-hidden="true"></section>
    <section class="team-challenge-skeleton" aria-hidden="true"></section>
    <section class="team-challenge-skeleton" aria-hidden="true"></section>`;
  dom.roster.innerHTML = '<article class="team-challenge-skeleton team-challenge-skeleton--wide" aria-hidden="true"></article>';
  dom.countdown.innerHTML = '<article class="team-countdown-card"><span class="spinner" aria-hidden="true"></span><strong>加载中</strong><p>正在同步团队挑战赛数据</p></article>';
  dom.empty.hidden = true;
  updateTeamHeader(dom);
}

function renderTeamChallengeError(dom) {
  setTeamControlsDisabled(dom, false);
  dom.board.innerHTML = '';
  dom.roster.innerHTML = '';
  dom.countdown.innerHTML = '';
  dom.empty.hidden = false;
  dom.empty.innerHTML = `
    <h3>加载失败</h3>
    <p>${escapeTeamChallengeHtml(teamChallengeState.error || '网络错误，请重试')}</p>
    <button class="btn btn-primary" type="button" data-team-retry>重试</button>`;
  dom.empty.querySelector('[data-team-retry]')?.addEventListener('click', handleTeamRetryClick);
  updateTeamHeader(dom);
}

function renderTeamChallenge(dom) {
  setTeamControlsDisabled(dom, false);
  updateTeamHeader(dom);
  const teams = filterTeamChallengeTeams(teamChallengeState.data.teams);
  if (!teams.length) {
    dom.board.innerHTML = '';
    dom.roster.innerHTML = '';
    dom.empty.hidden = false;
    dom.empty.innerHTML = '<h3>暂无数据</h3><p>暂无数据</p>';
    return;
  }
  dom.empty.hidden = true;
  dom.board.innerHTML = teams.map((team) => renderTeamChallengeCard(team)).join('');
  dom.roster.innerHTML = teams[0] ? renderTeamMembers(teams[0]) : '';
  dom.countdown.innerHTML = renderTeamCountdown(teamChallengeState.data.countdown);
  dom.board.querySelectorAll('[data-team-select]').forEach((button) => {
    button.addEventListener('click', handleTeamSelectClick);
  });
}

function updateTeamHeader(dom) {
  if (dom.title) dom.title.textContent = teamChallengeState.data.title;
  if (dom.subtitle) dom.subtitle.textContent = teamChallengeState.data.subtitle;
  if (dom.meta) dom.meta.textContent = teamChallengeState.lastUpdated ? `更新于 ${teamChallengeState.lastUpdated}` : '实时同步中';
  if (dom.summary) {
    dom.summary.innerHTML = [
      `<span class="summary-chip">${teamChallengeState.data.teams.length} 支队伍</span>`,
      `<span class="summary-chip">${escapeTeamChallengeHtml(teamChallengeState.filters.scope === 'all' ? '全部赛道' : teamChallengeState.filters.scope)}</span>`,
      `<span class="summary-chip">${escapeTeamChallengeHtml(teamChallengeState.filters.keyword || '未筛选')}</span>`,
    ].join('');
  }
  dom.filters.forEach((button) => {
    button.classList.toggle('is-active', button.dataset.teamFilter === teamChallengeState.filters.scope);
  });
  if (dom.keywordInput && dom.keywordInput.value !== teamChallengeState.filters.keyword) {
    dom.keywordInput.value = teamChallengeState.filters.keyword;
  }
}

function filterTeamChallengeTeams(teams) {
  return teams.filter((team) => {
    const scopeMatch = teamChallengeState.filters.scope === 'all' || String(team.trend).toLowerCase() === teamChallengeState.filters.scope;
    const keyword = teamChallengeState.filters.keyword.toLowerCase();
    const keywordMatch = !keyword || [team.name, team.rank, team.completed, team.total, ...(team.members || []).map((member) => member.name)].join(' ').toLowerCase().includes(keyword);
    return scopeMatch && keywordMatch;
  });
}

function renderTeamChallengeCard(team) {
  const selectedClass = team.id === teamChallengeState.selectedTeamId ? ' is-selected' : '';
  return `
    <article class="team-card${selectedClass}" data-team-id="${escapeTeamChallengeHtml(team.id)}">
      <header class="team-card__head">
        <div>
          <span class="summary-chip">第 ${escapeTeamChallengeHtml(String(team.rank))} 名</span>
          <h3>${escapeTeamChallengeHtml(team.name)}</h3>
          <p>${escapeTeamChallengeHtml(team.trendLabel || team.trend || '稳定上升')}</p>
        </div>
        <button class="btn btn-secondary" type="button" data-team-select="${escapeTeamChallengeHtml(team.id)}">查看</button>
      </header>
      <div>
        <div class="team-progress__label"><strong>${escapeTeamChallengeHtml(String(team.completed))}</strong><span>/ ${escapeTeamChallengeHtml(String(team.total))}</span></div>
        <div class="team-progress" aria-hidden="true"><i style="width:${team.progress}%"></i></div>
      </div>
      <dl class="team-stats">
        <div><dt>完成度</dt><dd>${escapeTeamChallengeHtml(String(team.progress))}%</dd></div>
        <div><dt>成员</dt><dd>${escapeTeamChallengeHtml(String(team.members.length))} 人</dd></div>
        <div><dt>趋势</dt><dd>${escapeTeamChallengeHtml(team.trend)}</dd></div>
      </dl>
    </article>`;
}

function renderTeamMembers(team) {
  const members = team.members.length ? team.members : [{ id: 'empty', name: '暂无成员', avatar: '—', contribution: 0 }];
  return `
    <article class="team-roster-card">
      <header class="team-roster-card__head">
        <div>
          <span class="summary-chip">成员贡献</span>
          <h3>${escapeTeamChallengeHtml(team.name)}</h3>
        </div>
      </header>
      <ul class="team-member-list">
        ${members.map((member) => `
          <li class="team-member">
            <span class="team-member__avatar">${escapeTeamChallengeHtml(String(member.avatar).slice(0, 2))}</span>
            <div>
              <strong>${escapeTeamChallengeHtml(member.name)}</strong>
              <p>贡献 ${escapeTeamChallengeHtml(String(member.contribution))}</p>
            </div>
          </li>`).join('')}
      </ul>
    </article>`;
}

function renderTeamCountdown(countdown) {
  return `
    <article class="team-countdown-card">
      <span class="summary-chip">${escapeTeamChallengeHtml(countdown.label)}</span>
      <strong>${escapeTeamChallengeHtml(countdown.remaining)}</strong>
      <p>${escapeTeamChallengeHtml(countdown.value)}</p>
    </article>`;
}

function handleTeamSelectClick(event) {
  teamChallengeState.selectedTeamId = event.currentTarget.dataset.teamSelect || '';
  renderTeamChallengeFromActiveRoot();
}

function setTeamControlsDisabled(dom, disabled) {
  dom.refreshButton && (dom.refreshButton.disabled = disabled);
  dom.retryButton && (dom.retryButton.disabled = disabled);
  dom.keywordInput && (dom.keywordInput.disabled = disabled);
  dom.filters.forEach((button) => { button.disabled = disabled; });
}

function escapeTeamChallengeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function formatTeamChallengeTime(date) {
  return new Intl.DateTimeFormat('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    month: '2-digit',
    day: '2-digit',
  }).format(date);
}
