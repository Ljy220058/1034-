window.apiClient = (() => {
  "use strict";

  const API_BASE = "/api/v1";
  const ACCESS_KEY_NAMES = ["access_credential", "accessCredential", "credential", "login_verificationCredential", "workerAccessCredential"];

  /**
   * Read the stored access credential from localStorage.
   * @returns {string} Trimmed credential string, or an empty string when unavailable.
   */
  function readAccessCredential() {
    if (typeof localStorage === "undefined") return "";
    for (const key of ACCESS_KEY_NAMES) {
      const value = localStorage.getItem(key);
      if (value && String(value).trim()) {
        return String(value).trim();
      }
    }
    return "";
  }

  /**
   * Create the JSON headers used by frontend API requests.
   * @param {Object} [options={}] - Header toggles for the request.
   * @param {boolean} [options.login_verification=false] - Whether to attach the stored access credential.
   * @param {boolean} [options.hasBody=false] - Whether the request sends a JSON body.
   * @returns {Record<string, string>} Request headers for fetch calls.
   * @description Builds a minimal JSON request header set and conditionally adds the access key.
   */
  function createJsonHeaders({ login_verification = false, hasBody = false } = {}) {
    const headers = { Accept: "application/json" };
    if (hasBody) {
      headers["Content-Type"] = "application/json";
    }
    if (login_verification) {
      const credential = readAccessCredential();
      if (credential) {
        headers["X-Access-Key"] = credential;
      }
    }
    return headers;
  }

  /**
   * Parse a fetch response body into JSON when possible.
   * @param {Response} response - The raw fetch response object.
   * @returns {Promise<object|null>} Parsed JSON payload, fallback detail object, or null for empty responses.
   * @description Reads the body once and gracefully degrades to a detail wrapper when JSON parsing fails.
   */
  async function parseJsonResponse(response) {
    const text = await response.text();
    if (!text) return null;
    try {
      return JSON.parse(text);
    } catch {
      return { detail: text };
    }
  }

  function buildApiError(response, payload) {
    const detail = payload?.detail;
    const message = typeof detail === "string" && detail.trim()
      ? detail.trim()
      : (response.status === 401 || response.status === 403 ? "未登录或访问受限" : `HTTP ${response.status}`);
    const error = new Error(message);
    error.status = response.status;
    error.payload = payload;
    return error;
  }

  async function fetchJson(path, { login_verification = false, method = "GET", body } = {}) {
    const response = await fetch(`${API_BASE}${path}`, {
      method,
      headers: createJsonHeaders({ login_verification, hasBody: body !== undefined }),
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const payload = await parseJsonResponse(response);
    if (!response.ok) {
      throw buildApiError(response, payload);
    }
    return payload;
  }

  function normalizeTaskQueue(payload) {
    const list = Array.isArray(payload) ? payload : payload?.data || payload?.tasks || payload?.items || [];
    return list.map((item, index) => ({
      id: item.id || item.task_id || `task-${index + 1}`,
      title: item.title || item.name || `待处理任务 ${index + 1}`,
      summary: item.summary || item.description || item.detail || "待补充说明",
      assignee: item.assignee || item.owner || "未分配",
      status: item.status || item.state || "todo",
      priority: item.priority || item.priority_level || item.rank || "normal",
      workspace: item.workspace || item.workspace_kind || "dir",
      updatedAt: item.updated_at || item.updatedAt || item.updated || "",
    }));
  }

  function normalizeWorkerDirectory(payload) {
    const list = Array.isArray(payload) ? payload : payload?.data || payload?.workers || payload?.items || [];
    return list.map((item, index) => ({
      id: item.id || item.profile || item.name || `worker-${index + 1}`,
      name: item.name || item.profile || item.id || `worker-${index + 1}`,
      title: item.title || item.label || item.role || "空闲 worker",
      type: item.type || item.category || item.group || "前端协作",
      status: item.status || item.state || "idle",
      load: Number(item.load ?? item.score ?? 0),
      capability: Array.isArray(item.capability) ? item.capability : (Array.isArray(item.skills) ? item.skills : []),
      bio: item.bio || item.description || "",
    }));
  }

  function normalizeAchievements(payload) {
    const source = payload?.data || payload || {};
    const list = Array.isArray(source.badges) ? source.badges : Array.isArray(source.items) ? source.items : [];
    return {
      averagePace: source.average_pace || source.averagePace || source.avg_pace || "",
      badges: list.map((item, index) => ({
        id: item.id || item.badge_id || `badge-${index + 1}`,
        name: item.name || item.title || `成就徽章 ${index + 1}`,
        description: item.description || item.detail || "持续训练，解锁更多跑步成就。",
        earned: Boolean(item.earned ?? item.unlocked ?? item.is_earned ?? item.obtained_at || item.earned_at),
        icon: item.icon || "🏅",
        obtainedAt: item.obtained_at || item.earned_at || item.unlocked_at || "",
        current: Number(item.current ?? item.progress_value ?? item.value ?? item.completed ?? 0),
        target: Number(item.target ?? item.goal ?? item.total ?? 0),
      })),
    };
  }

  function normalizeCheckinStats(payload) {
    const rows = Array.isArray(payload) ? payload : payload?.data || payload?.days || payload?.items || [];
    const summary = payload?.summary || payload?.stats || payload?.meta || {};
    return {
      summary: {
        currentStreak: Number(summary.currentStreak ?? summary.current_streak ?? summary.streak ?? 0),
        maxStreak: Number(summary.maxStreak ?? summary.max_streak ?? summary.longestStreak ?? 0),
        monthDays: Number(summary.monthDays ?? summary.month_days ?? summary.thisMonthDays ?? 0),
      },
      rows: rows.map((item, index) => ({
        date: item.date || item.day || item.record_date || item.checkin_date || `day-${index + 1}`,
        count: Number(item.count ?? item.times ?? item.checkins ?? item.value ?? 0),
        memberId: item.member_id || item.memberId || item.user_id || item.userId || "",
      })),
    };
  }

  function normalizeMemberList(payload) {
    const list = Array.isArray(payload) ? payload : payload?.data || payload?.items || payload?.members || [];
    return list.map((item, index) => ({
      id: item.id || item.member_id || `member-${index + 1}`,
      name: item.name || item.nickname || item.username || `成员 ${index + 1}`,
      phone: item.phone || item.mobile || item.tel || "",
      role: normalizeMemberRole(item.role || item.member_role || item.type),
      running_years: Number(item.running_years ?? item.runningYears ?? item.years_of_running ?? item.years) || 0,
      pace: item.pace || item.avg_pace || item.running_pace || "",
      usual_distance_km: Number(item.usual_distance_km ?? item.usualDistanceKm ?? item.distance_km ?? item.distance) || 0,
      training_goal: item.training_goal || item.goal || item.trainingGoal || item.note || "",
      created_at: item.created_at || item.createdAt || item.joined_at || "",
    }));
  }

  function normalizeMemberRole(role) {
    const value = String(role || "member").toLowerCase();
    return ["member", "leader", "admin"].includes(value) ? value : "member";
  }

  async function fetchMemberList({ login_verification = false, role = "all" } = {}) {
    const query = role && role !== "all" ? `?role=${encodeURIComponent(role)}` : "";
    const payload = await fetchJson(`/members${query}`, { login_verification });
    return normalizeMemberList(payload);
  }

  async function fetchTaskQueue({ login_verification = false } = {}) {
    const payload = await fetchJson("/workspaces/task-queue/tasks", { login_verification });
    return normalizeTaskQueue(payload);
  }

  async function fetchWorkerDirectory({ login_verification = false } = {}) {
    const payload = await fetchJson("/workspaces/task-queue/workers", { login_verification });
    return normalizeWorkerDirectory(payload);
  }

  async function fetchTeamChallengeOverview({ login_verification = false } = {}) {
    const payload = await fetchJson("/workspaces/team-challenge/overview", { login_verification });
    return payload?.data || payload || {};
  }

  async function dispatchCreativeIdea(idea, { login_verification = true } = {}) {
    return fetchJson("/workspaces/task-queue/dispatch", {
      login_verification,
      method: "POST",
      body: idea,
    });
  }

  async function fetchOnboardingBuddies({ login_verification = false } = {}) {
    const payload = await fetchJson("/members?role=member", { login_verification });
    const list = Array.isArray(payload) ? payload : payload?.data || payload?.items || payload?.members || [];
    return list.map((item, index) => ({
      id: item.id || item.member_id || `buddy-${index + 1}`,
      name: item.name || item.nickname || `成员 ${index + 1}`,
      pace: item.pace || item.avg_pace || "--",
      mileage: item.mileage || item.total_distance || item.usual_distance_km || 0,
    }));
  }

  async function fetchOnboardingChecklist({ login_verification = false } = {}) {
    const payload = await fetchJson("/members/onboarding-checklist", { login_verification });
    const list = Array.isArray(payload) ? payload : payload?.data || payload?.items || [];
    return list.map((item, index) => ({
      id: item.id || item.check_id || `check-${index + 1}`,
      label: item.label || item.title || item.name || `待办事项 ${index + 1}`,
      done: Boolean(item.done ?? item.completed ?? item.checked),
    }));
  }

  async function updateOnboardingChecklistItem(checkId, done, { login_verification = false } = {}) {
    return fetchJson(`/members/onboarding-checklist/${encodeURIComponent(checkId)}`, {
      login_verification,
      method: "PATCH",
      body: { done: Boolean(done) },
    });
  }

  async function completeOnboarding({ login_verification = false } = {}) {
    return fetchJson("/members/onboarding/complete", {
      login_verification,
      method: "POST",
    });
  }

  async function fetchOnboardingOverview({ login_verification = false } = {}) {
    const payload = await fetchJson("/members/onboarding", { login_verification });
    return payload?.data || payload || {};
  }

  return {
    readAccessCredential,
    createJsonHeaders,
    fetchJson,
    fetchTaskQueue,
    fetchWorkerDirectory,
    fetchTeamChallengeOverview,
    fetchMemberList,
    fetchOnboardingBuddies,
    fetchOnboardingChecklist,
    updateOnboardingChecklistItem,
    completeOnboarding,
    fetchOnboardingOverview,
    normalizeTaskQueue,
    normalizeWorkerDirectory,
    normalizeAchievements,
    normalizeCheckinStats,
    normalizeMemberList,
    dispatchCreativeIdea,
  };
})();
