     1|window.apiClient = (() => {
     2|  "use strict";
     3|
     4|  const API_BASE = "/api/v1";
     5|  const AUTH_TOKEN_KEYS = ["access_token", "accessToken", "token", "authToken", "workerAccessToken"];
     6|
     7|  function readAccessToken() {
     8|    if (typeof localStorage === "undefined") return "";
     9|    for (const key of AUTH_TOKEN_KEYS) {
    10|      const value = localStorage.getItem(key);
    11|      if (value && String(value).trim()) {
    12|        return String(value).trim();
    13|      }
    14|    }
    15|    return "";
    16|  }
    17|
    18|  function createJsonHeaders({ auth = false, hasBody = false } = {}) {
    19|    const headers = { Accept: "application/json" };
    20|    if (hasBody) {
    21|      headers["Content-Type"] = "application/json";
    22|    }
    23|    if (auth) {
    24|      const token = readAccessToken();
    25|      if (token) {
    26|        headers.Authorization = `Bearer ${token}`;
    27|      }
    28|    }
    29|    return headers;
    30|  }
    31|
    32|  async function parseJsonResponse(response) {
    33|    const text = await response.text();
    34|    if (!text) return null;
    35|    try {
    36|      return JSON.parse(text);
    37|    } catch {
    38|      return { detail: text };
    39|    }
    40|  }
    41|
    42|  function buildApiError(response, payload) {
    43|    const detail = payload?.detail;
    44|    const message = typeof detail === "string" && detail.trim()
    45|      ? detail.trim()
    46|      : (response.status === 401 || response.status === 403 ? "未登录或权限不足" : `HTTP ${response.status}`);
    47|    const error = new Error(message);
    48|    error.status = response.status;
    49|    error.payload = payload;
    50|    return error;
    51|  }
    52|
    53|  async function fetchJson(path, { auth = false, method = "GET", body } = {}) {
    54|    const response = await fetch(`${API_BASE}${path}`, {
    55|      method,
    56|      headers: createJsonHeaders({ auth, hasBody: body !== undefined }),
    57|      body: body === undefined ? undefined : JSON.stringify(body),
    58|    });
    59|    const payload = await parseJsonResponse(response);
    60|    if (!response.ok) {
    61|      throw buildApiError(response, payload);
    62|    }
    63|    return payload;
    64|  }
    65|
    66|  function normalizeTaskQueue(payload) {
    67|    const list = Array.isArray(payload) ? payload : payload?.data || payload?.tasks || payload?.items || [];
    68|    return list.map((item, index) => ({
    69|      id: item.id || item.task_id || `task-${index + 1}`,
    70|      title: item.title || item.name || `待处理任务 ${index + 1}`,
    71|      summary: item.summary || item.description || item.detail || "待补充说明",
    72|      assignee: item.assignee || item.owner || "未分配",
    73|      status: item.status || item.state || "todo",
    74|      priority: item.priority || item.priority_level || item.rank || "normal",
    75|      workspace: item.workspace || item.workspace_kind || "dir",
    76|      updatedAt: item.updated_at || item.updatedAt || item.updated || "",
    77|    }));
    78|  }
    79|
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

    function normalizeMemberList(payload) {
      const list = Array.isArray(payload) ? payload : payload?.data || payload?.members || payload?.items || [];
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

    async function fetchMemberList({ auth = false, role = "all" } = {}) {
      const query = role && role !== "all" ? `?role=${encodeURIComponent(role)}` : "";
      const payload = await fetchJson(`/members${query}`, { auth });
      return normalizeMemberList(payload);
    }

    94|  async function fetchTaskQueue({ auth = false } = {}) {
    95|    const payload = await fetchJson("/workspaces/task-queue/tasks", { auth });
    96|    return normalizeTaskQueue(payload);
    97|  }
    98|
    99|  async function fetchWorkerDirectory({ auth = false } = {}) {
   100|    const payload = await fetchJson("/workspaces/task-queue/workers", { auth });
   101|    return normalizeWorkerDirectory(payload);
   102|  }
   103|
   104|  async function dispatchCreativeIdea(idea, { auth = true } = {}) {
   105|    return fetchJson("/workspaces/task-queue/dispatch", {
   106|      auth,
   107|      method: "POST",
   108|      body: idea,
   109|    });
   110|  }
   111|
   return {
     readAccessToken,
     createJsonHeaders,
     fetchJson,
     fetchTaskQueue,
     fetchWorkerDirectory,
     fetchMemberList,
     dispatchCreativeIdea,
     normalizeTaskQueue,
     normalizeWorkerDirectory,
     normalizeMemberList,
   };

   123|