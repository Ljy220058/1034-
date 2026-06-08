     1|window.apiClient = (() => {
     2|  "use strict";
     3|     4|     4|     const API_BASE = "/api/v1";
     4|     const ACCESS_KEY_NAMES = ["access_token", "accessToken", "token", "authToken", "workerAccessToken"];
     5|     7|     7|     7|  function readAccessToken() {
     6|    if (typeof localStorage === "undefined") return "";
     7|    for (const key of ACCESS_KEY_NAMES) {
     8|      const value = localStorage.getItem(key);
     9|      if (value && String(value).trim()) {
    10|        return String(value).trim();
    11|      }
    12|    }
    13|    return "";
    14|  }
    15|    18|    18|    18|  function createJsonHeaders({ auth = false, hasBody = false } = {}) {
    16|    const headers = { Accept: "application/json" };
    17|    if (hasBody) {
    18|      headers["Content-Type"] = "application/json";
    19|    }
    20|    if (auth) {
    21|      const token = readAccessToken();
    22|      if (token) {
    23|        headers["X-Access-Key"] = token;
    24|      }
    25|    }
    26|    return headers;
    27|  }
    28|    32|    32|    32|  async function parseJsonResponse(response) {
    29|    const text = await response.text();
    30|    if (!text) return null;
    31|    try {
    32|      return JSON.parse(text);
    33|    } catch {
    34|      return { detail: text };
    35|    }
    36|  }
    37|    42|    42|    42|  function buildApiError(response, payload) {
    38|    const detail = payload?.detail;
    39|    const message = typeof detail === "string" && detail.trim()
    40|      ? detail.trim()
    41|      : (response.status === 401 || response.status === 403 ? "未登录或访问受限" : `HTTP ${response.status}`);
    42|    const error = new Error(message);
    43|    error.status = response.status;
    44|    error.payload = payload;
    45|    return error;
    46|  }
    47|    53|    53|    53|  async function fetchJson(path, { auth = false, method = "GET", body } = {}) {
    48|    const response = await fetch(`${API_BASE}${path}`, {
    49|      method,
    50|      headers: createJsonHeaders({ auth, hasBody: body !== undefined }),
    51|      body: body === undefined ? undefined : JSON.stringify(body),
    52|    });
    53|    const payload = await parseJsonResponse(response);
    54|    if (!response.ok) {
    55|      throw buildApiError(response, payload);
    56|    }
    57|    return payload;
    58|  }
    59|    66|    66|    66|  function normalizeTaskQueue(payload) {
    60|    const list = Array.isArray(payload) ? payload : payload?.data || payload?.tasks || payload?.items || [];
    61|    return list.map((item, index) => ({
    62|      id: item.id || item.task_id || `task-${index + 1}`,
    63|      title: item.title || item.name || `待处理任务 ${index + 1}`,
    64|      summary: item.summary || item.description || item.detail || "待补充说明",
    65|      assignee: item.assignee || item.owner || "未分配",
    66|      status: item.status || item.state || "todo",
    67|      priority: item.priority || item.priority_level || item.rank || "normal",
    68|      workspace: item.workspace || item.workspace_kind || "dir",
    69|      updatedAt: item.updated_at || item.updatedAt || item.updated || "",
    70|    }));
    71|  }
    72|    function normalizeWorkerDirectory(payload) {
    73|      const list = Array.isArray(payload) ? payload : payload?.data || payload?.workers || payload?.items || [];
    74|      return list.map((item, index) => ({
    75|        id: item.id || item.profile || item.name || `worker-${index + 1}`,
    76|        name: item.name || item.profile || item.id || `worker-${index + 1}`,
    77|        title: item.title || item.label || item.role || "空闲 worker",
    78|        type: item.type || item.category || item.group || "前端协作",
    79|        status: item.status || item.state || "idle",
    80|        load: Number(item.load ?? item.score ?? 0),
    81|        capability: Array.isArray(item.capability) ? item.capability : (Array.isArray(item.skills) ? item.skills : []),
    82|        bio: item.bio || item.description || "",
    83|      }));
    84|    }
    85|
    86|    function normalizeAchievements(payload) {
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
    87|      const rows = Array.isArray(payload) ? payload : payload?.data || payload?.days || payload?.items || [];
    88|      const summary = payload?.summary || payload?.stats || payload?.meta || {};
    89|      return {
    90|        summary: {
    91|          currentStreak: Number(summary.currentStreak ?? summary.current_streak ?? summary.streak ?? 0),
    92|          maxStreak: Number(summary.maxStreak ?? summary.max_streak ?? summary.longestStreak ?? 0),
    93|          monthDays: Number(summary.monthDays ?? summary.month_days ?? summary.thisMonthDays ?? 0),
    94|        },
    95|        rows: rows.map((item, index) => ({
    96|          date: item.date || item.day || item.record_date || item.checkin_date || `day-${index + 1}`,
    97|          count: Number(item.count ?? item.times ?? item.checkins ?? item.value ?? 0),
    98|          memberId: item.member_id || item.memberId || item.user_id || item.userId || '',
    99|        })),
   100|      };
   101|    }
   102|
   103|    function normalizeMemberList(payload) {
   104|
   105|      id: item.id || item.member_id || `member-${index + 1}`,
   106|      name: item.name || item.nickname || item.username || `成员 ${index + 1}`,
   107|      phone: item.phone || item.mobile || item.tel || "",
   108|      role: normalizeMemberRole(item.role || item.member_role || item.type),
   109|      running_years: Number(item.running_years ?? item.runningYears ?? item.years_of_running ?? item.years) || 0,
   110|      pace: item.pace || item.avg_pace || item.running_pace || "",
   111|      usual_distance_km: Number(item.usual_distance_km ?? item.usualDistanceKm ?? item.distance_km ?? item.distance) || 0,
   112|      training_goal: item.training_goal || item.goal || item.trainingGoal || item.note || "",
   113|      created_at: item.created_at || item.createdAt || item.joined_at || "",
   114|    }));
   115|  }
   116|   109|   109|   109|  function normalizeMemberRole(role) {
   117|    const value = String(role || "member").toLowerCase();
   118|    return ["member", "leader", "admin"].includes(value) ? value : "member";
   119|  }
   120|   114|   114|   114|  async function fetchMemberList({ auth = false, role = "all" } = {}) {
   121|    const query = role && role !== "all" ? `?role=${encodeURIComponent(role)}` : "";
   122|    const payload = await fetchJson(`/members${query}`, { auth });
   123|    return normalizeMemberList(payload);
   124|  }
   125|   120|   120|   120|  async function fetchTaskQueue({ auth = false } = {}) {
   126|    const payload = await fetchJson("/workspaces/task-queue/tasks", { auth });
   127|    return normalizeTaskQueue(payload);
   128|  }
   129|   125|   125|   125|  async function fetchWorkerDirectory({ auth = false } = {}) {
   130|    const payload = await fetchJson("/workspaces/task-queue/workers", { auth });
   131|    return normalizeWorkerDirectory(payload);
   132|  }
   133|   130|   130|   130|  async function dispatchCreativeIdea(idea, { auth = true } = {}) {
   134|    return fetchJson("/workspaces/task-queue/dispatch", {
   135|      auth,
   136|      method: "POST",
   137|      body: idea,
   138|    });
   139|  }
   140|   138|   138|   138|  return {
   141|    readAccessToken,
   142|    createJsonHeaders,
   143|    fetchJson,
   144|    fetchTaskQueue,
   145|    fetchWorkerDirectory,
   146|    fetchMemberList,
   147|    fetchCheckinStats,
   148|    fetchLeaderboard,
   149|    dispatchCreativeIdea,
   150|    normalizeTaskQueue,
   151|    normalizeWorkerDirectory,
   152|    normalizeMemberList,
   153|    normalizeLeaderboardList,
   154|  };
   155|})();
   156|   152|
   157|export async function fetchMembersByRole(role) {
   158|  const query = role ? `?role=${encodeURIComponent(role)}` : "";
   159|  return fetchJson(`/api/v1/members${query}`);
   160|}
   161|export async function fetchActivityPhotos(activityId) {
   162|  return fetchJson(`/api/v1/activities/${activityId}/photos`);
   163|}
   164|export async function uploadActivityPhotos(activityId, files) {
   165|  const formData = new FormData();
   166|  files.forEach((file) => {
   167|    formData.append('photos', file);
   168|  });
   169|  const response = await fetch(`/api/v1/activities/${activityId}/photos`, {
   170|    method: 'POST',
   171|    body: formData,
   172|  });
   173|  if (!response.ok) {
   174|    let message = '上传失败，请稍后重试';
   175|    try {
   176|      const data = await response.json();
   177|      message = data?.message || data?.detail || message;
   178|    } catch (error) {
   179|      message = message;
   180|    }
   181|    throw new Error(message);
   182|  }
   183|  return response.json();
   184|}
   185|