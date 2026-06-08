(()=>{
  'use strict';

  const STORAGE_KEY = '1034.sketch-generator.v1';
  const SAMPLE_PROMPT = '做一个暗色主题的活动报名页，需要主视觉、费用说明、表单、FAQ 和移动端适配。';
  const DEFAULT_STATE = {
    prompt: SAMPLE_PROMPT,
    generatedAt: '',
    variants: [],
    markdown: '',
  };

  const state = structuredClone(DEFAULT_STATE);
  const refs = {};

  document.addEventListener('DOMContentLoaded', initSketchGenerator);

  function initSketchGenerator() {
    const root = document.querySelector('[data-sketch-app]');
    if (!root) return;
    refs.root = root;
    refs.input = root.querySelector('[data-sketch-input]');
    refs.generate = root.querySelector('[data-sketch-generate]');
    refs.export = root.querySelector('[data-sketch-export]');
    refs.reset = root.querySelector('[data-sketch-reset]');
    refs.copy = root.querySelector('[data-sketch-copy]');
    refs.state = root.querySelector('[data-sketch-state]');
    refs.summary = root.querySelector('[data-sketch-summary]');
    refs.layout = root.querySelector('[data-sketch-layout]');
    refs.output = root.querySelector('[data-sketch-output]');
    refs.markdown = root.querySelector('[data-sketch-markdown]');

    bindSketchEvents();
    restoreSketchState();
    renderSketchGenerator({ initial: true });
  }

  function bindSketchEvents() {
    refs.generate?.addEventListener('click', handleGenerateSketch);
    refs.export?.addEventListener('click', handleExportMarkdown);
    refs.reset?.addEventListener('click', handleResetSketch);
    refs.copy?.addEventListener('click', handleCopyMarkdown);
    refs.input?.addEventListener('input', handleInputChange);
  }

  function restoreSketchState() {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null');
      if (!saved) {
        refs.input.value = SAMPLE_PROMPT;
        return;
      }
      state.prompt = saved.prompt || SAMPLE_PROMPT;
      state.generatedAt = saved.generatedAt || '';
      state.variants = Array.isArray(saved.variants) ? saved.variants : [];
      state.markdown = saved.markdown || '';
      refs.input.value = state.prompt;
    } catch {
      refs.input.value = SAMPLE_PROMPT;
    }
  }

  function saveSketchState() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  }

  function handleInputChange() {
    state.prompt = String(refs.input?.value || '').trim() || SAMPLE_PROMPT;
    saveSketchState();
    renderSketchGenerator({ initial: false });
  }

  function handleGenerateSketch() {
    state.prompt = String(refs.input?.value || '').trim() || SAMPLE_PROMPT;
    state.generatedAt = formatTime(new Date());
    state.variants = buildSketchVariants(state.prompt);
    state.markdown = buildMarkdown(state.prompt, state.variants, state.generatedAt);
    saveSketchState();
    renderSketchGenerator({ initial: false });
  }

  function handleExportMarkdown() {
    if (!state.markdown) handleGenerateSketch();
    const blob = new Blob([state.markdown], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `sketch-${Date.now()}.md`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1500);
    setStateMessage('已导出 Markdown 草图说明。', 'loaded');
  }

  async function handleCopyMarkdown() {
    const text = state.markdown || buildMarkdown(state.prompt, state.variants, state.generatedAt || formatTime(new Date()));
    try {
      await navigator.clipboard.writeText(text);
      setStateMessage('Markdown 说明已复制到剪贴板。', 'loaded');
    } catch {
      setStateMessage('复制失败，请手动选择下方文本。', 'error');
    }
  }

  function handleResetSketch() {
    state.prompt = SAMPLE_PROMPT;
    state.generatedAt = '';
    state.variants = [];
    state.markdown = '';
    refs.input.value = SAMPLE_PROMPT;
    localStorage.removeItem(STORAGE_KEY);
    renderSketchGenerator({ initial: true });
  }

  function renderSketchGenerator({ initial }) {
    if (!state.variants.length) {
      refs.summary.innerHTML = '<span class="summary-chip">暂无数据</span><span class="summary-chip">点击“生成草图”开始</span>';
      refs.layout.innerHTML = `
        <article class="sketch-generator__empty">
          <h3>暂无数据</h3>
          <p>输入中文需求后点击生成，系统会自动给出两种布局方案与 Markdown 说明。</p>
        </article>
      `;
      refs.output.textContent = '暂无内容';
      setStateMessage(initial ? '等待输入' : '尚未生成草图。', 'empty');
      return;
    }

    refs.summary.innerHTML = [
      `<span class="summary-chip"><strong>${escapeHtml(String(state.variants.length))}</strong> 种布局</span>`,
      `<span class="summary-chip">生成于 ${escapeHtml(state.generatedAt)}</span>`,
      `<span class="summary-chip">适合产品 / 开发快速评审</span>`,
    ].join('');

    refs.layout.innerHTML = state.variants.map(renderVariantCard).join('');
    refs.output.textContent = state.markdown;
    setStateMessage('已生成两种草图方案。', 'loaded');
  }

  function renderVariantCard(variant) {
    return `
      <article class="sketch-card" data-variant="${escapeHtml(variant.id)}">
        <header class="sketch-card__header">
          <div>
            <span class="template-badge">方案 ${escapeHtml(variant.label)}</span>
            <h3>${escapeHtml(variant.title)}</h3>
            <p>${escapeHtml(variant.subtitle)}</p>
          </div>
        </header>
        <section class="sketch-card__body">
          <div class="sketch-matrix">
            ${variant.layers.map((layer) => `
              <article class="sketch-layer">
                <span>${escapeHtml(layer.name)}</span>
                <p>${escapeHtml(layer.copy)}</p>
              </article>
            `).join('')}
          </div>
          <p class="sketch-card__notes">${escapeHtml(variant.note)}</p>
          <div class="sketch-card__actions">
            <button class="btn btn-secondary" type="button" data-sketch-focus="${escapeHtml(variant.id)}">强调此方案</button>
            <button class="btn btn-secondary" type="button" data-sketch-copy-variant="${escapeHtml(variant.id)}">复制方案摘要</button>
          </div>
        </section>
      </article>
    `;
  }

  function buildSketchVariants(prompt) {
    const cleaned = prompt.replace(/\s+/g, ' ').trim();
    const theme = inferTheme(cleaned);
    return [
      {
        id: 'a',
        label: 'A',
        title: `${theme}｜信息先行式布局`,
        subtitle: '适合产品评审与字段确认，强调结构清晰和操作路径。',
        note: '该方案把卖点、费用、报名入口和 FAQ 按纵向层级排列，适合先讨论信息完整度。',
        layers: [
          { name: '主视觉', copy: '大标题 + 副标题 + 关键价值点 + 主按钮，第一屏直接给出参与动机。' },
          { name: '信息卡片', copy: '费用、时间、地点、对象、报名截止时间做成四宫格，减少来回跳转。' },
          { name: '表单与 FAQ', copy: '将报名表单置于前半屏，FAQ 放在末尾，降低用户决策成本。' },
        ],
      },
      {
        id: 'b',
        label: 'B',
        title: `${theme}｜体验沉浸式布局`,
        subtitle: '适合活动海报感更强的页面，突出视觉氛围和滚动节奏。',
        note: '该方案使用卡片分层和粘性按钮，适合强调内容浏览体验与视觉氛围。',
        layers: [
          { name: '沉浸头图', copy: '大图封面、氛围遮罩和短文案，先建立情绪与主题识别。' },
          { name: '分段叙事', copy: '亮点、流程、嘉宾、日程按节段展开，提升滚动感和停留时长。' },
          { name: '悬浮行动', copy: '报名按钮在移动端底部固定，桌面端在侧边保持可见。' },
        ],
      },
    ];
  }

  function inferTheme(prompt) {
    const rules = [
      ['活动', '活动报名页'],
      ['课程', '课程介绍页'],
      ['招聘', '招聘落地页'],
      ['社区', '社区招募页'],
      ['直播', '直播预约页'],
    ];
    const match = rules.find(([keyword]) => prompt.includes(keyword));
    return match ? match[1] : '创意草图';
  }

  function buildMarkdown(prompt, variants, generatedAt) {
    return [
      `# 前端交互草图生成说明`,
      '',
      `- 需求：${prompt}`,
      `- 生成时间：${generatedAt}`,
      '',
      '## 方案 A：信息先行式布局',
      `- 标题：${variants[0].title}`,
      `- 说明：${variants[0].note}`,
      '- 结构：主视觉 / 信息卡片 / 表单与 FAQ',
      '',
      '## 方案 B：体验沉浸式布局',
      `- 标题：${variants[1].title}`,
      `- 说明：${variants[1].note}`,
      '- 结构：沉浸头图 / 分段叙事 / 悬浮行动',
      '',
      '## 评审建议',
      '- 若优先交付和字段确认，选择方案 A。',
      '- 若重视传播感和视觉氛围，选择方案 B。',
    ].join('\n');
  }

  function setStateMessage(message, kind) {
    refs.state.classList.toggle('is-error', kind === 'error');
    refs.state.innerHTML = `
      <div class="activity-state__inline">${kind === 'loaded' ? '' : '<span class="spinner" aria-hidden="true"></span>'}<h3>${kind === 'error' ? '网络错误' : kind === 'loaded' ? '已生成' : kind === 'empty' ? '等待输入' : '处理中'}</h3></div>
      <p>${escapeHtml(message)}</p>
    `;
  }

  function formatTime(date) {
    const pad = (value) => String(value).padStart(2, '0');
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
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
