window.apiClient = (() => {
  "use strict";
     4|     4|     const API_BASE = "/api/v1";
     const ACCESS_KEY_NAMES = ["access_token", "accessToken", "token", "authToken", "workerAccessToken"];
     7|     7|     7|  function readAccessToken() {
    if (typeof localStorage === "undefined") return "";
    for (const key of ACCESS_KEY_NAMES) {
      const value = localStorage.getItem(key);
      if (value && String(value).trim()) {
        return String(value).trim();
      }
    }
    return "";
  }
    18|    18|    18|  function createJsonHeaders({ auth = false, hasBody = false } = {}) {
    const headers = { Accept: "application/json" };
    if (hasBody) {
      headers["Content-Type"] = "application/json";
    }
    if (auth) {
      const token = readAccessToken();
      if (token) {
        headers["X-Access-Key"] = token;
      }
    }
    return headers;
  }
    32|    32|    32|  async function parseJsonResponse(response) {
    const text = await response.text();
    if (!text) return null;
    try {
      return JSON.parse(text);
    } catch {
      return { detail: text };
    }
  }
    42|    42|    42|  function buildApiError(response, payload) {
    const detail = payload?.detail;
    const message = typeof detail === "string" && detail.trim()
      ? detail.trim()
      : (response.status === 401 || response.status === 403 ? "未登录或访问受限" : `HTTP ${response.status}`);
    const error = new Error(message);
    error.status = response.status;
    error.payload = payload;
    return error;
  }
    53|    53|    53|  async function fetchJson(path, { auth = false, method = "GET", body } = {}) {
    const response = await fetch(`${API_BASE}${path}`, {
      method,
      headers: createJsonHeaders({ auth, hasBody: body !== undefined }),
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const payload = await parseJsonResponse(response);
    if (!response.ok) {
      throw buildApiError(response, payload);
    }
    return payload;
  }
    66|    66|    66|  function normalizeTaskQueue(payload) {
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
    80|    80|    80|  function normalizeWorkerDirectory(payload) {
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
    94|    94|    94|  function normalizeMemberList(payload) {
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
   109|   109|   109|  function normalizeMemberRole(role) {
    const value = String(role || "member").toLowerCase();
    return ["member", "leader", "admin"].includes(value) ? value : "member";
  }
   114|   114|   114|  async function fetchMemberList({ auth = false, role = "all" } = {}) {
    const query = role && role !== "all" ? `?role=${encodeURIComponent(role)}` : "";
    const payload = await fetchJson(`/members${query}`, { auth });
    return normalizeMemberList(payload);
  }
   120|   120|   120|  async function fetchTaskQueue({ auth = false } = {}) {
    const payload = await fetchJson("/workspaces/task-queue/tasks", { auth });
    return normalizeTaskQueue(payload);
  }
   125|   125|   125|  async function fetchWorkerDirectory({ auth = false } = {}) {
    const payload = await fetchJson("/workspaces/task-queue/workers", { auth });
    return normalizeWorkerDirectory(payload);
  }
   130|   130|   130|  async function dispatchCreativeIdea(idea, { auth = true } = {}) {
    return fetchJson("/workspaces/task-queue/dispatch", {
      auth,
      method: "POST",
      body: idea,
    });
  }
   138|   138|   138|  return {
    readAccessToken,
    createJsonHeaders,
    fetchJson,
    fetchTaskQueue,
    fetchWorkerDirectory,
    fetchMemberList,
    fetchLeaderboard,
    dispatchCreativeIdea,
    normalizeTaskQueue,
    normalizeWorkerDirectory,
    normalizeMemberList,
    normalizeLeaderboardList,
  };
})();
   152|
export async function fetchMembersByRole(role) {
  const query = role ? `?role=${encodeURIComponent(role)}` : "";
  return fetchJson(`/api/v1/members${query}`);
}
export async function fetchActivityPhotos(activityId) {
  return fetchJson(`/api/v1/activities/${activityId}/photos`);
}
export async function uploadActivityPhotos(activityId, files) {
  const formData = new FormData();
  files.forEach((file) => {
    formData.append('photos', file);
  });
  const response = await fetch(`/api/v1/activities/${activityId}/photos`, {
    method: 'POST',
    body: formData,
  });
  if (!response.ok) {
    let message = '上传失败，请稍后重试';
    try {
      const data = await response.json();
      message = data?.message || data?.detail || message;
    } catch (error) {
      message = message;
    }
    throw new Error(message);
  }
  return response.json();
}
