(()=> {
  "use strict";

  const STORAGE_KEY = "1034.member-board.filters.v1";
  const DEFAULT_PAGE_SIZE = 9;
  const DEFAULT_ROLE = "all";
  const ROLE_OPTIONS = ["all", "member", "leader", "admin"];
  const ROLE_LABELS = {
    all: "全部角色",
    member: "普通成员",
    leader: "领队",
    admin: "管理员",
  };

  const demoMembers = [
    { id: 101, name: "林远", phone: "13800000001", role: "member", running_years: 2, pace: "5'45\"/km", usual_distance_km: 8, training_goal: "准备 10 公里 PB", created_at: "2026-05-01T09:30:00+08:00" },
    { id: 102, name: "周岚", phone: "13800000002", role: "leader", running_years: 5, pace: "5'10\"/km", usual_distance_km: 15, training_goal: "带领周末长距离", created_at: "2026-04-18T19:10:00+08:00" },
    { id: 103, name: "陈洲", phone: "13800000003", role: "admin", running_years: 7, pace: "4'55\"/km", usual_distance_km: 21, training_goal: "维护训练计划与活动排期", created_at: "2026-03-10T08:20:00+08:00" },
    { id: 104, name: "许宁", phone: "13800000004", role: "member", running_years: 1, pace: "6'20\"/km", usual_distance_km: 5, training_goal: "完成首个 5 公里训练营", created_at: "2026-05-26T12:00:00+08:00" },
    { id: 105, name: "何川", phone: "13800000005", role: "leader", running_years: 4, pace: "5'00\"/km", usual_distance_km: 12, training_goal: "组织晨跑配速组", created_at: "2026-02-15T07:45:00+08:00" },
    { id: 106, name: "宋语", phone: "13800000006", role: "member", running_years: 3, pace: "5'58\"/km", usual_distance_km: 10, training_goal: "稳定周训练频次", created_at: "2026-06-02T18:40:00+08:00" },
  ];

  const state = {
    loading: true,
    error: "",
    members: [],
    source: "demo",
    search: "",
    role: DEFAULT_ROLE,
    page: 1,
    pageSize: DEFAULT_PAGE_SIZE,
    initialized: false,
  };

  const refs = {};

  document.addEventListener("DOMContentLoaded", initMemberBoard);

  function initMemberBoard() {
    cacheRefs();
    ensureMemberBoard();
    if (!refs.root) return;
    cacheRefs();
    bindEvents();
    restoreMemberFilters();
    state.initialized = true;
    loadMemberList();
  }

  function cacheRefs() {
    refs.root = document.querySelector("[data-member-board]");
    refs.summary = refs.root?.querySelector("[data-member-summary]");
    refs.state = refs.root?.querySelector("[data-member-state]");
    refs.grid = refs.root?.querySelector("[data-member-grid]");
    refs.search = refs.root?.querySelector("[data-member-search]");
    refs.role = refs.root?.querySelector("[data-member-role]");
    refs.pageSize = refs.root?.querySelector("[data-member-page-size]");
    refs.reset = refs.root?.querySelector("[data-member-reset]");
    refs.prev = refs.root?.querySelector("[data-member-prev]");
    refs.next = refs.root?.querySelector("[data-member-next]");
    refs.paginationInfo = refs.root?.querySelector("[data-member-pagination-info]");
  }

  function ensureMemberBoard() {
    if (document.querySelector("[data-member-board]")) return;
    const shell = document.querySelector("main .shell");
    if (!shell) return;
    ensureMemberBoardStyles();
    shell.insertAdjacentHTML("beforeend", renderMemberBoardSection());
  }

  function ensureMemberBoardStyles() {
    if (document.getElementById("member-board-inline-style")) return;
    const style = document.createElement("style");
    style.id = "member-board-inline-style";
    style.textContent = `
      /* 成员列表 */
      .member-board {
        display: grid;
        gap: var(--space-5);
      }
      .member-toolbar {
        display: grid;
        grid-template-columns: minmax(0, 1.1fr) repeat(2, minmax(0, 0.45fr)) auto;
        gap: var(--space-3);
        align-items: end;
      }
      .member-toolbar__actions {
        display: flex;
        flex-wrap: wrap;
        gap: var(--space-2);
        justify-content: flex-end;
      }
      .member-state {
        padding: var(--space-5);
        border-radius: var(--radius);
        border: 1px solid var(--line);
        background: var(--surface-2);
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        justify-content: space-between;
        gap: var(--space-3);
        color: var(--muted);
      }
      .member-state h3,
      .member-empty h3 {
        margin: 0;
        color: var(--text);
      }
      .member-state p,
      .member-empty p {
        margin: 0;
      }
      .member-state.is-error {
        border-color: var(--danger-border);
        background: var(--danger-bg);
      }
      .member-state.is-loaded {
        border-color: var(--success-border);
        background: var(--success-bg);
      }
      .member-state.is-empty {
        border-style: dashed;
      }
      .member-grid {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: var(--space-4);
        min-width: 0;
      }
      .member-card,
      .member-empty {
        min-width: 0;
        padding: var(--space-5);
        border-radius: var(--radius);
        border: 1px solid var(--line);
        background: linear-gradient(180deg, var(--card-bg), var(--card-bg-soft));
        box-shadow: var(--shadow-soft);
      }
      .member-card {
        display: grid;
        gap: var(--space-3);
        transition: transform var(--transition), border-color var(--transition), box-shadow var(--transition);
      }
      .member-card:hover,
      .member-card:focus-within {
        transform: translateY(-2px);
        border-color: var(--chip-active-border);
        box-shadow: var(--shadow);
      }
      .member-card__head {
        display: flex;
        align-items: start;
        justify-content: space-between;
        gap: var(--space-3);
      }
      .member-card__head h3 {
        margin: 0 0 var(--space-2);
        font-size: var(--font-lg);
      }
      .member-card__head p,
      .task-meta {
        margin: 0;
        color: var(--muted);
      }
      .member-role-badge {
        flex: 0 0 auto;
        padding: var(--space-1) var(--space-3);
        border-radius: var(--radius-lg);
        border: 1px solid var(--line);
        background: var(--chip-bg);
        color: var(--brand-ink);
        font-size: var(--font-xs);
        font-weight: 800;
      }
      .member-role-badge[data-role="member"] {
        border-color: var(--line);
        background: var(--surface-2);
        color: var(--text);
      }
      .member-role-badge[data-role="leader"] {
        border-color: var(--warning-border);
        background: var(--warning-bg);
        color: var(--warning);
      }
      .member-role-badge[data-role="admin"] {
        border-color: var(--success-border);
        background: var(--success-bg);
        color: var(--success);
      }
      .member-meta {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: var(--space-2);
        margin: 0;
      }
      .member-meta div {
        min-width: 0;
        padding: var(--space-3);
        border-radius: var(--radius-sm);
        border: 1px solid var(--line);
        background: var(--surface-2);
      }
      .member-meta dt {
        color: var(--muted);
        font-size: var(--font-xs);
      }
      .member-meta dd {
        margin: var(--space-1) 0 0;
        word-break: break-word;
      }
      .member-card__actions,
      .member-pagination,
      .member-pagination__actions {
        display: flex;
        flex-wrap: wrap;
        gap: var(--space-2);
      }
      .member-card__actions .btn,
      .member-pagination__actions .btn {
        flex: 1 1 140px;
      }
      .member-empty {
        grid-column: 1 / -1;
        min-height: 220px;
        display: grid;
        place-items: center;
        gap: var(--space-2);
        text-align: center;
        border-style: dashed;
        color: var(--muted);
      }
      .member-pagination {
        align-items: center;
        justify-content: space-between;
        padding: var(--space-4) var(--space-5);
        border-radius: var(--radius);
        border: 1px solid var(--line);
        background: var(--surface-2);
      }
      .member-pagination__info {
        color: var(--muted);
      }
      @media (max-width: 1024px) {
        .member-toolbar {
          grid-template-columns: repeat(2, minmax(0, 1fr));
        }
      }
      @media (max-width: 768px) {
        .member-toolbar,
        .member-grid,
        .member-meta,
        .member-pagination {
          grid-template-columns: 1fr;
        }
        .member-pagination {
          display: grid;
        }
        .member-toolbar__actions {
          justify-content: stretch;
        }
      }
      @media (max-width: 560px) {
        .member-card__actions .btn,
        .member-toolbar__actions .btn,
        .member-pagination__actions .btn {
          width: 100%;
        }
      }
    `;
    document.head.appendChild(style);
  }

  function renderMemberBoardSection() {
    return `
      <section class="card section member-board" id="成员列表" data-member-board>
        <header class="section-header">
          <section>
            <h2>成员列表</h2>
            <p>支持按角色快速筛选成员，并与搜索、分页状态保持同步。</p>
          </section>
          <section class="sidebar-panel__summary" data-member-summary aria-label="成员统计">
            <span class="summary-chip">同步中</span>
          </section>
        </header>

        <section class="member-toolbar" aria-label="成员筛选工具栏">
          <label class="field">
            搜索成员
            <input type="search" placeholder="按姓名、手机号、配速或目标搜索" data-member-search />
          </label>
          <label class="field">
            角色筛选
            <select data-member-role>
              <option value="all">全部角色</option>
              <option value="member">普通成员</option>
              <option value="leader">领队</option>
              <option value="admin">管理员</option>
            </select>
          </label>
          <label class="field">
            每页数量
            <select data-member-page-size>
              <option value="6">6 人</option>
              <option value="9" selected>9 人</option>
              <option value="12">12 人</option>
            </select>
          </label>
          <nav class="member-toolbar__actions" aria-label="成员筛选操作">
            <button class="btn btn-secondary" type="button" data-member-reset>清空筛选</button>
          </nav>
        </section>

        <section class="member-state is-loading" data-member-state aria-live="polite">
          <section class="state-inline"><span class="spinner" aria-hidden="true"></span><h3>加载中</h3></section>
          <p>正在同步成员列表。</p>
        </section>

        <section class="member-grid" data-member-grid aria-label="成员卡片列表">
          <article class="member-empty">
            <h3>加载中</h3>
            <p>正在准备成员卡片。</p>
          </article>
        </section>

        <section class="member-pagination" aria-label="成员分页">
          <p class="member-pagination__info" data-member-pagination-info>第 1 页，共 1 页</p>
          <nav class="member-pagination__actions" aria-label="成员分页操作">
            <button class="btn btn-secondary" type="button" data-member-prev disabled>上一页</button>
            <button class="btn btn-secondary" type="button" data-member-next disabled>下一页</button>
          </nav>
        </section>
      </section>
    `;
  }

  function bindEvents() {
    refs.search?.addEventListener("input", handleMemberFilterChange);
    refs.role?.addEventListener("change", handleMemberRoleChange);
    refs.pageSize?.addEventListener("change", handleMemberFilterChange);
    refs.reset?.addEventListener("click", handleMemberReset);
    refs.prev?.addEventListener("click", handleMemberPrevPage);
    refs.next?.addEventListener("click", handleMemberNextPage);
  }

  function restoreMemberFilters() {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
      if (saved) {
        state.search = String(saved.search || "");
        state.role = normalizeRole(saved.role);
        state.page = Math.max(1, Number(saved.page) || 1);
        state.pageSize = normalizePageSize(saved.pageSize);
      }
    } catch {
      state.search = "";
      state.role = DEFAULT_ROLE;
      state.page = 1;
      state.pageSize = DEFAULT_PAGE_SIZE;
    }
    syncMemberControls();
  }

  function syncMemberControls() {
    if (refs.search) refs.search.value = state.search;
    if (refs.role) refs.role.value = state.role;
    if (refs.pageSize) refs.pageSize.value = String(state.pageSize);
  }

  function saveMemberFilters() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({
      search: state.search,
      role: state.role,
      page: state.page,
      pageSize: state.pageSize,
    }));
  }

  async function loadMemberList() {
    state.loading = true;
    state.error = "";
    renderMemberBoard();
    try {
      const members = await fetchMemberList({ role: state.role });
      state.members = members;
      state.source = "api";
    } catch (error) {
      state.error = buildMemberError(error);
      state.members = demoMembers.slice();
      state.source = "demo";
    } finally {
      state.loading = false;
      clampMemberPage();
      renderMemberBoard();
      saveMemberFilters();
    }
  }

  function fetchMemberList({ role } = {}) {
    const normalizedRole = normalizeRole(role);
    if (window.apiClient?.fetchMemberList) {
      return window.apiClient.fetchMemberList({ auth: true, role: normalizedRole });
    }
    return Promise.resolve(demoMembers.slice());
  }

  function handleMemberFilterChange() {
    state.search = String(refs.search?.value || "").trim();
    state.pageSize = normalizePageSize(refs.pageSize?.value);
    state.page = 1;
    renderMemberBoard();
    saveMemberFilters();
  }

  function handleMemberRoleChange() {
    const nextRole = normalizeRole(refs.role?.value);
    if (nextRole === state.role) {
      handleMemberFilterChange();
      return;
    }
    state.role = nextRole;
    state.page = 1;
    syncMemberControls();
    saveMemberFilters();
    loadMemberList();
  }

  function handleMemberReset() {
    state.search = "";
    state.role = DEFAULT_ROLE;
    state.pageSize = DEFAULT_PAGE_SIZE;
    state.page = 1;
    syncMemberControls();
    saveMemberFilters();
    loadMemberList();
  }

  function handleMemberPrevPage() {
    if (state.page <= 1) return;
    state.page -= 1;
    renderMemberBoard();
    saveMemberFilters();
  }

  function handleMemberNextPage() {
    const totalPages = getMemberPagination().totalPages;
    if (state.page >= totalPages) return;
    state.page += 1;
    renderMemberBoard();
    saveMemberFilters();
  }

  function renderMemberBoard() {
    const filtered = getFilteredMembers();
    const pagination = getMemberPagination(filtered);
    renderMemberSummary(filtered, pagination);
    renderMemberState(filtered, pagination);
    renderMemberGrid(pagination.items);
    renderMemberPagination(filtered, pagination);
  }

  function renderMemberSummary(filtered, pagination) {
    if (!refs.summary) return;
    const roleLabel = getRoleLabel(state.role);
    const leaderCount = filtered.filter((item) => item.role === "leader").length;
    const adminCount = filtered.filter((item) => item.role === "admin").length;
    const sourceLabel = state.source === "api" ? "接口数据" : "演示数据";
    refs.summary.innerHTML = [
      `角色 <strong>${escapeHtml(roleLabel)}</strong>`,
      `结果 <strong>${filtered.length}</strong>`,
      `页码 <strong>${pagination.page}/${pagination.totalPages}</strong>`,
      `领队 / 管理员 <strong>${leaderCount}/${adminCount}</strong>`,
      `来源 <strong>${escapeHtml(sourceLabel)}</strong>`,
    ].map((item) => `<span class="summary-chip">${item}</span>`).join("");
  }

  function renderMemberState(filtered, pagination) {
    if (!refs.state) return;
    if (state.loading) {
      refs.state.className = "member-state is-loading";
      refs.state.innerHTML = '<section class="state-inline"><span class="spinner" aria-hidden="true"></span><h3>加载中</h3></section><p>正在同步成员列表与角色筛选结果。</p>';
      return;
    }
    if (state.error) {
      refs.state.className = "member-state is-error";
      refs.state.innerHTML = `<section class="state-inline"><h3>网络错误</h3></section><p>${escapeHtml(state.error)}</p><button class="btn btn-primary" type="button" data-member-retry>重试加载</button>`;
      refs.state.querySelector("[data-member-retry]")?.addEventListener("click", loadMemberList);
      return;
    }
    if (!filtered.length) {
      refs.state.className = "member-state is-empty";
      refs.state.innerHTML = '<section class="state-inline"><h3>暂无数据</h3></section><p>当前角色与搜索条件下暂无成员，请调整筛选后重试。</p><button class="btn btn-secondary" type="button" data-member-clear-empty>清空筛选</button>';
      refs.state.querySelector("[data-member-clear-empty]")?.addEventListener("click", handleMemberReset);
      return;
    }
    refs.state.className = "member-state is-loaded";
    refs.state.innerHTML = `<section class="state-inline"><h3>成员已同步</h3></section><p>当前展示第 ${pagination.page} 页，共 ${pagination.totalPages} 页；角色筛选在搜索、翻页与资料预览中会持续保留。</p><button class="btn btn-secondary" type="button" data-member-refresh>刷新列表</button>`;
    refs.state.querySelector("[data-member-refresh]")?.addEventListener("click", loadMemberList);
  }

  function renderMemberGrid(items) {
    if (!refs.grid) return;
    if (!items.length) {
      refs.grid.innerHTML = '<article class="member-empty"><h3>暂无数据</h3><p>请修改角色筛选或搜索关键词后重试。</p></article>';
      return;
    }
    refs.grid.innerHTML = items.map(renderMemberCard).join("");
    refs.grid.querySelectorAll("[data-member-card-action]").forEach((button) => {
      button.addEventListener("click", handleMemberCardAction);
    });
  }

  function renderMemberCard(member) {
    return `
      <article class="member-card">
        <header class="member-card__head">
          <section>
            <p class="task-meta">成员 #${escapeHtml(String(member.id))}</p>
            <h3>${escapeHtml(member.name || "未命名成员")}</h3>
            <p>${escapeHtml(member.training_goal || "暂无训练目标")}</p>
          </section>
          <span class="member-role-badge" data-role="${escapeHtml(member.role)}">${escapeHtml(getRoleLabel(member.role))}</span>
        </header>
        <dl class="member-meta">
          <div><dt>手机号</dt><dd>${escapeHtml(member.phone || "未填写")}</dd></div>
          <div><dt>跑龄</dt><dd>${escapeHtml(formatYears(member.running_years))}</dd></div>
          <div><dt>常规距离</dt><dd>${escapeHtml(formatDistance(member.usual_distance_km))}</dd></div>
          <div><dt>配速</dt><dd>${escapeHtml(member.pace || "未填写")}</dd></div>
        </dl>
        <nav class="member-card__actions" aria-label="成员卡片操作">
          <button class="btn btn-secondary" type="button" data-member-card-action="preview" data-member-id="${escapeHtml(String(member.id))}">查看资料</button>
          <button class="btn btn-secondary" type="button" data-member-card-action="role" data-member-role="${escapeHtml(member.role)}" disabled>${escapeHtml(getRoleActionLabel(member.role))}</button>
        </nav>
      </article>
    `;
  }

  function handleMemberCardAction(event) {
    const memberId = String(event.currentTarget?.dataset.memberId || "");
    if (!memberId || !refs.state) return;
    const member = state.members.find((item) => String(item.id) === memberId);
    if (!member) return;
    refs.state.className = "member-state is-loaded";
    refs.state.innerHTML = `<section class="state-inline"><h3>资料预览</h3></section><p>已聚焦 ${escapeHtml(member.name)}，当前角色为 ${escapeHtml(getRoleLabel(member.role))}；筛选状态已保留，可继续搜索或翻页查看其他成员。</p><button class="btn btn-secondary" type="button" data-member-refresh>返回列表状态</button>`;
    refs.state.querySelector("[data-member-refresh]")?.addEventListener("click", () => renderMemberState(getFilteredMembers(), getMemberPagination()));
  }

  function renderMemberPagination(filtered, pagination) {
    if (refs.paginationInfo) {
      refs.paginationInfo.textContent = filtered.length ? `第 ${pagination.page} 页，共 ${pagination.totalPages} 页 · 当前显示 ${pagination.items.length} / ${filtered.length} 人` : "第 1 页，共 1 页";
    }
    if (refs.prev) refs.prev.disabled = state.loading || pagination.page <= 1 || !filtered.length;
    if (refs.next) refs.next.disabled = state.loading || pagination.page >= pagination.totalPages || !filtered.length;
    if (refs.reset) refs.reset.disabled = state.loading;
    if (refs.search) refs.search.disabled = state.loading;
    if (refs.role) refs.role.disabled = state.loading;
    if (refs.pageSize) refs.pageSize.disabled = state.loading;
  }

  function getFilteredMembers() {
    const keyword = state.search.toLowerCase();
    return state.members.filter((member) => {
      if (state.role !== "all" && member.role !== state.role) return false;
      if (!keyword) return true;
      const searchable = [member.name, member.phone, member.pace, member.training_goal, member.role].map((item) => String(item || "").toLowerCase()).join(" ");
      return searchable.includes(keyword);
    });
  }

  function getMemberPagination(filteredMembers = getFilteredMembers()) {
    const totalItems = filteredMembers.length;
    const totalPages = Math.max(1, Math.ceil(totalItems / state.pageSize));
    const page = Math.min(Math.max(1, state.page), totalPages);
    const start = (page - 1) * state.pageSize;
    return {
      page,
      totalPages,
      items: filteredMembers.slice(start, start + state.pageSize),
    };
  }

  function clampMemberPage() {
    const totalPages = getMemberPagination().totalPages;
    state.page = Math.min(Math.max(1, state.page), totalPages);
  }

  function normalizeRole(value) {
    const role = String(value || DEFAULT_ROLE);
    return ROLE_OPTIONS.includes(role) ? role : DEFAULT_ROLE;
  }

  function normalizePageSize(value) {
    const size = Number(value) || DEFAULT_PAGE_SIZE;
    return [6, 9, 12].includes(size) ? size : DEFAULT_PAGE_SIZE;
  }

  function getRoleLabel(role) {
    return ROLE_LABELS[normalizeRole(role)] || ROLE_LABELS.all;
  }

  function getRoleActionLabel(role) {
    if (role === "leader") return "领队中";
    if (role === "admin") return "管理员中";
    return "普通成员";
  }

  function formatYears(value) {
    const years = Number(value);
    return Number.isFinite(years) ? `${years} 年` : "未填写";
  }

  function formatDistance(value) {
    const distance = Number(value);
    return Number.isFinite(distance) && distance > 0 ? `${distance} km` : "未填写";
  }

  function buildMemberError(error) {
    const status = Number(error?.status || 0);
    if (status === 401 || status === 403) return "未登录或权限不足，已切换为本地演示数据，可稍后重试。";
    return error?.message || "成员接口暂时不可用，已切换为本地演示数据。";
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }
})();
