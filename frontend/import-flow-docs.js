(()=>{
  "use strict";

  const root = document.querySelector('[data-import-flow-docs]');
  if (!root) return;

  const scenarios = {
    precheck: {
      badge: 'precheck',
      title: '预检阶段：先确认来源和字段',
      summary: '适合导入前扫描文件来源、字段映射、保存位置和撤销入口。',
      stateTitle: '预检就绪',
      stateText: '建议先检查来源可信度、字段完整性和授权是否仍然有效。',
      primary: '查看文案清单',
      secondary: '模拟错误',
      tip: '预检中建议把错误说清楚，让用户知道要改哪一项。',
      checklist: [
        '来源：本地文件、成员手动上传、第三方导出。',
        '读取字段：姓名、时间、距离、配速、标签、备注。',
        '保存位置：本地草稿 + 后端导入队列。',
        '撤销入口：导入前可撤销授权，导入后可查看记录。',
      ],
      branches: [
        { code: '400', title: '参数不合法', text: '请求字段或文件格式与当前映射不一致，请先检查字段对应关系。' },
        { code: '401', title: '授权失效', text: '登录态过期或未登录，请重新登录后再继续。' },
        { code: '403', title: '无权限', text: '当前账号没有导入权限，请联系管理员处理。' },
        { code: '422', title: '校验失败', text: '文件已读到，但内容校验未通过，请修正必填字段后重新提交。' },
      ],
      notes: [
        '重复上传同一批次时提示“活动已存在，请勿重复导入”。',
        '缺失字段时提示“缺少必填字段：xxx”。',
        '授权过期时给出登录入口，而不是继续尝试提交。',
      ],
    },
    wizard: {
      badge: 'wizard',
      title: '向导阶段：一步一步说明下一步',
      summary: '适合把导入过程拆成“选择文件 → 校验 → 提交 → 结果”四步。',
      stateTitle: '向导进行中',
      stateText: '每一步都应提供清晰的下一步按钮、返回按钮和错误回退。',
      primary: '查看流程图',
      secondary: '模拟错误',
      tip: '向导文案要短，按钮要明确，避免用户不知道下一步去哪。',
      checklist: [
        '步骤 1：选择文件并提示支持的格式。',
        '步骤 2：校验字段映射和必填项。',
        '步骤 3：确认提交目标与保存位置。',
        '步骤 4：显示成功结果与跳转入口。',
      ],
      branches: [
        { code: '重复活动', title: '重复导入', text: '检测到同名活动或同一批次重复提交，请阻止再次导入。' },
        { code: '缺失字段', title: '字段缺失', text: '缺少必填字段时，直接列出缺失项并保留当前填写内容。' },
        { code: '授权过期', title: '授权过期', text: '登录已失效时，向导应中断并引导用户重新登录。' },
        { code: '撤销后拒绝', title: '撤销后拒绝', text: '用户撤销授权后，所有提交动作都应立即拒绝并提示重新授权。' },
      ],
      notes: [
        '重复活动和缺失字段是最常见的前置拦截场景。',
        '当提交按钮不可用时，要说明原因而不是只置灰。',
        '每一步都保留“返回上一步”入口，减少用户丢失上下文。',
      ],
    },
    'anomaly-precheck': {
      badge: 'anomaly-precheck',
      title: '异常预检：专门处理边界场景',
      summary: '适合把异常场景单独归类，给出可执行的修复建议。',
      stateTitle: '异常已识别',
      stateText: '异常预检中应优先告诉用户“为什么失败”和“怎么修复”。',
      primary: '查看异常分支',
      secondary: '模拟错误',
      tip: '异常文案要能直接落地，避免只写“请求失败”。',
      checklist: [
        '400：请求参数或映射不正确。',
        '401：未登录或登录态失效。',
        '403：权限不足或角色被限制。',
        '422：字段值存在内容校验问题。',
      ],
      branches: [
        { code: '400', title: '请求格式错误', text: '请检查文件格式、编码和字段映射是否一致。' },
        { code: '401', title: '身份过期', text: '会话过期后，需要先登录再继续导入。' },
        { code: '403', title: '访问被拒绝', text: '账号没有导入权限，请联系管理员开通。' },
        { code: '422', title: '内容校验失败', text: '字段值不符合规则，请修正后再次提交。' },
      ],
      notes: [
        '异常分支优先显示修复建议，其次才是状态码。',
        '如果后端返回格式不一致，应该创建后端跟进任务，而不是在前端硬猜。',
        '撤销授权后再次提交应直接拒绝，不进入提交逻辑。',
      ],
    },
  };

  const dom = {
    summary: root.querySelector('[data-import-flow-summary]'),
    state: root.querySelector('[data-import-flow-state]'),
    checklist: root.querySelector('[data-import-flow-checklist]'),
    branches: root.querySelector('[data-import-flow-branches]'),
    notes: root.querySelector('[data-import-flow-notes]'),
    buttons: Array.from(root.querySelectorAll('[data-import-flow-toggle]')),
  };

  let current = 'precheck';
  let loading = true;
  let failed = false;

  document.addEventListener('DOMContentLoaded', initImportFlowDocs);

  function initImportFlowDocs() {
    bindEvents();
    renderImportFlowDocs();
    window.setTimeout(() => {
      loading = false;
      renderImportFlowDocs();
    }, 260);
  }

  function bindEvents() {
    dom.buttons.forEach((button) => {
      button.addEventListener('click', () => handleToggle(button.dataset.importFlowToggle || 'precheck'));
    });
  }

  function handleToggle(key) {
    if (!scenarios[key]) return;
    current = key;
    failed = false;
    renderImportFlowDocs();
  }

  function handleRetry() {
    failed = false;
    loading = true;
    renderImportFlowDocs();
    window.setTimeout(() => {
      loading = false;
      renderImportFlowDocs();
    }, 220);
  }

  function renderImportFlowDocs() {
    const scenario = scenarios[current];

    dom.buttons.forEach((button) => {
      const active = button.dataset.importFlowToggle === current;
      button.classList.toggle('is-active', active);
      button.setAttribute('aria-pressed', active ? 'true' : 'false');
      button.disabled = loading && !active;
    });

    if (loading) {
      dom.summary.innerHTML = '<span class="summary-chip">加载中</span><span class="summary-chip">暂无数据</span>';
      dom.state.innerHTML = '<div class="import-flow-docs__state-line"><span class="spinner" aria-hidden="true"></span><h3>正在加载中文状态文案</h3></div><p>请稍候，系统正在准备 precheck、wizard 与 anomaly-precheck 三组内容。</p>';
      dom.checklist.innerHTML = '<article class="import-flow-skeleton" aria-hidden="true"></article>';
      dom.branches.innerHTML = '<article class="import-flow-skeleton" aria-hidden="true"></article>';
      dom.notes.innerHTML = '<article class="import-flow-skeleton" aria-hidden="true"></article>';
      return;
    }

    dom.summary.innerHTML = [
      `<span class="summary-chip">${escapeHtml(scenario.badge)}</span>`,
      '<span class="summary-chip">暂无数据</span>',
      `<span class="summary-chip">${escapeHtml(scenario.tip)}</span>`,
    ].join('');

    dom.state.className = failed ? 'import-flow-docs__state is-error' : 'import-flow-docs__state';
    dom.state.innerHTML = `
      <div class="import-flow-docs__state-line">
        ${failed ? '' : '<span class="spinner" aria-hidden="true"></span>'}
        <h3>${escapeHtml(scenario.stateTitle)}</h3>
      </div>
      <p>${escapeHtml(scenario.stateText)}</p>
      <div class="import-flow-docs__actions">
        <button class="btn btn-primary" type="button" data-import-flow-retry>${failed ? '重试加载' : scenario.primary}</button>
        <button class="btn btn-secondary" type="button" data-import-flow-fail>${failed ? '恢复正常' : scenario.secondary}</button>
      </div>
    `;

    dom.state.querySelector('[data-import-flow-retry]')?.addEventListener('click', handleRetry);
    dom.state.querySelector('[data-import-flow-fail]')?.addEventListener('click', () => {
      failed = !failed;
      renderImportFlowDocs();
    });

    dom.checklist.innerHTML = `
      <article class="import-flow-card">
        <header class="import-flow-card__header">
          <span class="summary-chip">文案清单</span>
          <h3>${escapeHtml(scenario.title)}</h3>
        </header>
        <ul class="import-flow-list">
          ${scenario.checklist.map((item) => `<li>${escapeHtml(item)}</li>`).join('')}
        </ul>
      </article>
    `;

    dom.branches.innerHTML = `
      <article class="import-flow-card">
        <header class="import-flow-card__header">
          <span class="summary-chip">错误分支</span>
          <h3>400 / 401 / 403 / 422 与边界场景</h3>
        </header>
        <div class="import-flow-branch-grid">
          ${scenario.branches.map((branch) => `
            <article class="import-flow-branch">
              <span class="summary-chip">${escapeHtml(branch.code)}</span>
              <h4>${escapeHtml(branch.title)}</h4>
              <p>${escapeHtml(branch.text)}</p>
            </article>
          `).join('')}
        </div>
      </article>
    `;

    dom.notes.innerHTML = `
      <article class="import-flow-card">
        <header class="import-flow-card__header">
          <span class="summary-chip">落地提示</span>
          <h3>可直接写入页面的中文状态文案</h3>
        </header>
        <ol class="import-flow-notes">
          ${scenario.notes.map((item) => `<li>${escapeHtml(item)}</li>`).join('')}
        </ol>
      </article>
    `;
  }

  function escapeHtml(value) {
    return String(value)
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#39;');
  }
})();
