const weeklyReportMock = {
  id: "weekly-report-sztu-06",
  weekLabel: "6 月第 1 周",
  title: "深技大晨跑与夜跑运营周报",
  intro: "西丽湖环线、官龙山坡道和北区操场三类活动保持稳定参与，适合直接生成给社群的本周复盘。",
  activities: 8,
  participants: 126,
  distanceKm: 428,
  photoTitle: "西丽湖日出合影占位",
  photoCaption: "最佳活动照片区域预留 16:9 封面，后续接入活动相册 API 后替换为真实图片。",
  highlights: [
    "晨跑打卡覆盖 4 个训练小组",
    "夜跑活动平均参与 18 人",
    "长距离组完成官龙山坡道专项"
  ],
  apiHint: "/api/v1/reports/weekly-activity-preview"
};

const weeklyReportState = {
  loading: true,
  emptyMode: false,
  errorMode: false,
  generated: false,
  message: ""
};

const weeklyReportDom = {};

document.addEventListener("DOMContentLoaded", initWeeklyReportPreview);

function initWeeklyReportPreview() {
  bindWeeklyReportElements();
  if (!weeklyReportDom.root) return;
  renderWeeklyReportLoading();
  window.setTimeout(() => {
    weeklyReportState.loading = false;
    renderWeeklyReportPreview();
  }, 280);
}

function bindWeeklyReportElements() {
  weeklyReportDom.root = document.querySelector("[data-weekly-report]");
  weeklyReportDom.badge = document.querySelector("[data-weekly-report-badge]");
  weeklyReportDom.summary = document.querySelector("[data-weekly-report-summary]");
  weeklyReportDom.state = document.querySelector("[data-weekly-report-state]");
  weeklyReportDom.preview = document.querySelector("[data-weekly-report-preview]");
}

function fetchWeeklyReportPreview() {
  return Promise.resolve(weeklyReportMock);
}

function handleWeeklyReportGenerate() {
  weeklyReportState.generated = true;
  weeklyReportState.message = "已生成本地周报草稿：可复制指标与照片占位说明给社群运营同学。";
  renderWeeklyReportPreview();
}

function handleWeeklyReportEmpty() {
  weeklyReportState.emptyMode = true;
  weeklyReportState.errorMode = false;
  weeklyReportState.generated = false;
  weeklyReportState.message = "已切换到暂无数据演示。";
  renderWeeklyReportPreview();
}

function handleWeeklyReportError() {
  weeklyReportState.errorMode = true;
  weeklyReportState.emptyMode = false;
  weeklyReportState.generated = false;
  weeklyReportState.message = "加载失败演示：后续 API 不可用时展示此文案与重试入口。";
  renderWeeklyReportPreview();
}

function handleWeeklyReportRetry() {
  weeklyReportState.loading = true;
  weeklyReportState.emptyMode = false;
  weeklyReportState.errorMode = false;
  weeklyReportState.message = "正在重新整理本地周报预览。";
  renderWeeklyReportLoading();
  window.setTimeout(() => {
    weeklyReportState.loading = false;
    renderWeeklyReportPreview();
  }, 260);
}

function handleWeeklyReportReset() {
  weeklyReportState.emptyMode = false;
  weeklyReportState.errorMode = false;
  weeklyReportState.generated = false;
  weeklyReportState.message = "已恢复本周运营周报预览。";
  renderWeeklyReportPreview();
}

function renderWeeklyReportLoading() {
  renderWeeklyReportSummary(null);
  if (weeklyReportDom.badge) weeklyReportDom.badge.textContent = "加载中";
  if (weeklyReportDom.state) {
    weeklyReportDom.state.className = "weekly-report-state";
    weeklyReportDom.state.innerHTML = '<div class="activity-state__inline"><span class="spinner" aria-hidden="true"></span><h3>加载中</h3></div><p>正在整理本周活动运营数据。</p>';
  }
  if (weeklyReportDom.preview) {
    weeklyReportDom.preview.innerHTML = '<article class="weekly-report-skeleton" aria-hidden="true"></article>';
  }
}

function renderWeeklyReportPreview() {
  fetchWeeklyReportPreview().then((report) => {
    renderWeeklyReportSummary(report);
    renderWeeklyReportState(report);
    renderWeeklyReportCard(report);
  }).catch(() => {
    weeklyReportState.errorMode = true;
    renderWeeklyReportSummary(null);
    renderWeeklyReportState(null);
    renderWeeklyReportCard(null);
  });
}

function renderWeeklyReportSummary(report) {
  if (!weeklyReportDom.summary) return;
  if (!report || weeklyReportState.loading) {
    weeklyReportDom.summary.innerHTML = '<span class="summary-chip">加载中</span><span class="summary-chip">后续 API：/api/v1/reports/weekly-activity-preview</span>';
    return;
  }
  if (weeklyReportState.emptyMode) {
    weeklyReportDom.summary.innerHTML = '<span class="summary-chip">暂无数据</span><span class="summary-chip">可恢复示例</span>';
    return;
  }
  if (weeklyReportState.errorMode) {
    weeklyReportDom.summary.innerHTML = '<span class="summary-chip">加载失败</span><span class="summary-chip">可重试</span>';
    return;
  }
  const chips = [
    report.weekLabel,
    `${report.activities} 场活动`,
    `${report.participants} 人参与`,
    `${report.distanceKm} 公里`
  ];
  weeklyReportDom.summary.innerHTML = chips.map((text) => `<span class="summary-chip">${escapeWeeklyReportHtml(text)}</span>`).join("");
}

function renderWeeklyReportState(report) {
  if (!weeklyReportDom.state) return;
  if (weeklyReportDom.badge) weeklyReportDom.badge.textContent = weeklyReportState.generated ? "已生成草稿" : "本地预览";
  if (weeklyReportState.emptyMode) {
    weeklyReportDom.state.className = "weekly-report-state";
    weeklyReportDom.state.innerHTML = '<div><h3>暂无数据</h3><p>本周还没有可汇总的活动，生成按钮已禁用。</p></div><button class="btn btn-primary" type="button" data-weekly-report-reset>恢复预览</button>';
    weeklyReportDom.state.querySelector("[data-weekly-report-reset]")?.addEventListener("click", handleWeeklyReportReset);
    return;
  }
  if (weeklyReportState.errorMode) {
    weeklyReportDom.state.className = "weekly-report-state is-error";
    weeklyReportDom.state.innerHTML = '<div><h3>加载失败</h3><p>暂时无法整理周报预览，请检查网络或稍后重试。</p></div><button class="btn btn-primary" type="button" data-weekly-report-retry>重试</button>';
    weeklyReportDom.state.querySelector("[data-weekly-report-retry]")?.addEventListener("click", handleWeeklyReportRetry);
    return;
  }
  const message = weeklyReportState.message || `本地示例就绪，后续函数边界保留在 fetchWeeklyReportPreview，可接入 ${report.apiHint}。`;
  weeklyReportDom.state.className = "weekly-report-state";
  weeklyReportDom.state.innerHTML = `<div><h3>${escapeWeeklyReportHtml(weeklyReportState.generated ? "周报草稿已生成" : "周报预览就绪")}</h3><p>${escapeWeeklyReportHtml(message)}</p></div>`;
}

function renderWeeklyReportCard(report) {
  if (!weeklyReportDom.preview) return;
  if (weeklyReportState.emptyMode) {
    weeklyReportDom.preview.innerHTML = '<article class="weekly-report-empty"><h3>暂无数据</h3><p>本周暂无活动、参与人数和总里程，等活动发布后再生成运营周报。</p><button class="btn btn-secondary" type="button" data-weekly-report-reset>恢复预览</button></article>';
    weeklyReportDom.preview.querySelector("[data-weekly-report-reset]")?.addEventListener("click", handleWeeklyReportReset);
    return;
  }
  if (weeklyReportState.errorMode) {
    weeklyReportDom.preview.innerHTML = '<article class="weekly-report-empty"><h3>加载失败</h3><p>周报预览暂不可用，点击重试重新读取本地示例数据。</p><button class="btn btn-primary" type="button" data-weekly-report-retry>重试</button></article>';
    weeklyReportDom.preview.querySelector("[data-weekly-report-retry]")?.addEventListener("click", handleWeeklyReportRetry);
    return;
  }
  weeklyReportDom.preview.innerHTML = `<article class="weekly-report__surface">
    <section class="weekly-report__content">
      <span class="weekly-report__eyebrow">${escapeWeeklyReportHtml(report.weekLabel)} · Campus Ops</span>
      <h3>${escapeWeeklyReportHtml(report.title)}</h3>
      <p>${escapeWeeklyReportHtml(report.intro)}</p>
      <section class="weekly-report__stats" aria-label="本周运营指标">
        ${renderWeeklyReportStat("活动数量", `${report.activities} 场`, "72%")}
        ${renderWeeklyReportStat("参与人数", `${report.participants} 人`, "86%")}
        ${renderWeeklyReportStat("总里程", `${report.distanceKm} 公里`, "78%")}
      </section>
      <section class="weekly-report__timeline" aria-label="本周亮点">
        <h4>本周运营亮点</h4>
        <ol>${report.highlights.map((item) => `<li>${escapeWeeklyReportHtml(item)}</li>`).join("")}</ol>
      </section>
      <nav class="weekly-report__actions" aria-label="运营周报操作">
        <button class="btn btn-primary" type="button" data-weekly-report-generate ${weeklyReportState.generated ? "disabled" : ""}>${weeklyReportState.generated ? "已生成周报" : "生成周报"}</button>
        <button class="btn btn-secondary" type="button" data-weekly-report-empty>查看空态</button>
        <button class="btn btn-secondary" type="button" data-weekly-report-error>模拟加载失败</button>
      </nav>
    </section>
    <aside class="weekly-report__photo" aria-label="最佳活动照片占位">
      <span class="weekly-report__photo-badge">最佳活动照片</span>
      <h4>${escapeWeeklyReportHtml(report.photoTitle)}</h4>
      <p>${escapeWeeklyReportHtml(report.photoCaption)}</p>
    </aside>
  </article>`;
  weeklyReportDom.preview.querySelector("[data-weekly-report-generate]")?.addEventListener("click", handleWeeklyReportGenerate);
  weeklyReportDom.preview.querySelector("[data-weekly-report-empty]")?.addEventListener("click", handleWeeklyReportEmpty);
  weeklyReportDom.preview.querySelector("[data-weekly-report-error]")?.addEventListener("click", handleWeeklyReportError);
}

function renderWeeklyReportStat(label, value, meter) {
  return `<article class="weekly-report__stat"><span>${escapeWeeklyReportHtml(label)}</span><strong>${escapeWeeklyReportHtml(value)}</strong><div class="weekly-report__meter" style="--weekly-meter: ${escapeWeeklyReportHtml(meter)}"><span></span></div></article>`;
}

function escapeWeeklyReportHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&apos;");
}
