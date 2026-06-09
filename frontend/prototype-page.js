const helperText = '页面支持加载、空态、错误态与重试。';

/**
 * 生成任务卡片的 HTML 片段。
 * @description 返回包含概览、交互和状态三类卡片的静态模板字符串。
 * @returns {string} 任务卡片 HTML。
 */
function renderTaskCards() {
  return [
    {
      title: '项目简介',
      text: '展示 Hermes Swarm Lab 的核心目标与当前状态，帮助用户快速进入前端实现。',
      badge: '概览',
    },
    {
      title: '任务面板',
      text: '一屏查看候选任务、状态指示和筛选入口，适合桌面与手机浏览。',
      badge: '交互',
    },
    {
      title: '一键刷新',
      text: '保留明显的刷新按钮，并且在加载中显示骨架或 spinner。',
      badge: '状态',
    },
  ]
    .map(
      (item) => `
        <article class="task-card card">
          <span class="summary-chip">${item.badge}</span>
          <h3>${item.title}</h3>
          <p>${item.text}</p>
          <div class="task-card__actions">
            <button class="btn btn-primary" type="button">查看</button>
            <button class="btn btn-secondary" type="button">收藏</button>
          </div>
        </article>
      `,
    )
    .join('');
}

function renderPrototypePage() {
  return `
    <section class="prototype-hero card" id="概览">
      <article class="prototype-hero__copy">
        <span class="hero__eyebrow">Hermes Swarm Lab</span>
        <h2>中文创意任务一：设计极速原型页</h2>
        <p>一个可快速演示的单页原型，包含项目简介、任务面板、状态指示和一键刷新按钮。</p>
        <div class="prototype-hero__actions">
          <button class="btn btn-primary" type="button" data-prototype-refresh>一键刷新</button>
          <button class="btn btn-secondary" type="button" data-prototype-scroll>查看任务面板</button>
        </div>
      </article>
      <aside class="prototype-hero__panel">
        <div class="task-overview__grid">
          <article><span>主题</span><strong>深色 + 大留白</strong></article>
          <article><span>状态</span><strong data-prototype-status>待加载</strong></article>
          <article><span>动作</span><strong>刷新 / 筛选</strong></article>
          <article><span>宽度</span><strong>375 / 768 / 1280</strong></article>
        </div>
        <section class="task-board__state is-success" aria-live="polite">
          <div class="task-state__inline"><h3>示意状态</h3></div>
          <p>${helperText}</p>
        </section>
      </aside>
    </section>

    <section class="card section prototype-panel" id="任务面板">
      <header class="section-header">
        <div>
          <h2>任务面板</h2>
          <p>通过卡片展示三种关键体验：加载、空态和错误态。</p>
        </div>
        <span class="summary-chip">中文界面</span>
      </header>
      <div class="prototype-grid">${renderTaskCards()}</div>
      <section class="prototype-state prototype-state--loading creative-skeleton" id="状态指示" aria-live="polite">
        <div class="task-state__inline"><span class="spinner" aria-hidden="true"></span><h3>加载中</h3></div>
        <p>正在准备示例数据。</p>
      </section>
      <section class="prototype-empty creative-empty" aria-label="空态示例">
        <h3>暂无数据</h3>
        <p>当列表为空时，保留明确的文案和重试入口。</p>
        <button class="btn btn-primary" type="button">重试加载</button>
      </section>
      <section class="activity-state is-error prototype-error" aria-label="错误态示例">
        <div class="activity-state__inline"><h3>网络错误</h3></div>
        <p>断开后端时显示这段说明，并提供重试按钮。</p>
        <button class="btn btn-primary" type="button">重新加载</button>
      </section>
    </section>
  `;
}

document.body.insertAdjacentHTML('beforeend', renderPrototypePage());

document.querySelector('[data-prototype-scroll]')?.addEventListener('click', () => {
  document.querySelector('#任务面板')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
});

document.querySelector('[data-prototype-refresh]')?.addEventListener('click', () => {
  const status = document.querySelector('[data-prototype-status]');
  if (status) {
    status.textContent = '已刷新';
  }
});
