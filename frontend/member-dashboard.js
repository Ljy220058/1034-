const MEMBER_DASHBOARD_MONTH_COUNT = 6;
const MEMBER_DASHBOARD_EMPTY_TEXT = '暂无数据';

function createMemberDashboard(root = document) {
  const section = root.querySelector('[data-member-dashboard]');
  if (!section) return null;

  const elements = {
    section,
    refreshButtons: root.querySelectorAll('[data-member-dashboard-refresh]'),
    summary: section.querySelector('[data-member-dashboard-summary]'),
    state: section.querySelector('[data-member-dashboard-state]'),
    metrics: section.querySelector('[data-member-dashboard-metrics]'),
    chart: section.querySelector('[data-member-dashboard-chart]'),
    badges: section.querySelector('[data-member-dashboard-badges]'),
  };

  const state = {
    isLoading: false,
    hasLoaded: false,
    error: '',
    data: null,
  };

  async function refreshMemberDashboard() {
    if (!window.apiClient || typeof window.apiClient.fetchMemberAchievements !== 'function' || typeof window.apiClient.fetchLeaderboard !== 'function') {
      renderMemberDashboardError('仪表盘依赖的接口方法未就绪。');
      return;
    }

    state.isLoading = true;
    state.error = '';
    renderMemberDashboardLoading();

    try {
      const [achievements, leaderboard] = await Promise.all([
        window.apiClient.fetchMemberAchievements(),
        window.apiClient.fetchLeaderboard({ range: 'monthly' }),
      ]);
      state.data = buildMemberDashboardView(achievements, leaderboard);
      state.hasLoaded = true;
      state.isLoading = false;
      renderMemberDashboardSuccess();
    } catch (error) {
      state.isLoading = false;
      state.error = error instanceof Error ? error.message : '数据加载失败';
      renderMemberDashboardError(state.error);
    }
  }

  function bindMemberDashboardEvents() {
    elements.refreshButtons.forEach((button) => {
      button.addEventListener('click', () => {
        if (state.isLoading) return;
        refreshMemberDashboard();
      });
    });
  }

  function renderMemberDashboardLoading() {
    toggleRefreshButtons(true);
    renderSummary([{ label: '成员仪表盘', value: '同步中' }]);
    if (elements.state) {
      elements.state.className = 'panel-state';
      elements.state.innerHTML = `
        <div class="state-inline">
          <span class="spinner" aria-hidden="true"></span>
          <div>
            <h3>正在同步跑步数据</h3>
            <p>正在拉取成就徽章与近 6 个月跑量，请稍候。</p>
          </div>
        </div>
      `;
    }
    if (elements.metrics) {
      elements.metrics.innerHTML = Array.from({ length: 4 }).map(() => `
        <article class="member-dashboard-stat is-skeleton" aria-hidden="true">
          <span></span>
          <strong></strong>
          <small></small>
        </article>
      `).join('');
    }
    if (elements.chart) {
      elements.chart.innerHTML = `
        <article class="member-dashboard-chart__empty panel-skeleton">
          <span class="spinner" aria-hidden="true"></span>
          <p>正在生成趋势图</p>
        </article>
      `;
    }
    if (elements.badges) {
      elements.badges.innerHTML = Array.from({ length: 4 }).map(() => `
        <article class="member-badge-card is-skeleton" aria-hidden="true">
          <span class="member-badge-card__icon"></span>
          <strong></strong>
          <p></p>
        </article>
      `).join('');
    }
  }

  function renderMemberDashboardSuccess() {
    toggleRefreshButtons(false);
    const data = state.data;
    renderSummary([
      { label: '已获徽章', value: `${data.earnedBadges.length} 枚` },
      { label: '待解锁', value: `${data.lockedBadges.length} 枚` },
      { label: '近 6 个月总跑量', value: data.totalLastSixMonthsLabel },
      { label: '连续打卡', value: data.streakLabel },
    ]);

    if (elements.state) {
      elements.state.className = 'panel-state is-success';
      elements.state.innerHTML = `
        <div>
          <h3>数据已更新</h3>
          <p>本月跑量 ${escapeHtml(data.monthlyDistanceLabel)}，平均配速 ${escapeHtml(data.averagePaceLabel)}。</p>
        </div>
        <button class="btn btn--secondary" type="button" data-member-dashboard-refresh>重新拉取</button>
      `;
      elements.state.querySelector('[data-member-dashboard-refresh]')?.addEventListener('click', refreshMemberDashboard);
    }

    if (elements.metrics) {
      elements.metrics.innerHTML = data.metrics.map((item) => `
        <article class="member-dashboard-stat">
          <span>${escapeHtml(item.label)}</span>
          <strong>${escapeHtml(item.value)}</strong>
          <small>${escapeHtml(item.hint)}</small>
        </article>
      `).join('');
    }

    if (elements.chart) {
      const trendItems = data.monthlyTrend.slice(-MEMBER_DASHBOARD_MONTH_COUNT);
      const maxValue = Math.max(...trendItems.map((item) => item.distance), 1);
      elements.chart.innerHTML = `
        <header class="member-dashboard-chart__header">
          <div>
            <h3>近 6 个月跑量趋势</h3>
            <p>按月份聚合的公里数，帮助成员观察训练连续性。</p>
          </div>
          <span class="summary-chip">最高 ${escapeHtml(formatDistance(maxValue))}</span>
        </header>
        <div class="member-dashboard-chart__bars" role="img" aria-label="近 6 个月跑量柱状图">
          ${trendItems.map((item) => {
            const height = `${Math.max((item.distance / maxValue) * 100, item.distance > 0 ? 16 : 8)}%`;
            return `
              <article class="member-dashboard-bar-card">
                <span class="member-dashboard-bar__value">${escapeHtml(formatDistance(item.distance))}</span>
                <div class="member-dashboard-bar__track">
                  <i class="member-dashboard-bar__fill" style="--bar-height:${height}"></i>
                </div>
                <strong>${escapeHtml(item.label)}</strong>
              </article>
            `;
          }).join('')}
        </div>
      `;
    }

    if (elements.badges) {
      const badgeCards = data.badges.length ? data.badges : [createEmptyBadgeView()];
      elements.badges.innerHTML = badgeCards.map((badge) => badge.isEmpty
        ? `
          <article class="member-badge-empty panel-empty">
            <h3>${MEMBER_DASHBOARD_EMPTY_TEXT}</h3>
            <p>当前成员还没有可展示的徽章记录，请稍后重试。</p>
          </article>
        `
        : `
          <article class="member-badge-card ${badge.earned ? 'is-earned' : 'is-locked'}">
            <header class="member-badge-card__head">
              <span class="member-badge-card__icon" aria-hidden="true">${escapeHtml(badge.icon)}</span>
              <span class="summary-chip">${escapeHtml(badge.statusText)}</span>
            </header>
            <strong>${escapeHtml(badge.name)}</strong>
            <p>${escapeHtml(badge.description)}</p>
            ${badge.earned
              ? `<span class="member-badge-card__meta">获得日期：${escapeHtml(badge.dateLabel)}</span>`
              : `<div class="member-badge-progress"><div class="member-badge-progress__track"><i style="--progress-width:${escapeHtml(badge.progressPercent)}"></i></div><span>还差 ${escapeHtml(badge.remainingText)}</span></div>`}
          </article>
        `).join('');
    }
  }

  function renderMemberDashboardError(message) {
    toggleRefreshButtons(false);
    renderSummary([{ label: '成员仪表盘', value: '错误' }]);
    if (elements.state) {
      elements.state.className = 'panel-state is-error';
      elements.state.innerHTML = `
        <div>
          <h3>数据加载失败</h3>
          <p>${escapeHtml(message || '请稍后重试。')}</p>
        </div>
        <button class="btn btn--secondary" type="button" data-member-dashboard-refresh>重试</button>
      `;
      elements.state.querySelector('[data-member-dashboard-refresh]')?.addEventListener('click', refreshMemberDashboard);
    }
    if (elements.metrics) {
      elements.metrics.innerHTML = `
        <article class="member-dashboard-stat member-dashboard-stat--empty">
          <span>总跑量</span>
          <strong>--</strong>
          <small>等待重试</small>
        </article>
        <article class="member-dashboard-stat member-dashboard-stat--empty">
          <span>本月跑量</span>
          <strong>--</strong>
          <small>等待重试</small>
        </article>
        <article class="member-dashboard-stat member-dashboard-stat--empty">
          <span>平均配速</span>
          <strong>--</strong>
          <small>等待重试</small>
        </article>
        <article class="member-dashboard-stat member-dashboard-stat--empty">
          <span>连续打卡</span>
          <strong>--</strong>
          <small>等待重试</small>
        </article>
      `;
    }
    if (elements.chart) {
      elements.chart.innerHTML = `
        <article class="panel-empty">
          <h3>暂无数据</h3>
          <p>趋势图加载失败，请点击重试按钮重新拉取。</p>
        </article>
      `;
    }
    if (elements.badges) {
      elements.badges.innerHTML = `
        <article class="panel-empty member-badge-empty">
          <h3>暂无数据</h3>
          <p>徽章墙暂时不可用，请恢复网络后重试。</p>
        </article>
      `;
    }
  }

  function renderSummary(items) {
    if (!elements.summary) return;
    elements.summary.innerHTML = items.map((item) => `
      <span class="summary-chip">${escapeHtml(item.label)} <strong>${escapeHtml(item.value)}</strong></span>
    `).join('');
  }

  function toggleRefreshButtons(disabled) {
    elements.refreshButtons.forEach((button) => {
      button.disabled = disabled;
      button.setAttribute('aria-busy', disabled ? 'true' : 'false');
    });
  }

  bindMemberDashboardEvents();
  renderMemberDashboardLoading();
  refreshMemberDashboard();

  return { refreshMemberDashboard };
}

function buildMemberDashboardView(achievementsPayload, leaderboardPayload) {
  const achievements = normalizeAchievementPayload(achievementsPayload);
  const leaderboard = normalizeLeaderboardPayload(leaderboardPayload);
  const monthlyTrend = buildMonthlyTrend(achievements);
  const totalDistance = monthlyTrend.reduce((sum, item) => sum + item.distance, 0);
  const monthlyDistance = monthlyTrend.at(-1)?.distance ?? 0;
  const averagePace = averageNumber(achievements.map((item) => item.paceMinutesPerKm).filter(Number.isFinite));
  const streak = leaderboard.currentUser?.streakDays ?? achievements.reduce((max, item) => Math.max(max, item.streakDays ?? 0), 0);

  return {
    metrics: [
      { label: '总里程', value: formatDistance(totalDistance), hint: '近 6 个月累计' },
      { label: '总活动', value: `${achievements.length} 次`, hint: '含跑步与训练课' },
      { label: '平均配速', value: formatPace(averagePace), hint: '近 6 个月平均' },
      { label: '连续打卡', value: `${streak} 天`, hint: '最长连续训练' },
    ],
    monthlyTrend,
    earnedBadges: achievements.filter((item) => item.earned).map((item) => ({
      icon: item.icon,
      statusText: item.statusText,
      name: item.name,
      description: item.description,
      dateLabel: item.dateLabel,
      earned: true,
    })),
    lockedBadges: achievements.filter((item) => !item.earned),
    badges: achievements.length ? achievements.map((item) => ({
      icon: item.icon,
      statusText: item.statusText,
      name: item.name,
      description: item.description,
      dateLabel: item.dateLabel,
      progressPercent: item.progressPercent,
      remainingText: item.remainingText,
      earned: item.earned,
    })) : [createEmptyBadgeView()],
    totalLastSixMonthsLabel: formatDistance(totalDistance),
    monthlyDistanceLabel: formatDistance(monthlyDistance),
    averagePaceLabel: formatPace(averagePace),
    streakLabel: `${streak} 天`,
  };
}

function normalizeAchievementPayload(payload) {
  const items = Array.isArray(payload?.items) ? payload.items : Array.isArray(payload) ? payload : [];
  return items.map((item, index) => ({
    name: item.name || item.title || `成就 ${index + 1}`,
    description: item.description || '暂无描述',
    icon: item.icon || '🏅',
    dateLabel: item.date || item.earnedAt || '待解锁',
    earned: item.earned !== false,
    statusText: item.earned === false ? '未获得' : '已获得',
    progressPercent: clampPercent(item.progressPercent ?? item.progress ?? 0),
    remainingText: item.remainingText || item.remaining || '0%',
    distance: toNumber(item.distanceKm ?? item.distance ?? item.totalDistance ?? 0),
    paceMinutesPerKm: toNumber(item.paceMinutesPerKm ?? item.pace ?? item.averagePace),
    streakDays: toNumber(item.streakDays ?? item.streak),
    month: item.month || item.monthLabel || inferMonthLabel(index),
  }));
}

function normalizeLeaderboardPayload(payload) {
  return {
    currentUser: payload?.currentUser || payload?.member || null,
  };
}

function buildMonthlyTrend(items) {
  const monthlyMap = new Map();
  items.forEach((item) => {
    const label = item.month || inferMonthLabel(monthlyMap.size);
    const existing = monthlyMap.get(label) || { label, distance: 0 };
    existing.distance += item.distance || 0;
    monthlyMap.set(label, existing);
  });

  const ordered = Array.from(monthlyMap.values());
  while (ordered.length < MEMBER_DASHBOARD_MONTH_COUNT) {
    ordered.unshift({ label: inferMonthLabel(ordered.length), distance: 0 });
  }
  return ordered.slice(-MEMBER_DASHBOARD_MONTH_COUNT);
}

function createEmptyBadgeView() {
  return {
    isEmpty: true,
  };
}

function formatDistance(value) {
  const number = Number.isFinite(value) ? value : 0;
  return `${number.toFixed(number >= 100 ? 0 : 1)} km`;
}

function formatPace(value) {
  const number = Number.isFinite(value) && value > 0 ? value : 0;
  if (!number) return '暂无';
  const minutes = Math.floor(number);
  const seconds = Math.round((number - minutes) * 60);
  return `${minutes}'${String(seconds).padStart(2, '0')}" / km`;
}

function averageNumber(values) {
  if (!values.length) return 0;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function toNumber(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number : 0;
}

function clampPercent(value) {
  const number = Math.min(100, Math.max(0, Number(value) || 0));
  return `${number}%`;
}

function inferMonthLabel(index) {
  const month = String((index % 12) + 1).padStart(2, '0');
  return `2025-${month}`;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

window.createMemberDashboard = createMemberDashboard;
document.addEventListener('DOMContentLoaded', () => {
  window.createMemberDashboard();
});
