const conversationMock = {
  id: 'conv-1034-0421',
  title: '最近一次运营会复盘',
  target: '下周训练安排与报名转化',
  decisions: [
    '继续保留夜跑与节奏跑双线并行',
    '先补齐新成员引导文案，再开放批量报名',
    '活动页默认展示本周完成度与风险提醒'
  ],
  todo: ['确认补给点', '整理报名名单', '发布下一步提醒'],
  nextStep: '发一条中文提醒到群里，附上本周行动清单',
  sourceHint: '/api/v1/conversations/recent'
};

const conversationState = {
  loading: true,
  emptyMode: false,
  errorMode: false,
  message: '',
  selectedId: conversationMock.id,
  source: 'recent'
};

const conversationDom = {};

document.addEventListener('DOMContentLoaded', initConversationReplayCard);

function initConversationReplayCard() {
  bindConversationElements();
  bindConversationEvents();
  if (!conversationDom.root) return;
  renderConversationLoading();
  window.setTimeout(() => {
    conversationState.loading = false;
    renderConversationCard();
  }, 240);
}

function bindConversationElements() {
  conversationDom.root = document.querySelector('[data-conversation-replay]');
  conversationDom.summary = document.querySelector('[data-conversation-summary]');
  conversationDom.state = document.querySelector('[data-conversation-state]');
  conversationDom.panel = document.querySelector('[data-conversation-panel]');
  conversationDom.meta = document.querySelector('[data-conversation-meta]');
  conversationDom.source = document.querySelector('[data-conversation-replay-source]');
  conversationDom.refresh = document.querySelector('[data-conversation-refresh]');
  conversationDom.emptyToggle = document.querySelector('[data-conversation-empty-toggle]');
  conversationDom.errorToggle = document.querySelector('[data-conversation-error-toggle]');
}

function bindConversationEvents() {
  conversationDom.source?.addEventListener('change', handleConversationSourceChange);
  conversationDom.refresh?.addEventListener('click', handleConversationRetry);
  conversationDom.emptyToggle?.addEventListener('click', handleConversationEmpty);
  conversationDom.errorToggle?.addEventListener('click', handleConversationError);
}

function fetchConversationPreview() {
  return Promise.resolve(conversationMock);
}

function handleConversationNextStep() {
  conversationState.message = '已标记下一步：发送中文提醒并同步行动清单。';
  conversationState.selectedId = conversationMock.id;
  renderConversationCard();
}

function handleConversationEmpty() {
  conversationState.emptyMode = true;
  conversationState.errorMode = false;
  conversationState.message = '已切换到暂无会话演示。';
  renderConversationCard();
}

function handleConversationError() {
  conversationState.errorMode = true;
  conversationState.emptyMode = false;
  conversationState.message = '会话摘要暂时加载失败，显示重试入口。';
  renderConversationCard();
}

function handleConversationRetry() {
  conversationState.loading = true;
  conversationState.emptyMode = false;
  conversationState.errorMode = false;
  conversationState.message = '正在重新整理最近会话。';
  renderConversationLoading();
  window.setTimeout(() => {
    conversationState.loading = false;
    renderConversationCard();
  }, 260);
}

function handleConversationReset() {
  conversationState.emptyMode = false;
  conversationState.errorMode = false;
  conversationState.message = '已恢复最近会话复盘卡片。';
  renderConversationCard();
}

function handleConversationSourceChange(event) {
  conversationState.source = event.currentTarget?.value || 'recent';
  conversationState.message = conversationState.source === 'local' ? '已切换为本地示例数据。' : '已切换为最近会话。';
  renderConversationCard();
}

function renderConversationLoading() {
  renderConversationSummary(null);
  renderConversationMeta([]);
  if (conversationDom.state) {
    conversationDom.state.className = 'conversation-state';
    conversationDom.state.innerHTML = '<div class="activity-state__inline"><span class="spinner" aria-hidden="true"></span><h3>加载中</h3></div><p>正在读取最近会话摘要。</p>';
  }
  if (conversationDom.panel) {
    conversationDom.panel.innerHTML = '<article class="conversation-skeleton" aria-hidden="true"></article>';
  }
}

function renderConversationCard() {
  fetchConversationPreview().then((conversation) => {
    renderConversationSummary(conversation);
    renderConversationState(conversation);
    renderConversationPanel(conversation);
    renderConversationMeta(conversation);
  }).catch(() => {
    conversationState.errorMode = true;
    renderConversationSummary(null);
    renderConversationState(null);
    renderConversationPanel(null);
    renderConversationMeta([]);
  });
}

function renderConversationSummary(conversation) {
  if (!conversationDom.summary) return;
  if (!conversation || conversationState.loading) {
    conversationDom.summary.innerHTML = '<span class="summary-chip">加载中</span><span class="summary-chip">来源：/api/v1/conversations/recent</span>';
    return;
  }
  if (conversationState.emptyMode) {
    conversationDom.summary.innerHTML = '<span class="summary-chip">暂无数据</span><span class="summary-chip">可恢复示例</span>';
    return;
  }
  if (conversationState.errorMode) {
    conversationDom.summary.innerHTML = '<span class="summary-chip">加载失败</span><span class="summary-chip">可重试</span>';
    return;
  }
  const chips = [conversation.title, conversation.target, `${conversation.todo.length} 个待办`, '中文复盘卡片'];
  conversationDom.summary.innerHTML = chips.map((text) => `<span class="summary-chip">${escapeConversationHtml(text)}</span>`).join('');
}

function renderConversationMeta(conversation) {
  if (!conversationDom.meta) return;
  if (!conversation || conversationState.loading) {
    conversationDom.meta.innerHTML = '<span class="summary-chip">等待同步</span>';
    return;
  }
  if (conversationState.emptyMode) {
    conversationDom.meta.innerHTML = '<span class="summary-chip">暂无数据</span><span class="summary-chip">空态示例</span>';
    return;
  }
  if (conversationState.errorMode) {
    conversationDom.meta.innerHTML = '<span class="summary-chip">加载失败</span><span class="summary-chip">重试可用</span>';
    return;
  }
  const meta = [
    `会话 ID：${conversation.id}`,
    `目标：${conversation.target}`,
    `来源：${conversationState.source === 'local' ? '本地示例' : '最近会话'}`,
  ];
  conversationDom.meta.innerHTML = meta.map((item) => `<span class="summary-chip">${escapeConversationHtml(item)}</span>`).join('');
}

function renderConversationState(conversation) {
  if (!conversationDom.state) return;
  if (conversationState.emptyMode) {
    conversationDom.state.className = 'conversation-state';
    conversationDom.state.innerHTML = '<div><h3>暂无数据</h3><p>当前还没有可复盘的最近会话，先发起一次聊天或导入消息。</p></div><button class="btn btn-primary" type="button" data-conversation-reset>恢复预览</button>';
    conversationDom.state.querySelector('[data-conversation-reset]')?.addEventListener('click', handleConversationReset);
    return;
  }
  if (conversationState.errorMode) {
    conversationDom.state.className = 'conversation-state is-error';
    conversationDom.state.innerHTML = '<div><h3>加载失败</h3><p>最近会话摘要暂时无法读取，请稍后重试。</p></div><button class="btn btn-primary" type="button" data-conversation-retry>重试</button>';
    conversationDom.state.querySelector('[data-conversation-retry]')?.addEventListener('click', handleConversationRetry);
    return;
  }
  const message = conversationState.message || `本地示例就绪，后续可接入 ${conversation.sourceHint}。`;
  conversationDom.state.className = 'conversation-state';
  conversationDom.state.innerHTML = `<div><h3>${escapeConversationHtml('最近会话复盘卡片')}</h3><p>${escapeConversationHtml(message)}</p></div>`;
}

function renderConversationPanel(conversation) {
  if (!conversationDom.panel) return;
  if (conversationState.emptyMode) {
    conversationDom.panel.innerHTML = '<article class="conversation-empty"><h3>暂无数据</h3><p>本周还没有可复盘的会话内容，等有新讨论后再生成卡片。</p><button class="btn btn-secondary" type="button" data-conversation-reset>恢复预览</button></article>';
    conversationDom.panel.querySelector('[data-conversation-reset]')?.addEventListener('click', handleConversationReset);
    return;
  }
  if (conversationState.errorMode) {
    conversationDom.panel.innerHTML = '<article class="conversation-empty"><h3>加载失败</h3><p>会话卡片暂不可用，点击重试重新读取本地示例数据。</p><button class="btn btn-primary" type="button" data-conversation-retry>重试</button></article>';
    conversationDom.panel.querySelector('[data-conversation-retry]')?.addEventListener('click', handleConversationRetry);
    return;
  }
  conversationDom.panel.innerHTML = `<article class="conversation-card">
    <section class="conversation-card__top">
      <div>
        <span class="summary-chip">最近会话</span>
        <h3>${escapeConversationHtml(conversation.title)}</h3>
        <p>${escapeConversationHtml(conversation.target)}</p>
      </div>
      <span class="conversation-card__badge">${escapeConversationHtml(conversation.id)}</span>
    </section>
    <section class="conversation-card__decisions" aria-label="关键决策">
      <h4>关键决策</h4>
      <ul>${conversation.decisions.map((item) => `<li>${escapeConversationHtml(item)}</li>`).join('')}</ul>
    </section>
    <section class="conversation-card__todo" aria-label="待办事项">
      <h4>待办</h4>
      <ol>${conversation.todo.map((item) => `<li>${escapeConversationHtml(item)}</li>`).join('')}</ol>
    </section>
    <nav class="conversation-card__actions" aria-label="会话下一步操作">
      <button class="btn btn-primary" type="button" data-conversation-next-step>下一步</button>
      <button class="btn btn-secondary" type="button" data-conversation-empty>查看空态</button>
      <button class="btn btn-secondary" type="button" data-conversation-error>模拟加载失败</button>
    </nav>
    <p class="conversation-card__hint">${escapeConversationHtml(conversation.nextStep)}</p>
  </article>`;
  conversationDom.panel.querySelector('[data-conversation-next-step]')?.addEventListener('click', handleConversationNextStep);
  conversationDom.panel.querySelector('[data-conversation-empty]')?.addEventListener('click', handleConversationEmpty);
  conversationDom.panel.querySelector('[data-conversation-error]')?.addEventListener('click', handleConversationError);
}

function escapeConversationHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&apos;');
}
