(()=>{
  "use strict";

  const DEFAULT_WORKERS = [
    {
      id: 'frontend-dev',
      name: 'frontend-dev',
      role: '前端',
      status: '空闲',
      load: 18,
      capacity: 96,
      skills: ['页面搭建', '响应式', '微动效'],
      hint: '适合接收需要立即落地的 UI 与交互任务。',
    },
    {
      id: 'backend-dev',
      name: 'backend-dev',
      role: '后端',
      status: '忙碌',
      load: 64,
      capacity: 72,
      skills: ['接口', '字段校验', '数据聚合'],
      hint: '适合接收接口契约与数据一致性任务。',
    },
    {
      id: 'devops-engineer',
      name: 'devops-engineer',
      role: '运维',
      status: '离线',
      load: 82,
      capacity: 58,
      skills: ['部署', '探活', '日志巡检'],
      hint: '适合接收环境检查与发布保障任务。',
    },
    {
      id: 'reviewer',
      name: 'reviewer',
      role: '评审',
      status: '空闲',
      load: 22,
      capacity: 90,
      skills: ['验收', '回归', '代码阅读'],
      hint: '适合接收需要复核和验收的任务。',
    },
  ];

  const DEFAULT_TASKS = [
    {
      id: 't-worker-01',
      title: '补齐空闲 worker 探测面板',
      assignee: 'frontend-dev',
      status: 'running',
      priority: 'high',
      workspace_kind: 'dir',
      summary: '展示空闲 worker、加载状态与一键接单建议。',
      created_at: Date.now(),
      detail_url: '/tasks/t-worker-01',
    },
    {
      id: 't-worker-02',
      title: '检查任务板 API 返回结构',
      assignee: 'backend-dev',
      status: 'blocked',
      priority: 'medium',
      workspace_kind: 'dir',
      summary: '确认 task queue 数据字段稳定且可直接渲染。',
      created_at: Date.now() - 86400000,
      detail_url: '/tasks/t-worker-02',
    },
    {
      id: 't-worker-03',
      title: '校验本地静态预览',
      assignee: 'devops-engineer',
      status: 'done',
      priority: 'low',
      workspace_kind: 'scratch',
      summary: '确认 8080 端口的静态页面可以正常打开。',
      created_at: Date.now() - 172800000,
      detail_url: '/tasks/t-worker-03',
    },
  ];

  const state = {
    loading: true,
    error: '',
    workers: [],
    tasks: [],
    selectedWorker: '',
    selectedTask: '',
    scope: '全部',
  };

  document.addEventListener('DOMContentLoaded', initWorkerPanel);

  function initWorkerPanel() {
    const root = document.querySelector('[data-worker-panel]');
    if (!root) return;

    const refs = cacheRefs(root);
    if (!refs.list || !refs.summary || !refs.state) return;

    bindEvents(root, refs);
    loadPanel(root, refs);
  }

  function cacheRefs(root) {
    return {
      root,
      refreshButtons: Array.from(root.querySelectorAll('[data-worker-refresh]')),
      scopeButtons: Array.from(root.querySelectorAll('[data-worker-scope]')),
      searchInput: root.querySelector('[data-worker-search]'),
      workerSelect: root.querySelector('[data-worker-select="worker"]'),
      taskSelect: root.querySelector('[data-worker-select="task"]'),
      list: root.querySelector('[data-worker-list]'),
      summary: root.querySelector('[data-worker-summary]'),
      status: root.querySelector('[data-worker-status]'),
      state: root.querySelector('[data-worker-state]'),
      empty: root.querySelector('[data-worker-empty]'),
      error: root.querySelector('[data-worker-error]'),
      suggestion: root.querySelector('[data-worker-suggestion]'),
      retry: root.querySelector('[data-worker-retry]'),
      count: root.querySelector('[data-worker-count]'),
      idleCount: root.querySelector('[data-worker-idle-count]'),
      busyCount: root.querySelector('[data-worker-busy-count]'),
      taskCount: root.querySelector('[data-worker-task-count]'),
      idleList: root.querySelector('[data-worker-idle-list]'),
      taskList: root.querySelector('[data-worker-task-list]'),
    };
  }

  function bindEvents(root, refs) {
    refs.refreshButtons.forEach((button) => button.addEventListener('click', () => loadPanel(root, refs)));
    refs.scopeButtons.forEach((button) => button.addEventListener('click', () => {
      state.scope = button.dataset.workerScope || '全部';
      updateScopeButtons(refs);
      renderWorkers(refs);
    }));
    refs.searchInput?.addEventListener('input', () => renderWorkers(refs));
    refs.workerSelect?.addEventListener('change', () => {
      state.selectedWorker = refs.workerSelect.value;
      renderSuggestion(refs);
    });
    refs.taskSelect?.addEventListener('change', () => {
      state.selectedTask = refs.taskSelect.value;
      renderSuggestion(refs);
    });
    refs.retry?.addEventListener('click', () => loadPanel(root, refs));
  }

  async function loadPanel(root, refs) {
    setState(refs, 'loading', '加载中', '正在探测当前工作区的空闲 worker 与任务状态。', true);
    try {
      const data = await fetchBoardData();
      state.workers = normalizeWorkers(data.workers || data.idle_workers || data.members || []);
      state.tasks = normalizeTasks(data.tasks || data.data || []);
      state.error = '';
      renderOptions(refs);
      renderSummary(refs);
      renderWorkers(refs);
      renderSuggestion(refs);
      setState(refs, 'ready', '已就绪', '面板数据已同步，可开始筛选与接单建议。', false);
    } catch (error) {
      state.error = error && error.message ? error.message : '读取失败';
      state.workers = DEFAULT_WORKERS;
      state.tasks = DEFAULT_TASKS;
      renderOptions(refs);
      renderSummary(refs);
      renderWorkers(refs);
      renderSuggestion(refs);
      setState(refs, 'error', '网络错误', '无法读取后端数据，已切换到本地示例数据。', true);
    }
  }

  async function fetchBoardData() {
    const response = await fetch('/api/v1/workspaces/tasks/board', {
      headers: { Accept: 'application/json' },
    });
    if (!response.ok) throw new Error('请求任务看板失败');
    const payload = await response.json();
    if (!payload || !Object.prototype.hasOwnProperty.call(payload, 'data')) {
      throw new Error('API 返回格式不正确');
    }
    return payload.data;
  }

  function normalizeWorkers(list) {
    const source = Array.isArray(list) ? list : Object.entries(list || {}).map(([id, value]) => ({ id, ...value }));
    return (source.length ? source : DEFAULT_WORKERS).map((item, index) => {
      const id = String(item.id || item.worker_key || item.name || `worker-${index + 1}`);
      const load = clampNumber(item.load ?? item.busy_count ?? 40, 0, 100);
      const capacity = clampNumber(item.capacity ?? item.score ?? 80, 0, 100);
      const status = formatStatus(item.status || item.availability || (load < 30 ? '空闲' : load < 70 ? '忙碌' : '离线'));
      return {
        id,
        name: item.name || id,
        role: item.role || item.title || '未分类',
        status,
        load,
        capacity,
        skills: Array.isArray(item.skills || item.capabilities) ? (item.skills || item.capabilities) : [],
        hint: item.hint || item.suggestion || '建议优先分配可立即接单的任务。',
      };
    });
  }

  function normalizeTasks(list) {
    const source = Array.isArray(list) ? list : [];
    return (source.length ? source : DEFAULT_TASKS).map((item, index) => {
      const id = String(item.id || item.task_id || `task-${index + 1}`);
      return {
        id,
        title: item.title || item.name || `任务 ${index + 1}`,
        assignee: String(item.assignee || item.owner || '未分配'),
        status: formatTaskStatus(item.status),
        priority: formatPriority(item.priority || item.priority_level || 'medium'),
        workspace: String(item.workspace_kind || item.workspace || 'dir'),
        summary: item.summary || item.description || '暂无描述',
        detailUrl: item.detail_url || item.url || `/tasks/${encodeURIComponent(id)}`,
      };
    });
  }

  function renderOptions(refs) {
    if (refs.workerSelect) {
      refs.workerSelect.innerHTML = ['<option value="">请选择 worker</option>', ...state.workers.map((worker) => `<option value="${escapeHtml(worker.id)}">${escapeHtml(worker.name)}</option>`)].join('');
    }
    if (refs.taskSelect) {
      refs.taskSelect.innerHTML = ['<option value="">请选择任务</option>', ...state.tasks.map((task) => `<option value="${escapeHtml(task.id)}">${escapeHtml(task.title)}</option>`)].join('');
    }
  }

  function renderSummary(refs) {
    const filtered = filterWorkers();
    const idleCount = filtered.filter((worker) => worker.status === '空闲').length;
    const busyCount = filtered.filter((worker) => worker.status === '忙碌').length;
    if (refs.count) refs.count.textContent = String(filtered.length);
    if (refs.idleCount) refs.idleCount.textContent = String(idleCount);
    if (refs.busyCount) refs.busyCount.textContent = String(busyCount);
    if (refs.taskCount) refs.taskCount.textContent = String(state.tasks.length);
    if (refs.summary) {
      refs.summary.innerHTML = [
        chip(`当前 worker ${filtered.length}`),
        chip(`空闲 ${idleCount}`),
        chip(`忙碌 ${busyCount}`),
        chip(`任务 ${state.tasks.length}`),
      ].join('');
    }
  }

  function renderSkeleton(refs) {
    if (!refs.list) return;
    refs.list.innerHTML = `
      <div class="worker-panel__skeleton-list" aria-hidden="true">
        <div class="worker-panel__skeleton"></div>
        <div class="worker-panel__skeleton"></div>
      </div>
    `;
  }

  function renderWorkers(refs) {
    const filtered = filterWorkers();
    if (!refs.list) return;
    if (!filtered.length) {
      refs.list.innerHTML = `
        <article class="worker-panel__empty">
          <h3>暂无数据</h3>
          <p>当前筛选条件下没有可展示的 worker。</p>
        </article>
      `;
      return;
    }

    refs.list.innerHTML = filtered.map((worker) => {
      const selected = state.selectedWorker === worker.id;
      return `
        <article class="worker-panel__card${selected ? ' is-selected' : ''}">
          <header class="worker-panel__card-head">
            <div>
              <h3>${escapeHtml(worker.name)}</h3>
              <p>${escapeHtml(worker.role)}</p>
            </div>
            <span class="worker-panel__badge" data-state="${escapeHtml(worker.status)}">${escapeHtml(worker.status)}</span>
          </header>
          <p class="worker-panel__hint">${escapeHtml(worker.hint)}</p>
          <div class="worker-panel__bar" aria-hidden="true"><i style="width:${worker.load}%"></i></div>
          <dl class="worker-panel__meta">
            <div><dt>负载</dt><dd>${worker.load}%</dd></div>
            <div><dt>可用度</dt><dd>${worker.capacity}%</dd></div>
          </dl>
          <div class="worker-panel__skills">${worker.skills.length ? worker.skills.map((skill) => `<span class="worker-panel__tag">${escapeHtml(skill)}</span>`).join('') : '<span class="worker-panel__tag">暂无标签</span>'}</div>
          <div class="worker-panel__actions">
            <button class="btn btn-primary worker-panel__action" type="button" data-worker-select="${escapeHtml(worker.id)}">优先分配</button>
            <button class="btn btn-secondary worker-panel__action" type="button" data-worker-open="${escapeHtml(worker.id)}">查看建议</button>
          </div>
        </article>
      `;
    }).join('');

    refs.list.querySelectorAll('[data-worker-select]').forEach((button) => {
      button.addEventListener('click', () => {
        state.selectedWorker = button.dataset.workerSelect || '';
        if (refs.workerSelect) refs.workerSelect.value = state.selectedWorker;
        renderSuggestion(refs);
      });
    });
    refs.list.querySelectorAll('[data-worker-open]').forEach((button) => {
      button.addEventListener('click', () => {
        state.selectedWorker = button.dataset.workerOpen || '';
        if (refs.workerSelect) refs.workerSelect.value = state.selectedWorker;
        renderSuggestion(refs);
      });
    });
  }

  function renderSuggestion(refs) {
    if (!refs.suggestion) return;
    const worker = state.workers.find((item) => item.id === state.selectedWorker) || state.workers.find((item) => item.status === '空闲') || state.workers[0];
    const task = state.tasks.find((item) => item.id === state.selectedTask) || state.tasks[0];
    if (!worker || !task) {
      refs.suggestion.textContent = '暂无可用建议，请先加载数据。';
      return;
    }
    refs.suggestion.textContent = `建议将「${task.title}」分配给「${worker.name}」，因为当前负载 ${worker.load}% 且技能更匹配 ${worker.skills.slice(0, 2).join('、') || '基础接单'}。`;
  }

  function setState(refs, stateName, title, message, retryable) {
    if (refs.state) refs.state.dataset.state = stateName;
    if (refs.status) {
      refs.status.innerHTML = `
        <span class="worker-panel__status-chip" data-state="${escapeHtml(stateName === 'error' ? '离线' : stateName === 'loading' ? '忙碌' : '空闲')}">${escapeHtml(title)}</span>
        <span class="worker-panel__status-text">${escapeHtml(message)}</span>
      `;
    }
    if (refs.error) refs.error.hidden = stateName !== 'error';
    if (refs.empty) refs.empty.hidden = stateName !== 'empty';
    if (refs.retry) refs.retry.hidden = !retryable;
    if (refs.loadingState) refs.loadingState.hidden = stateName !== 'loading';
    if (refs.errorState) refs.errorState.hidden = stateName !== 'error';
    if (refs.readyState) refs.readyState.hidden = stateName !== 'ready';
    if (refs.state) {
      refs.state.innerHTML = `
        <div class="worker-panel__state worker-panel__state--${escapeHtml(stateName)}">
          <h3>${escapeHtml(title)}</h3>
          <p>${escapeHtml(message)}</p>
          ${retryable ? '<button class="btn btn-primary" type="button" data-worker-retry>重试</button>' : ''}
        </div>
      `;
    }
    refs.state.querySelector('[data-worker-retry]')?.addEventListener('click', () => loadPanel(refs.root, refs));
  }

  function updateScopeButtons(refs) {
    refs.scopeButtons.forEach((button) => {
      const active = (button.dataset.workerScope || '全部') === state.scope;
      button.classList.toggle('is-active', active);
      button.setAttribute('aria-pressed', active ? 'true' : 'false');
    });
  }

  function filterWorkers() {
    const query = String(document.querySelector('[data-worker-search]')?.value || '').trim().toLowerCase();
    return state.workers.filter((worker) => {
      const text = [worker.name, worker.role, worker.status, worker.hint, worker.skills.join(' ')].join(' ').toLowerCase();
      const matchesQuery = !query || text.includes(query);
      const matchesScope = state.scope === '全部' || worker.status === state.scope;
      return matchesQuery && matchesScope;
    });
  }

  function chip(text) {
    return `<span class="summary-chip">${escapeHtml(text)}</span>`;
  }

  function escapeHtml(value) {
    return String(value)
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#39;');
  }

  function formatStatus(value) {
    const raw = String(value || '').toLowerCase();
    if (raw.includes('idle') || raw === '空闲') return '空闲';
    if (raw.includes('offline') || raw === '离线') return '离线';
    return '忙碌';
  }

  function formatTaskStatus(value) {
    const raw = String(value || '').toLowerCase();
    if (['done', 'completed', '已完成'].includes(raw)) return '已完成';
    if (['blocked', '阻塞'].includes(raw)) return '阻塞';
    return '进行中';
  }

  function formatPriority(value) {
    const raw = String(value || '').toLowerCase();
    if (['high', 'urgent', '高'].includes(raw)) return '高';
    if (['low', '低'].includes(raw)) return '低';
    return '中';
  }

  function clampNumber(value, min, max) {
    const parsed = Number(value);
    if (Number.isNaN(parsed)) return min;
    return Math.min(max, Math.max(min, parsed));
  }
})();
