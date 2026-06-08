export function bootstrapInspirationCollection(options = {}) {
  const documentRef = options.document || (typeof document !== 'undefined' ? document : null);
  if (!documentRef) return null;

  const root = documentRef.querySelector('[data-inspiration-collection]');
  if (!root) return null;

  const STORAGE_KEY = '1034.inspiration-collection.v1';
  const PRIORITIES = ['high', 'medium', 'low'];
  const seedEntries = [
    {
      id: 'seed-1',
      title: '跑团新人欢迎卡片',
      summary: '进入页面时用一句友好的中文欢迎语介绍活动节奏和报名方式。',
      priority: 'high',
      tags: ['欢迎页', '跑团', '新手'],
      createdAt: Date.now() - 86400000 * 2,
      updatedAt: Date.now() - 86400000,
    },
    {
      id: 'seed-2',
      title: '周跑提醒弹层',
      summary: '在周三晚间弹出一次轻量提醒，提示用户补齐本周目标。',
      priority: 'medium',
      tags: ['提醒', '运营'],
      createdAt: Date.now() - 86400000 * 4,
      updatedAt: Date.now() - 86400000 * 2,
    },
  ];

  const refs = {
    form: root.querySelector('[data-inspiration-form]'),
    list: root.querySelector('[data-inspiration-list]'),
    summary: root.querySelector('[data-inspiration-summary]'),
    count: root.querySelector('[data-inspiration-count]'),
    title: root.querySelector('[data-inspiration-title]'),
    summaryInput: root.querySelector('[data-inspiration-summary-input]'),
    priority: root.querySelector('[data-inspiration-priority]'),
    tags: root.querySelector('[data-inspiration-tags]'),
    state: root.querySelector('[data-inspiration-state]'),
    helper: root.querySelector('[data-inspiration-helper]'),
    search: root.querySelector('[data-inspiration-search]'),
    filterButtons: Array.from(root.querySelectorAll('[data-inspiration-filter]')),
    save: root.querySelector('[data-inspiration-save]'),
    reset: root.querySelector('[data-inspiration-reset]'),
    reload: root.querySelector('[data-inspiration-reload]'),
    clearList: root.querySelector('[data-inspiration-clear-list]'),
    focus: root.querySelector('[data-inspiration-focus]'),
  };

  const state = {
    entries: [],
    filter: 'all',
    search: '',
    editingId: '',
    loading: true,
    error: '',
    submitting: false,
  };

  bindEvents();
  restoreEntries();
  renderAll();
  state.loading = false;
  renderState('已就绪');

  function bindEvents() {
    refs.form?.addEventListener('submit', handleSubmit);
    refs.form?.addEventListener('reset', handleReset);
    refs.save?.addEventListener('click', () => refs.form?.requestSubmit());
    refs.reset?.addEventListener('click', handleReset);
    refs.reload?.addEventListener('click', renderAll);
    refs.clearList?.addEventListener('click', handleClearList);
    refs.focus?.addEventListener('click', () => refs.title?.focus());
    refs.search?.addEventListener('input', handleSearch);
    refs.filterButtons.forEach((button) => button.addEventListener('click', handleFilterClick));
    [refs.title, refs.summaryInput, refs.priority, refs.tags].forEach((item) => item?.addEventListener('input', updateHelper));
    refs.priority?.addEventListener('change', updateHelper);
  }

  function restoreEntries() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) {
        state.entries = seedEntries.slice();
        persistEntries();
        return;
      }
      const parsed = JSON.parse(raw);
      state.entries = Array.isArray(parsed) ? parsed.map(normalizeEntry).filter(Boolean) : seedEntries.slice();
      if (!state.entries.length) {
        state.entries = seedEntries.slice();
        persistEntries();
      }
    } catch {
      state.entries = seedEntries.slice();
      state.error = '本地记录读取失败，已使用默认示例。';
    }
  }

  function persistEntries() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state.entries));
  }

  function normalizeEntry(item, index = 0) {
    if (!item) return null;
    return {
      id: String(item.id || `entry-${index + 1}`),
      title: String(item.title || '').trim(),
      summary: String(item.summary || '').trim(),
      priority: normalizePriority(item.priority),
      tags: normalizeTags(item.tags),
      createdAt: Number(item.createdAt || Date.now()),
      updatedAt: Number(item.updatedAt || Date.now()),
    };
  }

  function normalizePriority(value) {
    const raw = String(value || 'medium').toLowerCase();
    return PRIORITIES.includes(raw) ? raw : 'medium';
  }

  function normalizeTags(value) {
    if (Array.isArray(value)) return value.map((tag) => String(tag).trim()).filter(Boolean).slice(0, 6);
    return String(value || '')
      .split(/[，,\s]+/)
      .map((tag) => tag.trim())
      .filter(Boolean)
      .slice(0, 6);
  }

  function readForm() {
    return {
      title: String(refs.title?.value || '').trim(),
      summary: String(refs.summaryInput?.value || '').trim(),
      priority: normalizePriority(refs.priority?.value),
      tags: normalizeTags(refs.tags?.value),
    };
  }

  function validateEntry(entry) {
    const errors = [];
    if (!entry.title) errors.push('请输入创意标题');
    if (!entry.summary) errors.push('请输入摘要');
    if (!entry.tags.length) errors.push('请输入至少一个标签');
    return errors;
  }

  function handleSubmit(event) {
    event.preventDefault();
    const payload = readForm();
    const errors = validateEntry(payload);
    if (errors.length) {
      state.error = errors.join('；');
      renderState('校验未通过');
      return;
    }
    state.submitting = true;
    state.error = '';
    renderState('正在保存');
    const nextEntry = {
      id: state.editingId || `entry-${Date.now()}`,
      title: payload.title,
      summary: payload.summary,
      priority: payload.priority,
      tags: payload.tags,
      createdAt: state.entries.find((entry) => entry.id === state.editingId)?.createdAt || Date.now(),
      updatedAt: Date.now(),
    };
    state.entries = [nextEntry, ...state.entries.filter((entry) => entry.id !== state.editingId)];
    state.editingId = '';
    persistEntries();
    refs.form?.reset();
    state.submitting = false;
    renderAll();
    renderState('已保存灵感记录', true);
  }

  function handleReset() {
    state.editingId = '';
    state.error = '';
    state.submitting = false;
    updateHelper();
    renderState('表单已重置');
  }

  function handleClearList() {
    state.entries = [];
    persistEntries();
    renderAll();
    renderState('已清空本地记录');
  }

  function handleFilterClick(event) {
    state.filter = String(event.currentTarget?.dataset.inspirationFilter || 'all');
    refs.filterButtons.forEach((button) => {
      const active = String(button.dataset.inspirationFilter || 'all') === state.filter;
      button.classList.toggle('is-active', active);
      button.setAttribute('aria-pressed', active ? 'true' : 'false');
    });
    renderList();
  }

  function handleSearch(event) {
    state.search = String(event.currentTarget?.value || '').trim().toLowerCase();
    renderList();
  }

  function renderAll() {
    renderSummary();
    renderList();
    updateHelper();
  }

  function renderSummary() {
    const total = state.entries.length;
    const high = state.entries.filter((entry) => entry.priority === 'high').length;
    const tagCount = new Set(state.entries.flatMap((entry) => entry.tags)).size;
    if (refs.summary) {
      refs.summary.innerHTML = [
        `记录 ${total}`,
        `高优先级 ${high}`,
        `标签 ${tagCount}`,
      ].map((text) => `<span class="summary-chip">${escapeHtml(text)}</span>`).join('');
    }
    if (refs.count) refs.count.textContent = `${total} 条记录`;
  }

  function renderList() {
    if (!refs.list) return;
    const visible = state.entries.filter((entry) => {
      const matchesPriority = state.filter === 'all' || entry.priority === state.filter;
      const searchText = [entry.title, entry.summary, entry.tags.join(' ')].join(' ').toLowerCase();
      const matchesSearch = !state.search || searchText.includes(state.search);
      return matchesPriority && matchesSearch;
    });
    if (!visible.length) {
      refs.list.innerHTML = `
        <article class="inspiration-empty">
          <h3>暂无数据</h3>
          <p>${escapeHtml(state.search ? '试试换个关键词或清空筛选条件。' : '还没有保存任何灵感，先写下一条吧。')}</p>
          <button class="btn btn-primary" type="button" data-inspiration-empty-action>去填写</button>
        </article>
      `;
      refs.list.querySelector('[data-inspiration-empty-action]')?.addEventListener('click', () => refs.title?.focus());
      return;
    }
    refs.list.innerHTML = visible.map((entry) => renderCard(entry)).join('');
    refs.list.querySelectorAll('[data-inspiration-edit]').forEach((button) => {
      button.addEventListener('click', () => handleEdit(button.dataset.inspirationEdit || ''));
    });
    refs.list.querySelectorAll('[data-inspiration-copy]').forEach((button) => {
      button.addEventListener('click', () => handleCopy(button.dataset.inspirationCopy || ''));
    });
  }

  function renderCard(entry) {
    return `
      <article class="inspiration-card">
        <header class="inspiration-card__header">
          <div>
            <p class="inspiration-card__meta">${escapeHtml(formatDate(entry.updatedAt))}</p>
            <h3>${escapeHtml(entry.title)}</h3>
          </div>
          <span class="inspiration-badge inspiration-badge--${escapeHtml(entry.priority)}">${escapeHtml(formatPriority(entry.priority))}</span>
        </header>
        <p class="inspiration-card__summary">${escapeHtml(entry.summary)}</p>
        <div class="inspiration-tags">${entry.tags.map((tag) => `<span class="inspiration-tag">#${escapeHtml(tag)}</span>`).join('')}</div>
        <footer class="inspiration-card__actions">
          <button class="btn btn-secondary" type="button" data-inspiration-edit="${escapeHtml(entry.id)}">编辑</button>
          <button class="btn btn-secondary" type="button" data-inspiration-copy="${escapeHtml(entry.id)}">复制摘要</button>
        </footer>
      </article>
    `;
  }

  function handleEdit(id) {
    const entry = state.entries.find((item) => item.id === id);
    if (!entry) return;
    state.editingId = id;
    if (refs.title) refs.title.value = entry.title;
    if (refs.summaryInput) refs.summaryInput.value = entry.summary;
    if (refs.priority) refs.priority.value = entry.priority;
    if (refs.tags) refs.tags.value = entry.tags.join('，');
    updateHelper();
    refs.title?.focus();
    renderState('正在编辑这条灵感');
  }

  async function handleCopy(id) {
    const entry = state.entries.find((item) => item.id === id);
    if (!entry) return;
    try {
      await navigator.clipboard.writeText(`${entry.title}
${entry.summary}
#${entry.tags.join(' #')}`);
      renderState('摘要已复制到剪贴板', true);
    } catch {
      state.error = '复制失败，请手动选择文本。';
      renderState('复制失败');
    }
  }

  function renderState(message, success = false) {
    if (!refs.state) return;
    const isError = Boolean(state.error);
    refs.state.className = `inspiration-state ${isError ? 'is-error' : success ? 'is-success' : ''}`.trim();
    refs.state.innerHTML = `
      <div class="inspiration-state__inline">
        ${state.loading ? '<span class="spinner" aria-hidden="true"></span>' : ''}
        <h3>${escapeHtml(isError ? '加载失败' : success ? '已保存' : state.submitting ? '正在保存' : '已就绪')}</h3>
      </div>
      <p>${escapeHtml(message || state.error || '可直接编辑并保存灵感记录。')}</p>
      ${isError ? '<button class="btn btn-primary" type="button" data-inspiration-retry>重试</button>' : ''}
    `;
    refs.state.querySelector('[data-inspiration-retry]')?.addEventListener('click', () => {
      state.error = '';
      renderState('已重新恢复');
    });
    updateHelper();
  }

  function updateHelper() {
    if (!refs.helper) return;
    const payload = readForm();
    const tagText = payload.tags.length ? payload.tags.map((tag) => `#${tag}`).join(' ') : '#待补充';
    refs.helper.innerHTML = `
      <p>建议标题：<strong>${escapeHtml(payload.title || '先写一句短标题')}</strong></p>
      <p>摘要预览：<strong>${escapeHtml(payload.summary || '补一句能直接交代用途的描述')}</strong></p>
      <p>优先级：<strong>${escapeHtml(formatPriority(payload.priority))}</strong> · 标签：<strong>${escapeHtml(tagText)}</strong></p>
    `;
  }

  function formatPriority(value) {
    return { high: '高', medium: '中', low: '低' }[normalizePriority(value)] || '中';
  }

  function formatDate(timestamp) {
    const date = new Date(timestamp);
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
  }

  function escapeHtml(value) {
    return String(value)
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#39;');
  }
}
