function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

const API_BASE = '/api/v1';
const FEEDBACK_STORAGE_KEY = '1034.activity.feedback.timeline.v1';

const PARTICIPATION_STATUS_ORDER = [
  { key: 'registered', label: '已报名', emptyText: '尚未找到报名记录', description: '报名成功后会展示报名时间与当前席位状态。' },
  { key: 'waitlisted', label: '候补中', emptyText: '未进入候补', description: '当活动名额已满或返回候补字段时展示候补进度。' },
  { key: 'signed_in', label: '已签到', emptyText: '尚未签到', description: '签到成功后会展示签到时间和 GPS 校验状态。' },
  { key: 'pending_feedback', label: '待反馈', emptyText: '暂未开放反馈', description: '已签到但未提交反馈时，提示成员补充跑后反馈。' },
  { key: 'feedback_done', label: '已反馈', emptyText: '尚未反馈', description: '反馈提交或摘要接口返回反馈内容后标记为已反馈。' },
];

const demoTimelinePayload = {
  activity: {
    id: 1,
    title: '周末环湖慢跑',
    start_time: '2026-06-13T08:00:00+08:00',
    location: '人民公园东门',
    route: '环湖绿道 8km',
    distance_km: 8,
    pace_group: '5:30-6:00',
    description: '适合稳定配速训练，结束后收集跑后反馈。',
  },
  digest: {
    overview: { registered_count: 12, signed_in_count: 9, absent_count: 0 },
    feedback_summary: '暂无反馈',
    follow_up_suggestions: ['提醒未签到成员补签', '跑后收集配速感受'],
  },
  registrations: [
    { member_id: 1, status: 'registered', created_at: '2026-06-10T20:30:00+08:00' },
  ],
  checkins: [
    { member_id: 1, status: 'signed_in', signed_in_at: '2026-06-13T07:58:00+08:00', gps_checked: true },
  ],
  feedback: [],
};

const timelineState = {
  loading: false,
  error: '',
  payload: null,
  timeline: [],
  activityId: '1',
  memberId: '1',
  token: '',
};

const refs = {};

document.addEventListener('DOMContentLoaded', initParticipationTimeline);

function initParticipationTimeline() {
  refs.root = document.querySelector('[data-participation-timeline]');
  if (!refs.root) return;
  refs.activityId = refs.root.querySelector('[data-timeline-field="activity"]');
  refs.memberId = refs.root.querySelector('[data-timeline-field="member"]');
  refs.token = refs.root.querySelector('[data-timeline-field="token"]');
  refs.refreshButtons = Array.from(refs.root.querySelectorAll('[data-timeline-refresh]'));
  refs.demoButton = refs.root.querySelector('[data-timeline-demo]');
  refs.feedbackButton = refs.root.querySelector('[data-timeline-feedback]');
  refs.state = refs.root.querySelector('[data-timeline-state]');
  refs.list = refs.root.querySelector('[data-timeline-list]');
  refs.summary = refs.root.querySelector('[data-timeline-summary]');
  refs.activity = refs.root.querySelector('[data-timeline-activity]');
  refs.sources = refs.root.querySelector('[data-timeline-sources]');
  bindParticipationTimelineEvents();
  renderParticipationTimelineDemo();
}

function bindParticipationTimelineEvents() {
  refs.refreshButtons.forEach((button) => button.addEventListener('click', handleParticipationRefresh));
  refs.demoButton?.addEventListener('click', renderParticipationTimelineDemo);
  refs.feedbackButton?.addEventListener('click', handleLocalFeedbackSubmit);
  refs.activityId?.addEventListener('input', handleTimelineFieldChange);
  refs.memberId?.addEventListener('input', handleTimelineFieldChange);
  refs.token?.addEventListener('input', handleTimelineFieldChange);
}

function handleTimelineFieldChange() {
  timelineState.activityId = String(refs.activityId?.value || '').trim();
  timelineState.memberId = String(refs.memberId?.value || '').trim();
  timelineState.token = String(refs.token?.value || '').trim();
  renderTimelineSummary();
}

function createAuthHeaders() {
  const headers = { Accept: 'application/json' };
  const token = timelineState.token.replace(/^Bearer\s+/i, '');
  if (token) headers.Authorization = `Bearer ${token}`;
  return headers;
}

async function handleParticipationRefresh() {
  handleTimelineFieldChange();
  if (!timelineState.activityId) {
    timelineState.payload = null;
    timelineState.timeline = [];
    renderTimelineState('empty', '等待活动编号', '请输入活动 ID 后刷新参与状态时间线。');
    renderTimelineList([]);
    renderTimelineActivity(null);
    renderTimelineSummary();
    return;
  }
  await loadParticipationTimeline(timelineState.activityId);
}

async function loadParticipationTimeline(activityId) {
  timelineState.loading = true;
  timelineState.error = '';
  toggleTimelineButtons(true);
  renderTimelineState('loading', '加载中', '正在读取活动详情、报名状态、签到状态与反馈入口。');
  renderTimelineList([]);
  try {
    const payload = await fetchParticipationTimelineData(activityId);
    timelineState.payload = payload;
    timelineState.timeline = buildParticipationTimeline(payload, timelineState.memberId);
    renderTimelineActivity(payload.activity);
    renderTimelineList(timelineState.timeline);
    renderTimelineSources(payload);
    renderTimelineState(timelineState.timeline.length ? 'loaded' : 'empty', timelineState.timeline.length ? '时间线已同步' : '暂无数据', timelineState.timeline.length ? '已按报名、候补、签到、反馈顺序展示完整进度。' : '当前成员暂时没有参与记录。');
  } catch (error) {
    timelineState.error = error.message || '网络错误';
    timelineState.payload = null;
    timelineState.timeline = [];
    renderTimelineActivity(null);
    renderTimelineList([]);
    renderTimelineSources(null);
    renderTimelineState('error', '网络错误', `${timelineState.error}，请检查活动 ID、登录令牌或后端服务。`, true);
  } finally {
    timelineState.loading = false;
    toggleTimelineButtons(false);
    renderTimelineSummary();
  }
}

async function fetchParticipationTimelineData(activityId) {
  const [activityResult, digestResult, checkinResult] = await Promise.allSettled([
    fetchJson(`${API_BASE}/activities/${encodeURIComponent(activityId)}`),
    fetchJson(`${API_BASE}/activities/${encodeURIComponent(activityId)}/digest`),
    fetchJson(`${API_BASE}/activities/${encodeURIComponent(activityId)}/checkins`),
  ]);
  if (activityResult.status === 'rejected') throw activityResult.reason;
  const activity = unwrapApiData(activityResult.value);
  const digest = digestResult.status === 'fulfilled' ? unwrapApiData(digestResult.value) : null;
  const checkins = checkinResult.status === 'fulfilled' ? normalizeList(unwrapApiData(checkinResult.value)) : [];
  return {
    activity,
    digest,
    registrations: normalizeList(activity?.registrations || digest?.registrations || digest?.registration_records),
    checkins,
    feedback: readLocalFeedback(activityId),
  };
}

async function fetchJson(url) {
  const response = await fetch(url, { headers: createAuthHeaders() });
  if (!response.ok) {
    const error = new Error(response.status === 401 || response.status === 403 ? '未登录或权限不足' : `接口请求失败 ${response.status}`);
    error.status = response.status;
    throw error;
  }
  return response.json();
}

function unwrapApiData(payload) {
  return payload && Object.prototype.hasOwnProperty.call(payload, 'data') ? payload.data : payload;
}

function normalizeList(value) {
  if (Array.isArray(value)) return value;
  if (Array.isArray(value?.items)) return value.items;
  if (Array.isArray(value?.records)) return value.records;
  if (Array.isArray(value?.data)) return value.data;
  return [];
}

function renderParticipationTimelineDemo() {
  timelineState.activityId = '1';
  timelineState.memberId = '1';
  timelineState.payload = demoTimelinePayload;
  timelineState.timeline = buildParticipationTimeline(demoTimelinePayload, '1');
  if (refs.activityId) refs.activityId.value = timelineState.activityId;
  if (refs.memberId) refs.memberId.value = timelineState.memberId;
  renderTimelineActivity(demoTimelinePayload.activity);
  renderTimelineList(timelineState.timeline);
  renderTimelineSources(demoTimelinePayload);
  renderTimelineState('loaded', '示例已载入', '当前展示本地示例，点击刷新可读取后端真实数据。');
  renderTimelineSummary();
}

function buildParticipationTimeline(payload, memberId = '') {
  const normalizedMemberId = String(memberId || '').trim();
  const registrations = normalizeList(payload?.registrations);
  const checkins = normalizeList(payload?.checkins);
  const feedback = normalizeList(payload?.feedback);
  const registration = findMemberRecord(registrations, normalizedMemberId);
  const checkin = findMemberRecord(checkins, normalizedMemberId);
  const feedbackRecord = findMemberRecord(feedback, normalizedMemberId);
  const digest = payload?.digest || {};
  const isWaitlisted = Boolean(registration && ['waitlisted', 'waiting', '候补中'].includes(String(registration.status || '').toLowerCase()));
  const hasRegistration = Boolean(registration) || Number(digest?.overview?.registered_count || 0) > 0;
  const hasCheckin = Boolean(checkin) || Number(digest?.overview?.signed_in_count || 0) > 0;
  const hasFeedbackSummary = Boolean(digest?.feedback_summary && digest.feedback_summary !== '暂无反馈');
  const hasFeedback = Boolean(feedbackRecord) || hasFeedbackSummary;
  return PARTICIPATION_STATUS_ORDER.map((item) => {
    if (item.key === 'registered') {
      return createTimelineItem(item, hasRegistration && !isWaitlisted, registration?.created_at || registration?.registered_at || payload?.activity?.created_at, hasRegistration ? '报名记录已确认，可继续关注签到通知。' : item.description);
    }
    if (item.key === 'waitlisted') {
      return createTimelineItem(item, isWaitlisted, registration?.updated_at || registration?.created_at, isWaitlisted ? '当前处于候补中，请等待名额释放通知。' : item.description);
    }
    if (item.key === 'signed_in') {
      return createTimelineItem(item, hasCheckin, checkin?.signed_in_at || checkin?.checked_in_at, hasCheckin ? `签到已记录，GPS ${checkin?.gps_checked ? '已校验' : '未校验或未返回'}。` : item.description);
    }
    if (item.key === 'pending_feedback') {
      return createTimelineItem(item, hasCheckin && !hasFeedback, payload?.activity?.start_time, hasCheckin && !hasFeedback ? '你已签到，跑后反馈还未提交。' : item.description);
    }
    return createTimelineItem(item, hasFeedback, feedbackRecord?.created_at || feedbackRecord?.submitted_at, hasFeedback ? (feedbackRecord?.content || digest.feedback_summary || '反馈已提交。') : item.description);
  });
}

function createTimelineItem(template, active, time, detail) {
  return {
    ...template,
    active: Boolean(active),
    time: formatTimelineDate(time),
    detail: detail || template.description,
  };
}

function findMemberRecord(records, memberId) {
  if (!records.length) return null;
  if (!memberId) return records[0];
  return records.find((record) => String(record.member_id || record.memberId || record.member?.id || '') === memberId) || null;
}

function handleLocalFeedbackSubmit() {
  const activityId = String(timelineState.activityId || refs.activityId?.value || '').trim();
  const memberId = String(timelineState.memberId || refs.memberId?.value || '').trim();
  if (!activityId || !memberId) {
    renderTimelineState('error', '反馈信息不完整', '请先填写活动 ID 和成员 ID。', false);
    return;
  }
  const record = { activity_id: activityId, member_id: memberId, content: '已提交跑后反馈', created_at: new Date().toISOString() };
  const records = readAllLocalFeedback().filter((item) => !(String(item.activity_id) === activityId && String(item.member_id) === memberId));
  records.unshift(record);
  localStorage.setItem(FEEDBACK_STORAGE_KEY, JSON.stringify(records.slice(0, 20)));
  const payload = timelineState.payload || { ...demoTimelinePayload, activity: { ...demoTimelinePayload.activity, id: Number(activityId) || activityId } };
  timelineState.payload = { ...payload, feedback: readLocalFeedback(activityId) };
  timelineState.timeline = buildParticipationTimeline(timelineState.payload, memberId);
  renderTimelineList(timelineState.timeline);
  renderTimelineSources(timelineState.payload);
  renderTimelineState('loaded', '反馈已记录', '本地反馈入口已更新，时间线已切换为已反馈。');
  renderTimelineSummary();
}

function readAllLocalFeedback() {
  try {
    const records = JSON.parse(localStorage.getItem(FEEDBACK_STORAGE_KEY) || '[]');
    return Array.isArray(records) ? records : [];
  } catch {
    return [];
  }
}

function readLocalFeedback(activityId) {
  return readAllLocalFeedback().filter((item) => String(item.activity_id) === String(activityId));
}

function renderTimelineState(kind, title, message, retryable = false) {
  if (!refs.state) return;
  refs.state.className = `timeline-state is-${escapeHtml(kind)}`;
  refs.state.innerHTML = `
    <section class="state-inline">
      ${kind === 'loading' ? '<span class="spinner" aria-hidden="true"></span>' : ''}
      <h3>${escapeHtml(title)}</h3>
    </section>
    <p>${escapeHtml(message)}</p>
    ${retryable ? '<button class="btn btn-primary" type="button" data-timeline-refresh>重试加载</button>' : ''}
  `;
  refs.state.querySelector('[data-timeline-refresh]')?.addEventListener('click', handleParticipationRefresh);
}

function renderTimelineActivity(activity) {
  if (!refs.activity) return;
  if (!activity) {
    refs.activity.innerHTML = '<article class="timeline-empty"><h3>暂无数据</h3><p>刷新成功后会展示活动名称、路线和开始时间。</p></article>';
    return;
  }
  refs.activity.innerHTML = `
    <article class="timeline-activity-card">
      <p class="task-meta">活动详情 · ${escapeHtml(activity.location || '地点未返回')}</p>
      <h3>${escapeHtml(activity.title || '未命名活动')}</h3>
      <dl class="timeline-meta">
        <div><dt>开始时间</dt><dd>${escapeHtml(formatTimelineDate(activity.start_time))}</dd></div>
        <div><dt>路线</dt><dd>${escapeHtml(activity.route || '路线未返回')}</dd></div>
        <div><dt>距离</dt><dd>${escapeHtml(activity.distance_km ? `${activity.distance_km} km` : '未返回')}</dd></div>
        <div><dt>配速组</dt><dd>${escapeHtml(activity.pace_group || '未返回')}</dd></div>
      </dl>
      <p>${escapeHtml(activity.description || '暂无活动说明。')}</p>
    </article>
  `;
}

function renderTimelineList(items) {
  if (!refs.list) return;
  if (!items.length) {
    refs.list.innerHTML = '<article class="timeline-empty"><h3>暂无数据</h3><p>当前没有可展示的参与状态。</p></article>';
    return;
  }
  refs.list.innerHTML = items.map((item, index) => `
    <article class="timeline-step ${item.active ? 'is-active' : 'is-pending'}" data-step="${escapeHtml(item.key)}">
      <span class="timeline-step__index">${index + 1}</span>
      <section class="timeline-step__body">
        <header>
          <h3>${escapeHtml(item.label)}</h3>
          <span class="summary-chip">${escapeHtml(item.active ? '已完成' : item.emptyText)}</span>
        </header>
        <p>${escapeHtml(item.detail)}</p>
        <time>${escapeHtml(item.time || '时间未记录')}</time>
      </section>
    </article>
  `).join('');
}

function renderTimelineSources(payload) {
  if (!refs.sources) return;
  const sourceItems = [
    ['活动详情', `/api/v1/activities/${timelineState.activityId || '{activity_id}'}`],
    ['活动摘要', `/api/v1/activities/${timelineState.activityId || '{activity_id}'}/digest`],
    ['签到状态', `/api/v1/activities/${timelineState.activityId || '{activity_id}'}/checkins`],
    ['报名状态', '活动详情或摘要中的 registrations 字段'],
    ['反馈入口', '本地反馈记录 + digest.feedback_summary'],
  ];
  refs.sources.innerHTML = sourceItems.map(([label, value]) => `
    <article class="timeline-source-card">
      <span class="summary-chip">${escapeHtml(label)}</span>
      <p>${escapeHtml(value)}</p>
      <strong>${escapeHtml(getSourceState(label, payload))}</strong>
    </article>
  `).join('');
}

function getSourceState(label, payload) {
  if (!payload) return '等待同步';
  if (label === '活动详情') return payload.activity ? '已读取' : '暂无数据';
  if (label === '活动摘要') return payload.digest ? '已读取' : '未返回';
  if (label === '签到状态') return normalizeList(payload.checkins).length ? '已读取' : '暂无数据';
  if (label === '报名状态') return normalizeList(payload.registrations).length ? '已读取' : '未返回';
  return normalizeList(payload.feedback).length ? '已反馈' : '待反馈';
}

function renderTimelineSummary() {
  if (!refs.summary) return;
  const items = timelineState.timeline || [];
  const activeCount = items.filter((item) => item.active).length;
  refs.summary.innerHTML = [
    `活动 <strong>${escapeHtml(timelineState.activityId || '未填写')}</strong>`,
    `成员 <strong>${escapeHtml(timelineState.memberId || '未填写')}</strong>`,
    `进度 <strong>${activeCount}/${PARTICIPATION_STATUS_ORDER.length}</strong>`,
  ].map((item) => `<span class="summary-chip">${item}</span>`).join('');
}

function toggleTimelineButtons(disabled) {
  refs.refreshButtons?.forEach((button) => { button.disabled = disabled; });
  if (refs.demoButton) refs.demoButton.disabled = disabled;
  if (refs.feedbackButton) refs.feedbackButton.disabled = disabled;
}

function formatTimelineDate(value) {
  if (!value) return '时间未记录';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return String(value);
  return parsed.toLocaleString('zh-CN', { hour12: false });
}

export { PARTICIPATION_STATUS_ORDER, buildParticipationTimeline, normalizeList };
