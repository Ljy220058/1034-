(() => {
  "use strict";

  const ROUTE_DATA = {
    name: "滨江夜跑补给线",
    distance: "12.8 km",
    climb: "168 m",
    supplies: ["3.2 km 自助水站", "7.5 km 能量胶点", "10.8 km 拉伸补给"],
    transport: "起点近江地铁站 A 口集合，终点钱江新城可步行 6 分钟换乘 4/7 号线。",
    audience: "适合 10K 进阶、半马备赛、想练节奏跑的团员。",
    shareText: "我准备报名 1034「滨江夜跑补给线」：12.8 km / 168 m 爬升，3 个补给点，适合 10K 进阶和半马备赛，一起约跑吗？",
  };

  const state = { loading: false, copied: false, error: "", empty: false };
  const refs = {};

  document.addEventListener("DOMContentLoaded", initRouteHighlightCard);

  function initRouteHighlightCard() {
    cacheRouteRefs();
    bindRouteEvents();
    renderRouteCard();
  }

  function cacheRouteRefs() {
    refs.card = document.querySelector("[data-route-card]");
    refs.name = document.querySelector("[data-route-name]");
    refs.distance = document.querySelector("[data-route-distance]");
    refs.climb = document.querySelector("[data-route-climb]");
    refs.supplies = document.querySelector("[data-route-supplies]");
    refs.transport = document.querySelector("[data-route-transport]");
    refs.audience = document.querySelector("[data-route-audience]");
    refs.share = document.querySelector("[data-route-share]");
    refs.status = document.querySelector("[data-route-status]");
    refs.copy = document.querySelector("[data-route-copy]");
    refs.refresh = document.querySelector("[data-route-refresh]");
    refs.demoError = document.querySelector("[data-route-demo-error]");
    refs.demoEmpty = document.querySelector("[data-route-demo-empty]");
  }

  function bindRouteEvents() {
    refs.copy?.addEventListener("click", handleCopyRoute);
    refs.refresh?.addEventListener("click", handleRefreshRoute);
    refs.demoError?.addEventListener("click", handleDemoError);
    refs.demoEmpty?.addEventListener("click", handleDemoEmpty);
  }

  function renderRouteCard() {
    if (!refs.card) return;
    refs.card.classList.toggle("is-loading", state.loading);
    refs.card.classList.toggle("is-error", Boolean(state.error));
    refs.card.classList.toggle("is-empty", state.empty);

    if (state.loading) {
      renderRouteLoading();
      return;
    }
    if (state.error) {
      renderRouteError();
      return;
    }
    if (state.empty) {
      renderRouteEmpty();
      return;
    }
    renderRouteContent(ROUTE_DATA);
  }

  function renderRouteContent(route) {
    setText(refs.name, route.name);
    setText(refs.distance, route.distance);
    setText(refs.climb, route.climb);
    setText(refs.transport, route.transport);
    setText(refs.audience, route.audience);
    setText(refs.share, route.shareText);
    setText(refs.status, state.copied ? "分享文案已复制" : "可直接接入路线详情页");
    if (refs.supplies) {
      refs.supplies.innerHTML = route.supplies.map((item) => `<li>${escapeHtml(item)}</li>`).join("");
    }
    if (refs.copy) {
      refs.copy.disabled = false;
      refs.copy.textContent = state.copied ? "已复制" : "一键复制分享文案";
    }
  }

  function renderRouteLoading() {
    setText(refs.name, "路线加载中");
    setText(refs.distance, "--");
    setText(refs.climb, "--");
    setText(refs.transport, "正在同步起终点交通信息。");
    setText(refs.audience, "正在匹配适合人群。");
    setText(refs.share, "分享文案生成中...");
    setText(refs.status, "加载中");
    if (refs.supplies) refs.supplies.innerHTML = "<li>补给点加载中</li>";
    if (refs.copy) {
      refs.copy.disabled = true;
      refs.copy.textContent = "生成中...";
    }
  }

  function renderRouteError() {
    setText(refs.name, "路线数据异常");
    setText(refs.distance, "--");
    setText(refs.climb, "--");
    setText(refs.transport, "请点击重试恢复默认路线卡片。");
    setText(refs.audience, "暂时无法判断适合人群。");
    setText(refs.share, state.error);
    setText(refs.status, "网络错误");
    if (refs.supplies) refs.supplies.innerHTML = "<li>补给信息暂不可用</li>";
    if (refs.copy) {
      refs.copy.disabled = true;
      refs.copy.textContent = "暂不可复制";
    }
  }

  function renderRouteEmpty() {
    setText(refs.name, "暂无数据");
    setText(refs.distance, "0 km");
    setText(refs.climb, "0 m");
    setText(refs.transport, "当前没有可展示的起终点交通信息。");
    setText(refs.audience, "暂无适合人群标签。");
    setText(refs.share, "暂无数据，请刷新后生成分享文案。");
    setText(refs.status, "暂无数据");
    if (refs.supplies) refs.supplies.innerHTML = "<li>暂无数据</li>";
    if (refs.copy) {
      refs.copy.disabled = true;
      refs.copy.textContent = "暂无文案";
    }
  }

  async function handleCopyRoute() {
    if (state.loading || state.error || state.empty) return;
    try {
      await copyText(ROUTE_DATA.shareText);
      state.copied = true;
      renderRouteCard();
      window.setTimeout(() => {
        state.copied = false;
        renderRouteCard();
      }, 1600);
    } catch (error) {
      state.error = "复制失败，请手动选择分享文案。";
      renderRouteCard();
    }
  }

  function handleRefreshRoute() {
    state.loading = true;
    state.error = "";
    state.empty = false;
    state.copied = false;
    renderRouteCard();
    window.setTimeout(() => {
      state.loading = false;
      renderRouteCard();
    }, 700);
  }

  function handleDemoError() {
    state.loading = false;
    state.empty = false;
    state.error = "路线接口暂不可用，请稍后重试。";
    renderRouteCard();
  }

  function handleDemoEmpty() {
    state.loading = false;
    state.error = "";
    state.empty = true;
    renderRouteCard();
  }

  async function copyText(text) {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return;
    }
    const area = document.createElement("textarea");
    area.value = text;
    area.setAttribute("readonly", "readonly");
    area.className = "route-copy-buffer";
    document.body.append(area);
    area.select();
    document.execCommand("copy");
    area.remove();
  }

  function setText(target, value) {
    if (target) target.textContent = value;
  }

  function escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }
})();
