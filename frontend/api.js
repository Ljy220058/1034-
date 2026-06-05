/**
 * HTTP client helpers for the Running Club frontend.
 */
function buildUrl(baseUrl, path, query) {
  const trimmedBase = String(baseUrl || '').replace(/\/$/, '');
  const normalizedPath = String(path || '').startsWith('/') ? path : `/${path}`;
  const url = `${trimmedBase}${normalizedPath}`;
  const params = new URLSearchParams();
  Object.entries(query || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      params.set(key, value);
    }
  });
  const qs = params.toString();
  return qs ? `${url}?${qs}` : url;
}

/**
 * Create a small API client around the backend JSON contract.
 *
 * @param {object} [options]
 * @param {string} [options.baseUrl='/api/v1']
 * @param {(input: string, init?: RequestInit) => Promise<Response>} [options.fetchImpl]
 * @returns {{listAnnouncements:(query?: object)=>Promise<unknown>, createAnnouncement:(body: object)=>Promise<unknown>, listActivities:()=>Promise<unknown>, listTaskQueueTasks:(query?: object)=>Promise<unknown>, listKanbanTasks:(query?: object)=>Promise<unknown>, getConnectionStatus:()=>Promise<unknown>, retryConnection:()=>Promise<unknown>}}
 */
function createApiClient(options = {}) {
  const baseUrl = options.baseUrl || '/api/v1';
  const fetchImpl = options.fetchImpl || (typeof fetch === 'function' ? fetch.bind(globalThis) : null);
  if (!fetchImpl) {
    throw new Error('fetch implementation is required');
  }

  async function request(path, requestOptions = {}) {
    const response = await fetchImpl(buildUrl(baseUrl, path, requestOptions.query), {
      method: requestOptions.method || 'GET',
      headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
      body: requestOptions.body === undefined ? undefined : JSON.stringify(requestOptions.body),
    });
    const payload = await response.json();
    if (!response.ok) {
      const error = new Error(payload.detail || payload.message || `Request failed with status ${response.status}`);
      error.status = response.status;
      error.payload = payload;
      throw error;
    }
    if (!payload || !Object.prototype.hasOwnProperty.call(payload, 'data')) {
      throw new Error('Invalid API response: missing data field');
    }
    return payload.data;
  }

  return {
    listAnnouncements(query = {}) {
      return request('/announcements', { query });
    },
    createAnnouncement(body) {
      return request('/announcements', { method: 'POST', body });
    },
    listActivities() {
      return request('/activities');
    },
    listTaskQueueTasks(query = {}) {
      return request('/task-queue/tasks', { query });
    },
    listKanbanTasks(query = {}) {
      return request('/kanban/tasks', { query });
    },
    listKanbanTasks(query = {}) {
      return request('/kanban/tasks', { query });
    },
    getConnectionStatus() {
      return request('/status');
    },
    retryConnection() {
      return request('/status/retry', { method: 'POST' });
    },
  };
}

/**
 * Boot the announcements section and task creator form.
 *
 * @param {object} [options]
 * @param {Document} [options.document]
 * @param {{listAnnouncements:(query?: object)=>Promise<unknown>}} [options.client]
 * @returns {Promise<unknown>|null}
 */
async function bootstrap(options = {}) {
  const documentRef = options.document || (typeof document !== 'undefined' ? document : null);
  if (!documentRef) return null;
  const target = documentRef.querySelector('[data-announcements]');
  if (!target) return null;
  const client = options.client || createApiClient(options);
  try {
    const announcements = await client.listAnnouncements({ status: 'published' });
    renderAnnouncements(announcements, target);
    bootstrapTaskCreator({ document: documentRef });
    return announcements;
  } catch (error) {
    target.innerHTML = `<p class="error-state">${escapeHtml(error.message)}</p>`;
    throw error;
  }
}

function normalizeConnectionStatus(rawStatus) {
  if (!rawStatus || typeof rawStatus !== 'object') {
    return {
      status: 'unknown',
      label: '连接状态未知',
      tone: 'amber',
      message: '正在等待状态服务返回结果。',
      retryLabel: '重试连接',
      canRetry: true,
    };
  }

  const status = String(rawStatus.status || rawStatus.state || rawStatus.connection_status || 'unknown').toLowerCase();
  const map = {
    connected: { label: '已连接', tone: 'green', message: rawStatus.message || '状态服务在线，实时数据正常刷新。', retryLabel: '刷新连接', canRetry: true },
    reconnecting: { label: '重连中', tone: 'amber', message: rawStatus.message || '正在尝试恢复与服务的连接。', retryLabel: '再次重试', canRetry: true },
    disconnected: { label: '已断开', tone: 'red', message: rawStatus.message || '连接已断开，请手动重试。', retryLabel: '重新连接', canRetry: true },
    error: { label: '状态异常', tone: 'red', message: rawStatus.message || '状态接口返回异常。', retryLabel: '重试连接', canRetry: true },
    unknown: { label: '连接状态未知', tone: 'amber', message: rawStatus.message || '暂时无法确认连接状态。', retryLabel: '重试连接', canRetry: true },
  };
  const resolved = map[status] || map.unknown;
  return {
    status,
    label: resolved.label,
    tone: resolved.tone,
    message: resolved.message,
    retryLabel: resolved.retryLabel,
    canRetry: resolved.canRetry,
  };
}

function setConnectionStatusView(nodes, view) {
  if (!nodes || !nodes.badge) return;
  nodes.badge.className = `connection-badge ${view.tone}`;
  nodes.badge.textContent = view.label;
  if (nodes.message) nodes.message.textContent = view.message;
  if (nodes.retry) {
    nodes.retry.textContent = view.retryLabel;
    nodes.retry.disabled = !view.canRetry;
  }
}

async function bootstrapConnectionStatus(options = {}) {
  const documentRef = options.document || (typeof document !== 'undefined' ? document : null);
  if (!documentRef) return null;
  const badge = documentRef.querySelector('[data-connection-badge]');
  const message = documentRef.querySelector('[data-connection-message]');
  const retry = documentRef.querySelector('[data-connection-retry]');
  if (!badge || !message || !retry) return null;

  const client = options.client || createApiClient(options);
  const nodes = { badge, message, retry };
  let inFlight = null;

  const load = async () => {
    badge.dataset.state = 'loading';
    setConnectionStatusView(nodes, { status: 'loading', label: '连接检查中…', tone: 'amber', message: '正在读取实时连接状态。', retryLabel: '重试连接', canRetry: false });
    retry.disabled = true;
    try {
      const status = await client.getConnectionStatus();
      const view = normalizeConnectionStatus(status);
      badge.dataset.state = view.status;
      setConnectionStatusView(nodes, view);
      return view;
    } catch (error) {
      badge.dataset.state = 'error';
      setConnectionStatusView(nodes, {
        status: 'error',
        label: '加载失败',
        tone: 'red',
        message: error.message || '无法获取连接状态。',
        retryLabel: '再次重试',
        canRetry: true,
      });
      return null;
    }
  };

  retry.addEventListener('click', async () => {
    if (inFlight) return inFlight;
    retry.disabled = true;
    inFlight = (async () => {
      try {
        const status = await client.retryConnection();
        const view = normalizeConnectionStatus(status);
        badge.dataset.state = view.status;
        setConnectionStatusView(nodes, view);
        return view;
      } catch (error) {
        badge.dataset.state = 'error';
        setConnectionStatusView(nodes, {
          status: 'error',
          label: '重连失败',
          tone: 'red',
          message: error.message || '重连请求失败。',
          retryLabel: '再次重试',
          canRetry: true,
        });
        return null;
      } finally {
        inFlight = null;
      }
    })();
    return inFlight;
  });

  const initial = await load();
  return { load, initial };
}

/**
 * Render a task list board with filters and state handling.
 *
 * @param {object} [options]
 * @param {Document} [options.document]
 * @param {{listTaskQueueTasks:(query?: object)=>Promise<unknown>}} [options.client]
 * @returns {Promise<unknown>|null}
 */
async function bootstrapTaskList(options = {}) {
  const documentRef = options.document || (typeof document !== 'undefined' ? document : null);
  if (!documentRef) return null;
  const board = documentRef.querySelector('[data-task-board]');
  if (!board) return null;
  const client = options.client || createApiClient(options);
  const nodes = {
    summary: documentRef.querySelector('[data-task-summary]'),
    assignee: documentRef.querySelector('[data-task-filter="assignee"]'),
    status: documentRef.querySelector('[data-task-filter="status"]'),
    refresh: documentRef.querySelector('[data-task-refresh]'),
    list: documentRef.querySelector('[data-task-list]'),
    state: documentRef.querySelector('[data-task-state]'),
  };

  const normalizeTasks = (payload) => {
    if (Array.isArray(payload)) return payload;
    if (payload && Array.isArray(payload.items)) return payload.items;
    if (payload && Array.isArray(payload.tasks)) return payload.tasks;
    return [];
  };

  const toText = (value, fallback = '—') => {
    const text = value === undefined || value === null ? '' : String(value).trim();
    return text || fallback;
  };

  const getTaskText = (task, keys, fallback = '—') => {
    for (const key of keys) {
      const value = task?.[key];
      if (value !== undefined && value !== null && String(value).trim() !== '') {
        return String(value);
      }
    }
    return fallback;
  };

  const getTaskId = (task, index) => getTaskText(task, ['id', 'task_id', 'taskId', 'slug'], `task-${index + 1}`);

  const getTaskActionItems = (task) => {
    if (Array.isArray(task?.actions) && task.actions.length) return task.actions;
    return [
      { label: '查看', tone: 'primary' },
      { label: '推进', tone: 'neutral' },
    ];
  };

  const renderState = (kind, title, message) => {
    if (!nodes.state) return;
    nodes.state.innerHTML = `
      <div class="task-state ${kind}">
        <h3>${escapeHtml(title)}</h3>
        <p>${escapeHtml(message)}</p>
      </div>
    `;
  };

  const renderSummary = (tasks) => {
    if (!nodes.summary) return;
    const counts = tasks.reduce((acc, task) => {
      const status = String(getTaskText(task, ['status', 'state', 'task_status'], 'unknown')).toLowerCase();
      acc[status] = (acc[status] || 0) + 1;
      return acc;
    }, {});
    const total = tasks.length;
    const active = total - (counts.done || counts.completed || 0);
    nodes.summary.innerHTML = `
      <span class="summary-chip">总计 ${total}</span>
      <span class="summary-chip">进行中 ${counts.running || counts.in_progress || 0}</span>
      <span class="summary-chip">已完成 ${counts.done || counts.completed || 0}</span>
      <span class="summary-chip">活跃 ${active}</span>
    `;
  };

  const renderList = (tasks) => {
    if (!nodes.list) return;
    if (!tasks.length) {
      nodes.list.innerHTML = `
        <article class="task-empty-state" aria-label="暂无任务">
          <h3>当前没有符合条件的任务</h3>
          <p>可以切换筛选条件，或创建新的任务卡片来开始工作。</p>
        </article>
      `;
      return;
    }
    nodes.list.innerHTML = tasks.map((task, index) => {
      const id = getTaskId(task, index);
      const title = toText(getTaskText(task, ['title', 'name', 'summary'], '未命名任务'));
      const status = toText(getTaskText(task, ['status', 'state', 'task_status'], 'unknown'));
      const assignee = toText(getTaskText(task, ['assignee', 'owner', 'assigned_to'], '未分配'));
      const priority = toText(getTaskText(task, ['priority', 'level'], 'normal'));
      const workspace = toText(getTaskText(task, ['workspace_path', 'workspace', 'path'], '—'));
      const description = toText(getTaskText(task, ['body', 'description', 'summary_text'], '暂无描述'));
      const actions = getTaskActionItems(task).map((action) => `<button class="task-action ${escapeHtml(action.tone || 'neutral')}" type="button">${escapeHtml(action.label)}</button>`).join('');
      return `
        <article class="task-card" data-task-id="${escapeHtml(id)}">
          <div class="task-card-header">
            <div>
              <p class="task-meta">#${escapeHtml(id)} · ${escapeHtml(status)}</p>
              <h3>${escapeHtml(title)}</h3>
            </div>
            <span class="task-badge">${escapeHtml(priority)}</span>
          </div>
          <p class="task-description">${escapeHtml(description)}</p>
          <dl class="task-details">
            <div><dt>负责人</dt><dd>${escapeHtml(assignee)}</dd></div>
            <div><dt>工作区</dt><dd>${escapeHtml(workspace)}</dd></div>
          </dl>
          <div class="task-actions">${actions}</div>
        </article>
      `;
    }).join('');
  };

  const getFilterValue = (node) => node ? String(node.value || '').trim() : '';

  const loadTasks = async () => {
    board.dataset.state = 'loading';
    renderState('loading', '加载中', '正在获取工作区任务列表。');
    try {
      const tasks = normalizeTasks(await client.listTaskQueueTasks({
        assignee: getFilterValue(nodes.assignee),
        status: getFilterValue(nodes.status),
      }));
      const filtered = tasks.filter((task) => {
        const assignee = getTaskText(task, ['assignee', 'owner', 'assigned_to'], '').toLowerCase();
        const status = getTaskText(task, ['status', 'state', 'task_status'], '').toLowerCase();
        const assigneeFilter = getFilterValue(nodes.assignee).toLowerCase();
        const statusFilter = getFilterValue(nodes.status).toLowerCase();
        const assigneeMatch = !assigneeFilter || assignee === assigneeFilter;
        const statusMatch = !statusFilter || status === statusFilter;
        return assigneeMatch && statusMatch;
      });
      board.dataset.state = 'ready';
      renderSummary(filtered);
      renderList(filtered);
      if (!filtered.length) {
        renderState('empty', '没有匹配的任务', '当前筛选条件下没有任务。');
      } else {
        renderState('ready', '任务已加载', `已加载 ${filtered.length} 个任务。`);
      }
      return filtered;
    } catch (error) {
      board.dataset.state = 'error';
      renderState('error', '加载失败', error.message || '无法获取任务列表。');
      if (nodes.list) {
        nodes.list.innerHTML = '';
      }
      if (nodes.summary) {
        nodes.summary.innerHTML = '';
      }
      return [];
    }
  };

  const rerender = () => loadTasks();
  nodes.assignee?.addEventListener('change', rerender);
  nodes.status?.addEventListener('change', rerender);
  nodes.refresh?.addEventListener('click', rerender);

  return loadTasks();
}

/**
 * Export the browser entry points for convenience.
 */
export {
  buildUrl,
  bootstrap,
  bootstrapConnectionStatus,
  bootstrapTaskCreator,
  bootstrapTaskList,
  createApiClient,
  normalizeConnectionStatus,
  setConnectionStatusView,
};
