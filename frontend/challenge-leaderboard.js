const challengeLeaderboardState = {
  mode: 'noChallenge',
  loading: true,
  error: '',
  retrying: false,
  hydrated: false,
};

const challengeLeaderboardModes = {
  noChallenge: {
    label: '暂无挑战赛',
    title: '暂无校园挑战赛',
    message: '当前没有正在进行的挑战赛。你可以先创建本月活动，或查看历史数据作为参考。',
    actionLabel: '创建挑战赛',
    actionHref: '/challenges/create?source=leaderboard-empty',
    status: '等待创建',
    stat: '0 场挑战赛',
    fallbackTitle: '降级展示：空状态引导',
    fallbackMessage: '用清晰的创建入口、历史说明和示例排名占位，避免页面空白。',
    tone: 'default',
    rows: [],
  },
  noScore: {
    label: '有挑战无成绩',
    title: '挑战赛已开启，暂无成绩',
    message: '同学们已报名，但还没有上传有效跑步记录。先展示报名情况、规则说明和首跑提醒。',
    actionLabel: '查看上传规则',
    actionHref: '/challenges/rules?source=no-score',
    status: '等待首个成绩',
    stat: '12 人已报名',
    fallbackTitle: '降级展示：低数据榜单',
    fallbackMessage: '保留报名人数、规则入口和示例名次占位，提示完成首跑后自动刷新。',
    tone: 'default',
    rows: [],
  },
  importFailed: {
    label: '数据导入失败',
    title: '成绩导入失败',
    message: '本次成绩文件未能同步成功。页面会保留上一次可用数据，并给出可重试的导入入口。',
    actionLabel: '重试导入',
    actionType: 'button',
    status: '接口异常',
    stat: '保留缓存榜单',
    fallbackTitle: '降级展示：缓存数据',
    fallbackMessage: '导入失败时不清空榜单，继续展示上次可用排名、更新时间和错误说明。',
    tone: 'danger',
    rows: [
      { name: '阿柠', meta: '上次同步 · 女子组', score: '42.6K' },
      { name: '跑团教练', meta: '上次同步 · 公开组', score: '38.2K' },
      { name: '芝士', meta: '上次同步 · 新生组', score: '31.8K' },
    ],
  },
  notRegistered: {
    label: '用户未报名',
    title: '你还未报名本次挑战赛',
    message: '你仍可浏览公开成绩，但个人目标、排名变化和完赛徽章会在报名后展示。',
    actionLabel: '立即报名',
    actionHref: '/challenges/register?source=leaderboard-guest',
    status: '访客浏览',
    stat: '开放公开榜单',
    fallbackTitle: '降级展示：公开 Top 3',
    fallbackMessage: '未报名时只展示公开排行榜、报名 CTA 和参赛权益，不暴露个人敏感成绩。',
    tone: 'default',
    rows: [
      { name: '星星', meta: '公开榜 · 5 月挑战', score: '58.4K' },
      { name: '阿柠', meta: '公开榜 · 5 月挑战', score: '42.6K' },
      { name: '芝士', meta: '公开榜 · 5 月挑战', score: '31.8K' },
    ],
  },
};

if (typeof document !== 'undefined') {
  document.addEventListener('DOMContentLoaded', initChallengeLeaderboard);
}

function initChallengeLeaderboard() {
  const root = document.querySelector('[data-challenge-leaderboard]');
  if (!root) return;
  const dom = bindChallengeLeaderboardDom(root);
  bindChallengeLeaderboardEvents(dom);
  renderChallengeLeaderboardLoading(dom);
  window.setTimeout(() => {
    challengeLeaderboardState.loading = false;
    challengeLeaderboardState.hydrated = true;
    renderChallengeLeaderboard(dom);
  }, 160);
}

function bindChallengeLeaderboardDom(root) {
  return {
    root,
    summary: root.querySelector('[data-challenge-summary]'),
    mode: root.querySelector('[data-challenge-mode]'),
    stage: root.querySelector('[data-challenge-stage]'),
    scenarioButtons: Array.from(root.querySelectorAll('[data-challenge-scenario]')),
    resetButton: root.querySelector('[data-challenge-reset]'),
    sourceSelect: root.querySelector('[data-challenge-source]'),
  };
}

function bindChallengeLeaderboardEvents(dom) {
  dom.scenarioButtons.forEach((button) => {
    button.addEventListener('click', handleChallengeScenarioClick);
  });
  dom.resetButton?.addEventListener('click', handleChallengeResetClick);
  dom.sourceSelect?.addEventListener('change', handleChallengeSourceChange);
}

function handleChallengeScenarioClick(event) {
  const scenario = event.currentTarget.dataset.challengeScenario || 'noChallenge';
  challengeLeaderboardState.mode = challengeLeaderboardModes[scenario] ? scenario : 'noChallenge';
  challengeLeaderboardState.error = '';
  renderChallengeLeaderboardFromActiveRoot();
}

function handleChallengeResetClick() {
  challengeLeaderboardState.mode = 'noChallenge';
  challengeLeaderboardState.error = '';
  renderChallengeLeaderboardFromActiveRoot();
}

function handleChallengeSourceChange(event) {
  const source = String(event.currentTarget.value || '').trim();
  if (source === 'offline') {
    challengeLeaderboardState.mode = 'importFailed';
  } else if (source === 'guest') {
    challengeLeaderboardState.mode = 'notRegistered';
  } else if (source === 'running') {
    challengeLeaderboardState.mode = 'noScore';
  } else {
    challengeLeaderboardState.mode = 'noChallenge';
  }
  challengeLeaderboardState.error = '';
  renderChallengeLeaderboardFromActiveRoot();
}

function renderChallengeLeaderboardFromActiveRoot() {
  const root = document.querySelector('[data-challenge-leaderboard]');
  if (!root) return;
  renderChallengeLeaderboard(bindChallengeLeaderboardDom(root));
}

function renderChallengeLeaderboardLoading(dom) {
  setChallengeControlsDisabled(dom, true);
  if (dom.summary) dom.summary.innerHTML = '<span class="summary-chip">加载中</span>';
  dom.stage.innerHTML = `
    <section class="challenge-stage__status">
      <div class="activity-state__inline"><span class="spinner" aria-hidden="true"></span><h3>加载中</h3></div>
      <p>正在整理挑战赛排行榜方案。</p>
    </section>
    <section class="challenge-layout" aria-label="排行榜预览与降级展示">
      <section class="challenge-rank-list" data-challenge-rank-list aria-label="排行榜预览">
        <article class="challenge-skeleton" aria-hidden="true"></article>
        <article class="challenge-skeleton" aria-hidden="true"></article>
        <article class="challenge-skeleton" aria-hidden="true"></article>
      </section>
      <aside class="challenge-side-panel" data-challenge-side-panel aria-label="低数据量降级展示">
        <article class="challenge-skeleton" aria-hidden="true"></article>
      </aside>
    </section>`;
}

function renderChallengeLeaderboard(dom) {
  const mode = challengeLeaderboardModes[challengeLeaderboardState.mode] || challengeLeaderboardModes.noChallenge;
  setChallengeControlsDisabled(dom, false);
  if (dom.mode) dom.mode.textContent = mode.label;
  renderChallengeSummary(dom, mode);
  renderChallengeStage(dom, mode);
}

function renderChallengeSummary(dom, mode) {
  if (!dom.summary) return;
  const chips = [mode.label, mode.status, mode.stat, mode.fallbackTitle];
  dom.summary.innerHTML = chips.map((text) => `<span class="summary-chip">${escapeChallengeLeaderboardHtml(text)}</span>`).join('');
}

function renderChallengeStage(dom, mode) {
  const errorClass = mode.tone === 'danger' ? ' is-error' : '';
  const loadingHint = challengeLeaderboardState.retrying ? '正在重试导入……' : '已准备好切换状态';
  dom.stage.innerHTML = `
    <section class="challenge-stage__status${errorClass}">
      <div class="activity-state__inline">
        ${challengeLeaderboardState.retrying ? '<span class="spinner" aria-hidden="true"></span>' : ''}
        <h3>${escapeChallengeLeaderboardHtml(mode.title)}</h3>
      </div>
      <p>${escapeChallengeLeaderboardHtml(mode.message)}${mode.actionType === 'button' ? ' ' + loadingHint : ''}</p>
    </section>
    <section class="challenge-layout" aria-label="排行榜预览与降级展示">
      <section class="challenge-rank-list" data-challenge-rank-list aria-label="排行榜预览">
        ${renderChallengeRankList(mode)}
      </section>
      <aside class="challenge-side-panel" data-challenge-side-panel aria-label="低数据量降级展示">
        ${renderChallengeFallback(mode)}
      </aside>
    </section>`;
  dom.stage.querySelector('[data-challenge-retry]')?.addEventListener('click', handleChallengeRetryClick);
}

function renderChallengeRankList(mode) {
  if (!mode.rows.length) {
    const toneClass = mode.tone === 'danger' ? ' is-danger' : '';
    return `
      <article class="challenge-empty-card${toneClass}">
        <span class="summary-chip">${escapeChallengeLeaderboardHtml(mode.label)}</span>
        <h3>${escapeChallengeLeaderboardHtml(mode.title)}</h3>
        <p>${escapeChallengeLeaderboardHtml(mode.message)}</p>
        <nav class="challenge-empty-card__actions" aria-label="主操作">
          ${renderChallengeAction(mode)}
        </nav>
        <section class="challenge-empty-card__fallbacks" aria-label="降级展示摘要">
          <span class="summary-chip">${escapeChallengeLeaderboardHtml(mode.status)}</span>
          <span class="summary-chip">${escapeChallengeLeaderboardHtml(mode.stat)}</span>
        </section>
      </article>`;
  }
  return mode.rows.map((item, index) => renderChallengeRankCard(item, index)).join('');
}

function renderChallengeRankCard(item, index) {
  return `
    <article class="challenge-rank-card">
      <span class="challenge-rank-card__rank" aria-label="第 ${index + 1} 名">${index + 1}</span>
      <section>
        <h3>${escapeChallengeLeaderboardHtml(item.name)}</h3>
        <p>${escapeChallengeLeaderboardHtml(item.meta)}</p>
      </section>
      <section class="challenge-rank-card__score" aria-label="成绩">
        <span>累计里程</span>
        <strong>${escapeChallengeLeaderboardHtml(item.score)}</strong>
      </section>
    </article>`;
}

function renderChallengeFallback(mode) {
  return `
    <article class="challenge-fallback-card">
      <span class="summary-chip">降级展示</span>
      <h3>${escapeChallengeLeaderboardHtml(mode.fallbackTitle)}</h3>
      <p>${escapeChallengeLeaderboardHtml(mode.fallbackMessage)}</p>
      <nav class="challenge-empty-card__actions" aria-label="降级操作">
        ${renderChallengeAction(mode)}
      </nav>
    </article>
    <article class="challenge-low-card">
      <span class="summary-chip">最小交互验证</span>
      <h3>切换四个状态并确认按钮可点击</h3>
      <p>筛选芯片更新 aria-pressed；重试按钮有 disabled/loading 过程；移动端场景不横向溢出。</p>
    </article>`;
}

function renderChallengeAction(mode) {
  if (mode.actionType === 'button') {
    return `<button class="btn btn-primary" type="button" data-challenge-retry>${escapeChallengeLeaderboardHtml(mode.actionLabel)}</button>`;
  }
  return `<a class="btn btn-primary" href="${escapeChallengeLeaderboardHtml(mode.actionHref)}">${escapeChallengeLeaderboardHtml(mode.actionLabel)}</a>`;
}

function handleChallengeRetryClick(event) {
  const button = event.currentTarget;
  challengeLeaderboardState.retrying = true;
  button.disabled = true;
  button.textContent = '正在重试';
  renderChallengeLeaderboardFromActiveRoot();
  window.setTimeout(() => {
    challengeLeaderboardState.retrying = false;
    challengeLeaderboardState.mode = 'importFailed';
    renderChallengeLeaderboardFromActiveRoot();
  }, 520);
}

function setChallengeControlsDisabled(dom, disabled) {
  dom.scenarioButtons.forEach((button) => {
    button.disabled = disabled;
  });
  if (dom.resetButton) dom.resetButton.disabled = disabled;
  if (dom.sourceSelect) dom.sourceSelect.disabled = disabled;
}

function escapeChallengeLeaderboardHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

if (typeof module !== 'undefined') {
  module.exports = {
    challengeLeaderboardModes,
    escapeChallengeLeaderboardHtml,
  };
}
