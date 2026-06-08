import { createApiClient, escapeHtml } from './api.js';

const ATTENDANCE_STATUS_TEXT = {
  signed_in: '已签到',
  absent: '缺勤',
  revoked: '已撤销',
  pending: '待签到',
};

function formatAttendanceStatus(value) {
  const key = String(value || '').toLowerCase();
  return ATTENDANCE_STATUS_TEXT[key] || String(value || '未知');
}

function formatDateTime(value) {
  if (!value) return '未记录';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return String(value);
  return parsed.toLocaleString('zh-CN', { hour12: false });
}

function getAttendanceItems(payload) {
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload?.items)) return payload.items;
  if (Array.isArray(payload?.records)) return payload.records;
  if (Array.isArray(payload?.data)) return payload.data;
  return [];
}

function isManagerRole(role) {
  return ['admin', 'leader'].includes(String(role || '').toLowerCase());
}

function getRoleLabel(role) {
  const roleMap = { member: '普通成员', leader: '领队', admin: '管理员' };
  return roleMap[String(role || '').toLowerCase()] || '普通成员';
}

function getAttendanceId(record) {
  return String(record.id || record.attendance_id || record.checkin_id || '');
}

function getMemberLabel(record) {
  return String(record.member_name || record.name || record.member_id || '未知成员');
}

function buildAttendancePayload(form, managerOnly = false) {
  const formData = new FormData(form);
  const payload = {
    member_id: Number(formData.get('member_id')),
    gps_checked: Boolean(formData.get('gps_checked')),
  };
  const checkedInAt = String(formData.get('checked_in_at') || '').trim();
  const reason = String(formData.get('reason') || '').trim();
  if (checkedInAt) payload.checked_in_at = checkedInAt;
  if (managerOnly && reason) payload.reason = reason;
  return payload;
}

function setButtonLoading(button, loading, label) {
  if (!button) return;
  button.disabled = Boolean(loading);
  if (loading) {
    button.dataset.originalText = button.textContent || '';
    button.textContent = label;
    return;
  }
  if (button.dataset.originalText) button.textContent = button.dataset.originalText;
}

function renderAttendanceState(target, kind, title, message, retryable = false) {
  if (!target) return;
  target.innerHTML = `
    <article class="attendance-state attendance-state--${escapeHtml(kind)}">
      <div class="task-state__inline">
        ${kind === 'loading' ? '<span class="spinner" aria-hidden="true"></span>' : ''}
        <h3>${escapeHtml(title)}</h3>
      </div>
      <p>${escapeHtml(message)}</p>
      ${retryable ? '<button class="btn btn-primary" type="button" data-attendance-retry>重试</button>' : ''}
    </article>
  `;
}

function renderAttendanceList(target, records, managerMode) {
  if (!target) return;
  if (!records.length) {
    target.innerHTML = '<article class="attendance-empty"><h3>暂无数据</h3><p>当前活动还没有出勤记录。</p></article>';
    return;
  }

  target.innerHTML = records.map((record) => {
    const status = String(record.status || '').toLowerCase();
    const tone = status === 'revoked' ? 'red' : status === 'signed_in' ? 'green' : 'muted';
    const attendanceId = getAttendanceId(record);
    const revokeReason = record.revoke_reason || record.revoked_reason || record.reason || '';
    return `
      <article class="attendance-card">
        <header>
          <div>
            <p class="task-meta">成员 ${escapeHtml(getMemberLabel(record))}</p>
            <h3>${escapeHtml(formatAttendanceStatus(status))}</h3>
          </div>
          <span class="attendance-badge attendance-badge--${tone}">${escapeHtml(formatAttendanceStatus(status))}</span>
        </header>
        <dl class="attendance-details">
          <div><dt>签到时间</dt><dd>${escapeHtml(formatDateTime(record.signed_in_at || record.checked_in_at))}</dd></div>
          <div><dt>GPS 校验</dt><dd>${record.gps_checked ? '已校验' : '未校验'}</dd></div>
          <div><dt>记录编号</dt><dd>${escapeHtml(attendanceId || '未返回')}</dd></div>
          <div><dt>来源</dt><dd>${escapeHtml(record.source || record.created_source || '普通签到')}</dd></div>
        </dl>
        ${revokeReason ? `<p class="attendance-audit">撤销/补签原因：${escapeHtml(revokeReason)}</p>` : ''}
        ${managerMode && attendanceId && status !== 'revoked' ? `
          <form class="attendance-inline-form" data-revoke-form data-attendance-id="${escapeHtml(attendanceId)}">
            <label for="revoke-${escapeHtml(attendanceId)}">撤销原因</label>
            <input id="revoke-${escapeHtml(attendanceId)}" name="reason" placeholder="请输入撤销原因" required />
            <button class="task-action" type="submit">撤销签到</button>
          </form>
        ` : ''}
      </article>
    `;
  }).join('');
}

function bootstrapAttendancePanel(options = {}) {
  const documentRef = options.document || (typeof document !== 'undefined' ? document : null);
  if (!documentRef) return null;

  const root = documentRef.querySelector('[data-attendance-panel]');
  if (!root) return null;

  const client = options.client || createApiClient(options);
  const activityInput = root.querySelector('[data-attendance-field="activity"]');
  const tokenInput = root.querySelector('[data-attendance-field="token"]');
  const roleSelect = root.querySelector('[data-attendance-field="role"]');
  const memberForm = root.querySelector('[data-checkin-form]');
  const backfillForm = root.querySelector('[data-backfill-form]');
  const managerArea = root.querySelector('[data-manager-attendance]');
  const listTarget = root.querySelector('[data-attendance-list]');
  const stateTarget = root.querySelector('[data-attendance-state]');
  const roleLabel = root.querySelector('[data-attendance-role-label]');
  const countTarget = root.querySelector('[data-attendance-count]');
  const refreshButtons = Array.from(root.querySelectorAll('[data-attendance-refresh]'));
  const state = { records: [], loading: false, error: '', role: roleSelect?.value || 'member' };

  function getAuthOptions() {
    const rawToken = String(tokenInput?.value || '').trim();
    const token = rawToken.replace(/^Bearer\s+/i, '');
    return token ? { token } : {};
  }

  function getActivityId() {
    return String(activityInput?.value || '').trim();
  }

  function syncRoleVisibility() {
    state.role = String(roleSelect?.value || 'member');
    const managerMode = isManagerRole(state.role);
    if (managerArea) managerArea.hidden = !managerMode;
    if (roleLabel) roleLabel.textContent = getRoleLabel(state.role);
    renderAttendanceList(listTarget, state.records, managerMode);
  }

  async function fetchAttendanceList() {
    const activityId = getActivityId();
    if (!activityId) {
      state.records = [];
      renderAttendanceList(listTarget, [], isManagerRole(state.role));
      renderAttendanceState(stateTarget, 'empty', '等待活动编号', '请输入活动 ID 后刷新出勤列表。');
      if (countTarget) countTarget.textContent = '0 条';
      return;
    }

    state.loading = true;
    state.error = '';
    refreshButtons.forEach((button) => { button.disabled = true; });
    renderAttendanceState(stateTarget, 'loading', '加载中', '正在读取活动出勤列表。');
    try {
      const payload = await client.listActivityCheckins(activityId, getAuthOptions());
      state.records = getAttendanceItems(payload);
      renderAttendanceList(listTarget, state.records, isManagerRole(state.role));
      renderAttendanceState(stateTarget, state.records.length ? 'loaded' : 'empty', state.records.length ? '出勤列表已同步' : '暂无数据', state.records.length ? '可继续签到、补签或撤销。' : '当前活动还没有出勤记录。');
      if (countTarget) countTarget.textContent = `${state.records.length} 条`;
    } catch (error) {
      state.error = error.message || '网络错误';
      renderAttendanceList(listTarget, [], isManagerRole(state.role));
      renderAttendanceState(stateTarget, 'error', '网络错误', `${state.error}，请检查活动 ID、登录令牌或后端服务。`, true);
      stateTarget?.querySelector('[data-attendance-retry]')?.addEventListener('click', fetchAttendanceList);
      if (countTarget) countTarget.textContent = '错误';
    } finally {
      state.loading = false;
      refreshButtons.forEach((button) => { button.disabled = false; });
    }
  }

  async function handleCheckinSubmit(event) {
    event.preventDefault();
    const activityId = getActivityId();
    const submitButton = memberForm?.querySelector('[type="submit"]');
    if (!activityId) {
      renderAttendanceState(stateTarget, 'error', '缺少活动编号', '请先填写活动 ID。');
      return;
    }
    setButtonLoading(submitButton, true, '签到中…');
    try {
      await client.createCheckin(activityId, buildAttendancePayload(memberForm), getAuthOptions());
      memberForm.reset();
      await fetchAttendanceList();
      renderAttendanceState(stateTarget, 'loaded', '签到成功', '普通签到已提交并刷新列表。');
    } catch (error) {
      renderAttendanceState(stateTarget, 'error', '签到失败', error.message || '网络错误', true);
      stateTarget?.querySelector('[data-attendance-retry]')?.addEventListener('click', () => handleCheckinSubmit(event));
    } finally {
      setButtonLoading(submitButton, false);
    }
  }

  async function handleBackfillSubmit(event) {
    event.preventDefault();
    if (!isManagerRole(state.role)) return;
    const activityId = getActivityId();
    const submitButton = backfillForm?.querySelector('[type="submit"]');
    if (!activityId) {
      renderAttendanceState(stateTarget, 'error', '缺少活动编号', '请先填写活动 ID。');
      return;
    }
    setButtonLoading(submitButton, true, '补签中…');
    try {
      await client.backfillCheckin(activityId, buildAttendancePayload(backfillForm, true), getAuthOptions());
      backfillForm.reset();
      await fetchAttendanceList();
      renderAttendanceState(stateTarget, 'loaded', '补签成功', '管理员补签已提交并刷新列表。');
    } catch (error) {
      renderAttendanceState(stateTarget, 'error', '补签失败', error.message || '网络错误', true);
      stateTarget?.querySelector('[data-attendance-retry]')?.addEventListener('click', () => handleBackfillSubmit(event));
    } finally {
      setButtonLoading(submitButton, false);
    }
  }

  async function handleRevokeSubmit(event) {
    const form = event.target.closest('[data-revoke-form]');
    if (!form) return;
    event.preventDefault();
    if (!isManagerRole(state.role)) return;
    const activityId = getActivityId();
    const attendanceId = form.dataset.attendanceId;
    const reason = String(new FormData(form).get('reason') || '').trim();
    const submitButton = form.querySelector('[type="submit"]');
    if (!activityId || !attendanceId || !reason) {
      renderAttendanceState(stateTarget, 'error', '撤销信息不完整', '请填写活动 ID、记录编号与撤销原因。');
      return;
    }
    setButtonLoading(submitButton, true, '撤销中…');
    try {
      await client.revokeCheckin(activityId, attendanceId, { reason }, getAuthOptions());
      await fetchAttendanceList();
      renderAttendanceState(stateTarget, 'loaded', '撤销成功', '撤销请求已提交并刷新列表。');
    } catch (error) {
      renderAttendanceState(stateTarget, 'error', '撤销失败', error.message || '网络错误', true);
      stateTarget?.querySelector('[data-attendance-retry]')?.addEventListener('click', () => handleRevokeSubmit(event));
    } finally {
      setButtonLoading(submitButton, false);
    }
  }

  roleSelect?.addEventListener('change', syncRoleVisibility);
  refreshButtons.forEach((button) => button.addEventListener('click', fetchAttendanceList));
  memberForm?.addEventListener('submit', handleCheckinSubmit);
  backfillForm?.addEventListener('submit', handleBackfillSubmit);
  listTarget?.addEventListener('submit', handleRevokeSubmit);
  syncRoleVisibility();
  renderAttendanceState(stateTarget, 'empty', '等待活动编号', '请输入活动 ID 后刷新出勤列表。');

  return { fetchAttendanceList, syncRoleVisibility, state };
}

export { bootstrapAttendancePanel, formatAttendanceStatus, getAttendanceItems };
