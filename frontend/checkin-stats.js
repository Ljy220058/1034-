window.checkinStats = (() => {
  "use strict";

  const API_BASE = "/api/v1";

  function createDefaultStats() {
    const today = new Date();
    const monthKey = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}`;
    return {
      monthKey,
      monthLabel: `${today.getFullYear()} 年 ${today.getMonth() + 1} 月`,
      continuousDays: 0,
      attendanceRate: 0,
      totalCheckins: 0,
      activeDays: 0,
      totalDays: 0,
      heatmap: [],
      summary: "正在加载打卡统计",
      updatedAt: "",
      memberName: "当前成员",
      statusText: "待同步",
    };
  }

  function parseDateLabel(value) {
    if (!value) return "未知";
    const text = String(value).trim();
    const date = new Date(text);
    if (Number.isNaN(date.getTime())) return text;
    return `${date.getMonth() + 1}/${date.getDate()}`;
  }

  function normalizeHeatmap(source) {
    if (!Array.isArray(source)) return [];
    return source.map((item, index) => {
      const intensity = Number(item.intensity ?? item.value ?? item.count ?? 0);
      const level = Number.isFinite(intensity) ? Math.max(0, Math.min(4, Math.round(intensity))) : 0;
      return {
        date: item.date || item.day || item.checkin_date || `day-${index + 1}`,
        label: item.label || parseDateLabel(item.date || item.day || item.checkin_date),
        count: Number(item.count ?? item.times ?? item.value ?? 0) || 0,
        level,
      };
    });
  }

  function normalizeStats(payload) {
    const today = new Date();
    const defaultStats = createDefaultStats();
    if (!payload) return defaultStats;
    const data = payload.data || payload.stats || payload.result || payload;
    const monthValue = data.month || data.monthKey || data.month_key || defaultStats.monthKey;
    const date = new Date(`${monthValue}-01`);
    const validDate = Number.isNaN(date.getTime()) ? today : date;
    const attendanceRate = Number(data.attendance_rate ?? data.attendanceRate ?? data.rate ?? 0) || 0;
    return {
      monthKey: monthValue,
      monthLabel: data.monthLabel || `${validDate.getFullYear()} 年 ${validDate.getMonth() + 1} 月`,
      continuousDays: Number(data.continuous_days ?? data.continuousDays ?? data.streak ?? 0) || 0,
      attendanceRate: attendanceRate > 1 ? attendanceRate : attendanceRate * 100,
      totalCheckins: Number(data.total_checkins ?? data.totalCheckins ?? data.checkins ?? 0) || 0,
      activeDays: Number(data.active_days ?? data.activeDays ?? data.days ?? 0) || 0,
      totalDays: Number(data.total_days ?? data.totalDays ?? data.month_days ?? 0) || 0,
      heatmap: normalizeHeatmap(data.heatmap || data.calendar || data.month_calendar || []),
      summary: data.summary || data.message || "打卡统计已同步",
      updatedAt: data.updated_at || data.updatedAt || payload.updated_at || payload.updatedAt || "",
      memberName: data.member_name || data.memberName || data.user_name || data.username || "当前成员",
      statusText: data.status_text || data.statusText || data.status || "正常",
    };
  }

  async function fetchCheckinStats({ memberId = "", month = "", login_verification = false } = {}) {
    const params = new URLSearchParams();
    if (memberId) params.set("member_id", memberId);
    if (month) params.set("month", month);
    const query = params.toString() ? `?${params.toString()}` : "";
    const response = await fetch(`${API_BASE}/checkins/stats${query}`, {
      headers: login_verification ? { "Accept": "application/json" } : { "Accept": "application/json" },
    });
    const payload = await response.json().catch(() => null);
    if (!response.ok) {
      const detail = payload?.detail || payload?.message || `HTTP ${response.status}`;
      const error = new Error(detail);
      error.status = response.status;
      error.payload = payload;
      throw error;
    }
    return normalizeStats(payload);
  }

  function buildHeatmapGrid(heatmap) {
    const days = heatmap.length ? heatmap : Array.from({ length: 28 }, (_, index) => ({
      label: String(index + 1),
      count: 0,
      level: 0,
    }));
    return days.map((day) => ({
      label: day.label,
      count: day.count,
      level: day.level,
      ariaLabel: `${day.label}，${day.count} 次打卡`,
    }));
  }

  return {
    createDefaultStats,
    normalizeStats,
    normalizeHeatmap,
    fetchCheckinStats,
    buildHeatmapGrid,
  };
})();
