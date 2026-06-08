const emptyStatePresets = {
  home: {
    tone: "default",
    label: "首页空闲态",
    title: "今天还没有新的跑团动态",
    message: "先浏览训练模板，或创建一条活动安排，让成员一打开首页就知道下一步做什么。",
    actionLabel: "创建活动安排",
    actionHref: "/tasks/create?source=home-empty",
    illustration: "home"
  },
  list: {
    tone: "default",
    label: "空列表",
    title: "暂无数据",
    message: "当前列表没有可展示内容，调整筛选条件或创建第一条约跑任务。",
    actionLabel: "创建第一条活动",
    actionHref: "/tasks/create?source=empty-list",
    illustration: "list"
  },
  loaded: {
    tone: "success",
    label: "加载完成",
    title: "数据已同步，暂时没有待处理项",
    message: "系统已经完成刷新；如果成员刚提交新内容，可以稍后再次加载。",
    actionLabel: "再次刷新",
    actionType: "button",
    illustration: "loaded"
  },
  search: {
    tone: "default",
    label: "搜索无结果",
    title: "没有找到匹配内容",
    message: "换一个关键词、清空筛选，或回到全部类型查看已有活动。",
    actionLabel: "清空搜索条件",
    actionType: "button",
    illustration: "search"
  },
  permission: {
    tone: "danger",
    label: "权限不足",
    title: "当前账号暂无权限",
    message: "请联系管理员开通跑团管理权限，或切换到具备权限的账号后重试。",
    actionLabel: "联系管理员",
    actionHref: "/support?topic=permission",
    illustration: "permission"
  }
};

function getEmptyStatePreset(kind) {
  return emptyStatePresets[kind] || emptyStatePresets.list;
}

function renderEmptyIllustration(type) {
  const className = `empty-illustration empty-illustration--${escapeEmptyHtml(type || "list")}`;
  const blocks = type === "search" || type === "permission"
    ? "<span></span>"
    : "<span></span><span></span><span></span>";
  return `<figure class="${className}" aria-hidden="true">${blocks}</figure>`;
}

function renderEmptyState(options = {}) {
  const preset = getEmptyStatePreset(options.kind);
  const title = options.title || preset.title;
  const message = options.message || preset.message;
  const actionLabel = options.actionLabel || preset.actionLabel;
  const actionHref = options.actionHref || preset.actionHref || "#";
  const actionType = options.actionType || preset.actionType || "link";
  const tone = options.tone || preset.tone;
  const toneClass = tone === "danger" ? " is-danger" : tone === "success" ? " is-success" : "";
  const illustration = renderEmptyIllustration(options.illustration || preset.illustration);
  const action = actionType === "button"
    ? `<button class="btn btn-primary" type="button" data-empty-action="${escapeEmptyHtml(options.kind || "list")}">${escapeEmptyHtml(actionLabel)}</button>`
    : `<a class="btn btn-primary" href="${escapeEmptyHtml(actionHref)}">${escapeEmptyHtml(actionLabel)}</a>`;

  return `
    <section class="empty-guide-card${toneClass}" aria-label="${escapeEmptyHtml(preset.label)}">
      <div class="empty-guide-card__visual">${illustration}</div>
      <header>
        <span class="summary-chip">${escapeEmptyHtml(preset.label)}</span>
        <h3>${escapeEmptyHtml(title)}</h3>
      </header>
      <p>${escapeEmptyHtml(message)}</p>
      <nav class="empty-guide-card__actions" aria-label="空状态操作">
        ${action}
      </nav>
    </section>`;
}

function mountEmptyState(target, options = {}) {
  if (!target) return;
  target.innerHTML = renderEmptyState(options);
}

function bootstrapEmptyStateDemo() {
  const demo = document.querySelector("[data-empty-guide-demo]");
  if (!demo) return;
  mountEmptyState(demo.querySelector('[data-empty-slot="home"]'), { kind: "home" });
  mountEmptyState(demo.querySelector('[data-empty-slot="list"]'), { kind: "list" });
  mountEmptyState(demo.querySelector('[data-empty-slot="loaded"]'), { kind: "loaded" });
  demo.querySelector('[data-empty-action="search"]')?.addEventListener("click", () => {
    const input = document.querySelector("[data-activity-search]");
    if (input) {
      input.value = "";
      input.dispatchEvent(new Event("input", { bubbles: true }));
      input.focus();
    }
  });
  demo.querySelector('[data-empty-action="loaded"]')?.addEventListener("click", (event) => {
    const button = event.currentTarget;
    button.disabled = true;
    button.textContent = "刷新中";
    window.setTimeout(() => {
      button.disabled = false;
      button.textContent = "再次刷新";
    }, 680);
  });
}

function escapeEmptyHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

document.addEventListener("DOMContentLoaded", bootstrapEmptyStateDemo);
window.renderEmptyState = renderEmptyState;
window.mountEmptyState = mountEmptyState;
