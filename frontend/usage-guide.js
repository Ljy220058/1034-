window.usageGuideModule = (() => {
  "use strict";

  const STORAGE_KEY = '1034.usage-guide.expanded.v1';
  const BOUND_FLAG = 'usageGuideBound';

  const content = [
    {
      title: '页面功能简介',
      body: '本页用于快速浏览 1034 跑团管理系统的成员档案、活动时间线、排行榜与快捷操作。顶部导航可直接跳转到对应模块，适合在桌面端和手机端查看。',
    },
    {
      title: '快捷操作提示',
      body: '常用动作包括刷新数据、查看成员详情、导出档案与重试加载。页面中的按钮都会保持暗色主题统一，并在数据不可用时自动显示空态或错误提示。',
    },
    {
      title: '移动端适配',
      body: '小屏设备下，卡片与按钮会自动改为纵向排列，避免横向滚动。建议在手机端优先使用顶部导航和单列内容区阅读。',
    },
  ];

  const state = {
    expanded: readInitialState(),
  };

  let refs = {};

  document.addEventListener('DOMContentLoaded', initUsageGuide);

  function initUsageGuide() {
    cacheRefs();
    if (!refs.host || refs.host.dataset[BOUND_FLAG] === 'true') return;
    refs.host.dataset[BOUND_FLAG] = 'true';
    renderContent();
    render();
    bindEvents();
  }

  function cacheRefs() {
    refs.host = document.querySelector('[data-usage-guide]');
    refs.toggle = document.querySelector('[data-usage-guide-toggle]');
    refs.body = document.querySelector('[data-usage-guide-body]');
    refs.status = document.querySelector('[data-usage-guide-status]');
    refs.content = document.querySelector('[data-usage-guide-content]');
  }

  function bindEvents() {
    refs.toggle?.addEventListener('click', toggleGuide);
    refs.host?.addEventListener('keydown', handleKeydown);
  }

  function readInitialState() {
    try {
      return localStorage.getItem(STORAGE_KEY) === 'expanded';
    } catch {
      return false;
    }
  }

  function persistState() {
    try {
      localStorage.setItem(STORAGE_KEY, state.expanded ? 'expanded' : 'collapsed');
    } catch {
      // Ignore storage failures in private browsing or restricted contexts.
    }
  }

  function toggleGuide() {
    state.expanded = !state.expanded;
    persistState();
    render();
  }

  function handleKeydown(event) {
    if (event.key === 'Enter' || event.key === ' ') {
      const target = event.target;
      if (target === refs.host || target === refs.toggle) {
        event.preventDefault();
        toggleGuide();
      }
    }
  }

  function renderContent() {
    if (!refs.content) return;
    refs.content.innerHTML = content.map((item) => `
      <article class="usage-guide__item">
        <h3>${item.title}</h3>
        <p>${item.body}</p>
      </article>
    `).join('');
  }

  function render() {
    if (!refs.host || !refs.toggle || !refs.body || !refs.status) return;
    refs.host.classList.toggle('is-expanded', state.expanded);
    refs.host.classList.toggle('is-collapsed', !state.expanded);
    refs.toggle.setAttribute('aria-expanded', String(state.expanded));
    refs.body.hidden = !state.expanded;
    refs.status.textContent = state.expanded ? '当前已展开，点击标题可收起。' : '默认收起，点击标题查看提示。';
    refs.host.setAttribute('aria-label', state.expanded ? '页面使用说明面板，已展开' : '页面使用说明面板，已收起');
  }

  return { initUsageGuide };
})();
