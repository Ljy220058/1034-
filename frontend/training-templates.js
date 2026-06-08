const trainingTemplates = [
  {
    id: "template-5k",
    title: "5 公里入门提升",
    distance: "5 公里",
    audience: "适合刚开始规律跑步、希望完成校园 5K 的成员",
    cycle: "4 周",
    sessions: "每周 3 次",
    goal: "稳定完成 5 公里，建立轻松配速习惯",
    level: "新手友好",
    weeks: [
      { week: "第 1 周", focus: "建立跑走节奏", plan: ["轻松跑 2K + 拉伸", "跑走结合 25 分钟", "周末慢跑 3K"] },
      { week: "第 2 周", focus: "延长连续跑时间", plan: ["轻松跑 3K", "短坡冲刺 6 组", "周末慢跑 4K"] },
      { week: "第 3 周", focus: "感受目标配速", plan: ["轻松跑 3K", "节奏跑 2K", "周末模拟 5K"] },
      { week: "第 4 周", focus: "减量与完成", plan: ["恢复跑 2K", "唤醒跑 15 分钟", "完成 5K 测试"] }
    ]
  },
  {
    id: "template-10k",
    title: "10 公里稳步进阶",
    distance: "10 公里",
    audience: "适合已能完成 5K、想挑战 10K 的跑团成员",
    cycle: "6 周",
    sessions: "每周 4 次",
    goal: "顺利完成 10 公里，并掌握一次节奏训练",
    level: "进阶耐力",
    weeks: [
      { week: "第 1 周", focus: "巩固基础跑量", plan: ["轻松跑 4K", "核心力量 20 分钟", "节奏跑 3K", "周末长跑 6K"] },
      { week: "第 2 周", focus: "增加长距离", plan: ["轻松跑 5K", "间歇 400 米 6 组", "恢复跑 3K", "周末长跑 7K"] },
      { week: "第 3 周", focus: "稳定配速输出", plan: ["轻松跑 5K", "节奏跑 4K", "恢复跑 3K", "周末长跑 8K"] },
      { week: "第 4 周", focus: "跑姿与效率", plan: ["轻松跑 4K", "跑姿 drills", "间歇 800 米 4 组", "周末长跑 9K"] },
      { week: "第 5 周", focus: "接近目标距离", plan: ["恢复跑 4K", "节奏跑 5K", "轻松跑 3K", "周末模拟 10K"] },
      { week: "第 6 周", focus: "减量测试", plan: ["轻松跑 3K", "唤醒跑 20 分钟", "休息或拉伸", "完成 10K 测试"] }
    ]
  },
  {
    id: "template-half",
    title: "半马系统备赛",
    distance: "半马",
    audience: "适合有 10K 基础、希望完成半程马拉松的成员",
    cycle: "10 周",
    sessions: "每周 4–5 次",
    goal: "完成 21.0975 公里，形成补给与长跑节奏",
    level: "耐力挑战",
    weeks: [
      { week: "第 1–2 周", focus: "建立半马基础", plan: ["轻松跑 6K", "节奏跑 4K", "力量训练", "周末长跑 10K"] },
      { week: "第 3–4 周", focus: "提升乳酸阈值", plan: ["轻松跑 7K", "间歇 1K 4 组", "恢复跑 5K", "周末长跑 12–14K"] },
      { week: "第 5–6 周", focus: "补给演练", plan: ["轻松跑 8K", "半马配速跑 6K", "核心训练", "周末长跑 15–17K"] },
      { week: "第 7–8 周", focus: "峰值跑量", plan: ["恢复跑 6K", "节奏跑 8K", "轻松跑 5K", "周末长跑 18–20K"] },
      { week: "第 9–10 周", focus: "减量比赛", plan: ["轻松跑 5K", "目标配速唤醒", "拉伸放松", "完成半马"] }
    ]
  },
  {
    id: "template-marathon",
    title: "全马耐力构建",
    distance: "全马",
    audience: "适合有半马经验、准备第一次全程马拉松的稳定跑者",
    cycle: "16 周",
    sessions: "每周 5 次",
    goal: "安全完成全马，掌握长距离补给与恢复节奏",
    level: "高阶备赛",
    weeks: [
      { week: "第 1–4 周", focus: "基础跑量累积", plan: ["轻松跑 8K", "马拉松配速跑 6K", "恢复跑", "力量训练", "周末长跑 18–22K"] },
      { week: "第 5–8 周", focus: "耐力与配速控制", plan: ["轻松跑 10K", "间歇 1K 5 组", "恢复跑 6K", "配速跑 10K", "周末长跑 24–28K"] },
      { week: "第 9–12 周", focus: "峰值长距离", plan: ["恢复跑 8K", "马拉松配速跑 14K", "轻松跑 10K", "核心力量", "周末长跑 30–32K"] },
      { week: "第 13–14 周", focus: "比赛模拟", plan: ["轻松跑 8K", "配速跑 12K", "补给演练", "周末长跑 26–30K"] },
      { week: "第 15–16 周", focus: "减量与比赛", plan: ["轻松跑 6K", "唤醒跑 20 分钟", "睡眠与拉伸", "完成全马"] }
    ]
  }
];

const templateState = {
  selectedId: "template-5k",
  usedIds: new Set(),
  loading: true,
  emptyMode: false,
  message: ""
};

const templateDom = {};

document.addEventListener("DOMContentLoaded", initTrainingTemplates);

function initTrainingTemplates() {
  bindTrainingTemplateElements();
  if (!templateDom.root) return;
  bindTrainingTemplateEvents();
  renderTrainingTemplatesLoading();
  window.setTimeout(() => {
    templateState.loading = false;
    renderTrainingTemplates();
  }, 260);
}

function bindTrainingTemplateElements() {
  templateDom.root = document.querySelector("[data-training-templates]");
  templateDom.list = document.querySelector("[data-template-list]");
  templateDom.detail = document.querySelector("[data-template-detail]");
  templateDom.state = document.querySelector("[data-template-state]");
  templateDom.summary = document.querySelector("[data-template-summary]");
  templateDom.emptyToggle = document.querySelector("[data-template-empty-toggle]");
  templateDom.reset = document.querySelector("[data-template-reset]");
}

function bindTrainingTemplateEvents() {
  templateDom.list?.addEventListener("click", handleTemplateListClick);
  templateDom.list?.addEventListener("keydown", handleTemplateListKeydown);
  templateDom.detail?.addEventListener("click", handleTemplateDetailClick);
  templateDom.emptyToggle?.addEventListener("click", handleTemplateEmptyToggle);
  templateDom.reset?.addEventListener("click", handleTemplateReset);
}

function handleTemplateListClick(event) {
  const card = event.target.closest("[data-template-id]");
  if (!card) return;
  templateState.selectedId = card.dataset.templateId;
  templateState.message = `已打开「${getSelectedTemplate().title}」详情。`;
  renderTrainingTemplates();
}

function handleTemplateListKeydown(event) {
  if (!["Enter", " "].includes(event.key)) return;
  const card = event.target.closest("[data-template-id]");
  if (!card) return;
  event.preventDefault();
  templateState.selectedId = card.dataset.templateId;
  templateState.message = `已打开「${getSelectedTemplate().title}」详情。`;
  renderTrainingTemplates();
}

function handleTemplateDetailClick(event) {
  const button = event.target.closest("[data-template-use]");
  if (!button) return;
  const current = getSelectedTemplate();
  templateState.usedIds.add(current.id);
  templateState.message = `已将「${current.title}」加入本地计划草稿，可继续切换其他模板。`;
  renderTrainingTemplates();
}

function handleTemplateEmptyToggle() {
  templateState.emptyMode = true;
  templateState.message = "已切换到空态演示。";
  renderTrainingTemplates();
}

function handleTemplateReset() {
  templateState.emptyMode = false;
  templateState.selectedId = "template-5k";
  templateState.usedIds.clear();
  templateState.message = "已恢复模板库初始状态。";
  renderTrainingTemplates();
}

function renderTrainingTemplatesLoading() {
  renderTemplateSummary();
  if (templateDom.state) {
    templateDom.state.className = "template-state";
    templateDom.state.innerHTML = '<div class="activity-state__inline"><span class="spinner" aria-hidden="true"></span><h3>加载中</h3></div><p>正在整理训练计划模板。</p>';
  }
  if (templateDom.list) {
    templateDom.list.innerHTML = '<article class="template-skeleton" aria-hidden="true"></article><article class="template-skeleton" aria-hidden="true"></article><article class="template-skeleton" aria-hidden="true"></article><article class="template-skeleton" aria-hidden="true"></article>';
  }
  if (templateDom.detail) {
    templateDom.detail.innerHTML = '<article class="template-skeleton template-skeleton--detail" aria-hidden="true"></article>';
  }
}

function renderTrainingTemplates() {
  renderTemplateSummary();
  renderTemplateState();
  renderTemplateList();
  renderTemplateDetail();
}

function renderTemplateSummary() {
  if (!templateDom.summary) return;
  const usedCount = templateState.usedIds.size;
  const chips = [
    `模板 ${trainingTemplates.length} 类`,
    `已使用 ${usedCount} 个`,
    templateState.emptyMode ? "空态演示" : `当前：${getSelectedTemplate().distance}`
  ];
  templateDom.summary.innerHTML = chips.map((text) => `<span class="summary-chip">${escapeTemplateHtml(text)}</span>`).join("");
}

function renderTemplateState() {
  if (!templateDom.state) return;
  if (templateState.emptyMode) {
    templateDom.state.className = "template-state";
    templateDom.state.innerHTML = '<div class="activity-state__inline"><h3>暂无数据</h3></div><p>当前没有训练模板，可点击恢复按钮回到模板库。</p><button class="btn btn-primary" type="button" data-template-reset-inline>恢复模板</button>';
    templateDom.state.querySelector("[data-template-reset-inline]")?.addEventListener("click", handleTemplateReset);
    return;
  }
  templateDom.state.className = "template-state";
  const message = templateState.message || "点击左侧模板卡片查看每周训练安排示例，使用按钮会写入本地交互状态。";
  templateDom.state.innerHTML = `<div class="activity-state__inline"><h3>模板就绪</h3></div><p>${escapeTemplateHtml(message)}</p>`;
}

function renderTemplateList() {
  if (!templateDom.list) return;
  if (templateState.emptyMode) {
    templateDom.list.innerHTML = '<article class="template-empty"><h3>暂无数据</h3><p>模板列表为空时保留清晰说明和恢复入口。</p><button class="btn btn-secondary" type="button" data-template-reset-list>恢复模板</button></article>';
    templateDom.list.querySelector("[data-template-reset-list]")?.addEventListener("click", handleTemplateReset);
    return;
  }
  templateDom.list.innerHTML = trainingTemplates.map(renderTemplateCard).join("");
}

function renderTemplateCard(item) {
  const active = item.id === templateState.selectedId;
  const used = templateState.usedIds.has(item.id);
  return `<article class="template-card ${active ? "is-active" : ""}" data-template-id="${escapeTemplateHtml(item.id)}" tabindex="0" aria-label="查看${escapeTemplateHtml(item.title)}详情" aria-current="${active ? "true" : "false"}">
    <header class="template-card__header">
      <span class="template-badge">${escapeTemplateHtml(item.distance)}</span>
      <span class="template-badge template-badge--soft">${escapeTemplateHtml(used ? "已使用" : item.level)}</span>
    </header>
    <h3>${escapeTemplateHtml(item.title)}</h3>
    <p>${escapeTemplateHtml(item.audience)}</p>
    <dl class="template-card__meta">
      <div><dt>训练周期</dt><dd>${escapeTemplateHtml(item.cycle)}</dd></div>
      <div><dt>每周次数</dt><dd>${escapeTemplateHtml(item.sessions)}</dd></div>
      <div><dt>预计目标</dt><dd>${escapeTemplateHtml(item.goal)}</dd></div>
    </dl>
  </article>`;
}

function renderTemplateDetail() {
  if (!templateDom.detail) return;
  if (templateState.emptyMode) {
    templateDom.detail.innerHTML = '<article class="template-empty template-empty--detail"><h3>暂无数据</h3><p>选择恢复模板后，这里会显示每周训练安排示例。</p></article>';
    return;
  }
  const item = getSelectedTemplate();
  const used = templateState.usedIds.has(item.id);
  templateDom.detail.innerHTML = `<article class="template-detail-card">
    <header class="template-detail-card__header">
      <div>
        <span class="summary-chip">${escapeTemplateHtml(item.level)}</span>
        <h3>${escapeTemplateHtml(item.title)}</h3>
        <p>${escapeTemplateHtml(item.goal)}</p>
      </div>
      <button class="btn btn-primary" type="button" data-template-use="${escapeTemplateHtml(item.id)}" ${used ? "disabled" : ""}>${escapeTemplateHtml(used ? "已加入本地草稿" : "使用此模板")}</button>
    </header>
    <section class="template-week-grid" aria-label="每周训练安排示例">
      ${item.weeks.map(renderTemplateWeek).join("")}
    </section>
  </article>`;
}

function renderTemplateWeek(week) {
  return `<article class="template-week">
    <header><span>${escapeTemplateHtml(week.week)}</span><strong>${escapeTemplateHtml(week.focus)}</strong></header>
    <ul>${week.plan.map((entry) => `<li>${escapeTemplateHtml(entry)}</li>`).join("")}</ul>
  </article>`;
}

function getSelectedTemplate() {
  return trainingTemplates.find((item) => item.id === templateState.selectedId) || trainingTemplates[0];
}

function escapeTemplateHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}
