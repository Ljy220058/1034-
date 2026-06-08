(()=>{
  "use strict";

  const API_BASE = "/api/v1";
  const root = document.querySelector("[data-calendar-export-root]");
  if (!root) return;

  const scenarios = {
    "no-training": {
      title: "场景一：无训练",
      copy: "当天没有训练安排时，建议直接导出空日历说明，提示成员稍后再试或查看其他日期。",
      stateTitle: "暂无训练",
      stateText: "今天没有可导出的训练安排，可点击恢复默认示例。",
      primary: "导出空日历",
      tone: "is-empty",
      timeline: [
        { title: "检查结果", text: "训练计划列表为空，导出按钮应保留但显示空态说明。" },
        { title: "主按钮", text: "使用“导出空日历”作为主操作，方便直接生成一个空 ICS 说明。" },
        { title: "验证步骤", text: "切换到此场景后，确认 375px 下按钮换行正常且无横向滚动。" }
      ]
    },
    "missing-location": {
      title: "场景二：缺少地点",
      copy: "当训练时间和内容存在，但地点字段缺失时，导出需要降级展示并提醒补全地点信息。",
      stateTitle: "地点未填写",
      stateText: "当前训练已有时间与项目，但缺少地点字段，导出将使用“待补充地点”占位。",
      primary: "继续导出",
      tone: "is-empty",
      timeline: [
        { title: "降级展示", text: "在日历中使用“待补充地点”文案，不阻断其他训练内容的导出。" },
        { title: "主按钮", text: "保留继续导出，避免因为单个字段缺失而中断整个计划。" },
        { title: "验证步骤", text: "检查文案是否完整、按钮是否可点击，以及说明区域是否清晰。" }
      ]
    },
    "cross-day": {
      title: "场景三：跨天训练",
      copy: "长距离或夜间训练可能跨越两个自然日，导出时需要同时提示开始和结束时间。",
      stateTitle: "跨天训练",
      stateText: "当前训练从晚上开始并延续到次日，建议在导出说明中同时展示开始/结束日期。",
      primary: "查看时间拆分",
      tone: "is-empty",
      timeline: [
        { title: "时间提示", text: "明确标出起始日期、结束日期和跨天说明，减少成员误解。" },
        { title: "主按钮", text: "提供“查看时间拆分”帮助用户确认跨天训练的边界。" },
        { title: "验证步骤", text: "确认标题、说明和时间节点在平板与手机宽度下都能完整显示。" }
      ]
    },
    "export-error": {
      title: "场景四：导出失败",
      copy: "如果后端导出接口返回异常，应明确告知失败原因，并提供重试入口而不是静默失效。",
      stateTitle: "导出失败",
      stateText: "ICS 文件生成失败，请稍后重试或检查后端导出接口是否可用。",
      primary: "重试导出",
      tone: "is-error",
      timeline: [
        { title: "错误反馈", text: "展示网络/服务异常文案，避免用户误以为导出成功。" },
        { title: "主按钮", text: "使用“重试导出”触发二次请求，按钮需有 hover/active/disabled 三态。" },
        { title: "验证步骤", text: "断开后端或模拟 500 后，确认错误态与重试按钮都能正常出现。" }
      ]
    }
  };

  const dom = {
    state: root.querySelector("[data-calendar-export-state]"),
    timeline: root.querySelector("[data-calendar-export-timeline]"),
    title: root.querySelector("[data-calendar-export-title]"),
    copy: root.querySelector("[data-calendar-export-copy]"),
    buttons: Array.from(root.querySelectorAll("[data-calendar-export-toggle]")),
  };

  let current = "no-training";
  let loading = true;

  document.addEventListener("DOMContentLoaded", initCalendarExport);

  function initCalendarExport() {
    bindCalendarEvents();
    renderCalendarExport();
    window.setTimeout(() => {
      loading = false;
      renderCalendarExport();
    }, 220);
  }

  function bindCalendarEvents() {
    dom.buttons.forEach((button) => button.addEventListener("click", () => handleScenarioChange(button.dataset.calendarExportToggle || "")));
  }

  function handleScenarioChange(key) {
    if (!scenarios[key]) return;
    current = key;
    renderCalendarExport();
  }

  async function handlePrimaryAction(key) {
    if (key === "export-error") {
      loading = true;
      renderCalendarExport();
      await fetch(`${API_BASE}/training-calendar/export`, { headers: { Accept: "application/json" } }).catch(() => null);
      window.setTimeout(() => {
        loading = false;
        renderCalendarExport();
      }, 260);
      return;
    }
    current = key;
    renderCalendarExport();
  }

  function renderCalendarExport() {
    const scenario = scenarios[current];
    dom.buttons.forEach((button) => {
      const active = button.dataset.calendarExportToggle === current;
      button.classList.toggle("btn-primary", active);
      button.classList.toggle("btn-secondary", !active);
      button.disabled = loading && !active;
    });

    if (loading) {
      dom.state.className = "calendar-export__state is-empty";
      dom.state.innerHTML = '<div class="activity-state__inline"><span class="spinner" aria-hidden="true"></span><h3>加载中</h3></div><p>正在准备训练日历导出场景。</p>';
      dom.timeline.innerHTML = '<article class="calendar-export__skeleton" aria-hidden="true"></article>';
      dom.title.textContent = "正在加载";
      dom.copy.textContent = "稍后将展示四种中文空态与异常提示方案。";
      return;
    }

    dom.state.className = `calendar-export__state ${scenario.tone}`;
    dom.state.innerHTML = `
      <div class="activity-state__inline">
        ${scenario.tone === "is-error" ? "" : '<span class="spinner" aria-hidden="true"></span>'}
        <h3>${scenario.stateTitle}</h3>
      </div>
      <p>${scenario.stateText}</p>
      <button class="btn btn-primary" type="button">${scenario.primary}</button>
    `;

    dom.timeline.innerHTML = scenario.timeline.map((item) => `
      <article class="calendar-export__timeline-item">
        <div>
          <h4>${item.title}</h4>
          <p>${item.text}</p>
        </div>
      </article>
    `).join("");

    dom.title.textContent = scenario.title;
    dom.copy.textContent = scenario.copy;
    dom.state.querySelector("button")?.addEventListener("click", () => handlePrimaryAction(current));
  }
})();
