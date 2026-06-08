const 样例列表 = [
  {
    contract_version: "training_review_card.v1",
    training_id: "act_42",
    member_id: 1001,
    plan_goal: {
      goal_text: "完成 10 公里稳步进阶训练",
      target_distance_km: 10.0,
      target_pace_seconds_per_km: 360,
      source: "activity",
    },
    actual_distance_km: 10.24,
    duration_seconds: 3744,
    average_pace_seconds_per_km: 366,
    completion_rate: 1.024,
    completion_status: "completed",
    anomaly_tags: ["无异常"],
    recommendation_text: "本次训练完成度良好，建议下次保持 6 分 05 秒左右配速，并在训练后补充拉伸。",
    data_quality: {
      gps_status: "available",
      distance_source: "gps_track",
      pace_source: "duration_and_distance",
      degraded: false,
      degrade_reason: null,
    },
    generated_at: "2026-06-06T12:00:00Z",
  },
  {
    contract_version: "training_review_card.v1",
    training_id: "act_43",
    member_id: 1002,
    plan_goal: {
      goal_text: "稳定完成 5 公里，建立轻松配速习惯",
      target_distance_km: 5.0,
      target_pace_seconds_per_km: null,
      source: "training_template",
    },
    actual_distance_km: 5.12,
    duration_seconds: 1920,
    average_pace_seconds_per_km: 375,
    completion_rate: 1.024,
    completion_status: "completed",
    anomaly_tags: ["GPS缺失"],
    recommendation_text: "本次距离来自导入文件，缺少 GPS 轨迹。建议下次开启定位记录，以便复盘路线和配速波动。",
    data_quality: {
      gps_status: "missing",
      distance_source: "import_file",
      pace_source: "duration_and_distance",
      degraded: true,
      degrade_reason: "缺少 GPS 轨迹，距离采用导入文件中的汇总距离",
    },
    generated_at: "2026-06-06T12:05:00Z",
  },
  {
    contract_version: "training_review_card.v1",
    training_id: "act_44",
    member_id: 1003,
    plan_goal: {
      goal_text: "完成半马系统备赛中的周末长跑",
      target_distance_km: 18.0,
      target_pace_seconds_per_km: 390,
      source: "training_template",
    },
    actual_distance_km: 7.2,
    duration_seconds: 3120,
    average_pace_seconds_per_km: 433,
    completion_rate: 0.4,
    completion_status: "partial",
    anomaly_tags: ["未完成训练"],
    recommendation_text: "本次完成约 40%，建议先关注恢复和补水；下次可把长距离拆成分段目标，逐步回到计划跑量。",
    data_quality: {
      gps_status: "available",
      distance_source: "gps_track",
      pace_source: "duration_and_distance",
      degraded: false,
      degrade_reason: null,
    },
    generated_at: "2026-06-06T12:10:00Z",
  },
];

const 必填字段 = new Set([
  "contract_version",
  "training_id",
  "member_id",
  "plan_goal",
  "actual_distance_km",
  "duration_seconds",
  "average_pace_seconds_per_km",
  "completion_rate",
  "completion_status",
  "anomaly_tags",
  "recommendation_text",
  "data_quality",
  "generated_at",
]);
const 计划目标必填字段 = new Set(["goal_text", "target_distance_km", "target_pace_seconds_per_km", "source"]);
const 数据质量必填字段 = new Set(["gps_status", "distance_source", "pace_source", "degraded", "degrade_reason"]);
const 完成状态集合 = new Set(["completed", "partial", "not_completed", "unknown"]);
const 计划来源集合 = new Set(["activity", "training_template", "member_profile", "fallback"]);
const GPS状态集合 = new Set(["available", "missing", "empty", "not_required", "unknown"]);
const 距离来源集合 = new Set(["gps_track", "import_file", "manual", "activity_plan", "unknown"]);
const 配速来源集合 = new Set(["duration_and_distance", "import_file", "manual", "unknown"]);

function 断言(条件, 信息) {
  if (!条件) throw new Error(信息);
}

function 数字或空值(值) {
  return 值 === null || (typeof 值 === "number" && Number.isFinite(值));
}

function 整数或空值(值) {
  return 值 === null || Number.isInteger(值);
}

function 校验集合字段(对象, 必填集合, 名称, 序号) {
  const 缺失 = [...必填集合].filter((字段) => !(字段 in 对象));
  断言(缺失.length === 0, `第 ${序号} 条 ${名称} 缺少字段：${缺失.join("、")}`);
}

function 校验复盘卡片(样例, 序号) {
  校验集合字段(样例, 必填字段, "根对象", 序号);
  断言(样例.contract_version === "training_review_card.v1", `第 ${序号} 条版本错误`);
  断言(typeof 样例.training_id === "string" && 样例.training_id.trim().length > 0, `第 ${序号} 条 training_id 无效`);
  断言(Number.isInteger(样例.member_id) && 样例.member_id > 0, `第 ${序号} 条 member_id 无效`);

  const 计划目标 = 样例.plan_goal;
  断言(计划目标 && typeof 计划目标 === "object" && !Array.isArray(计划目标), `第 ${序号} 条 plan_goal 必须是对象`);
  校验集合字段(计划目标, 计划目标必填字段, "plan_goal", 序号);
  断言(typeof 计划目标.goal_text === "string" && 计划目标.goal_text.trim().length > 0, `第 ${序号} 条 goal_text 不能为空`);
  断言(数字或空值(计划目标.target_distance_km), `第 ${序号} 条目标距离类型无效`);
  if (计划目标.target_distance_km !== null) 断言(计划目标.target_distance_km > 0, `第 ${序号} 条目标距离必须大于 0`);
  断言(整数或空值(计划目标.target_pace_seconds_per_km), `第 ${序号} 条目标配速类型无效`);
  if (计划目标.target_pace_seconds_per_km !== null) 断言(计划目标.target_pace_seconds_per_km > 0, `第 ${序号} 条目标配速必须大于 0`);
  断言(计划来源集合.has(计划目标.source), `第 ${序号} 条 plan_goal.source 无效`);

  for (const 字段 of ["actual_distance_km", "completion_rate"]) {
    断言(数字或空值(样例[字段]), `第 ${序号} 条 ${字段} 类型无效`);
    if (样例[字段] !== null) 断言(样例[字段] >= 0, `第 ${序号} 条 ${字段} 不能小于 0`);
  }
  for (const 字段 of ["duration_seconds", "average_pace_seconds_per_km"]) {
    断言(整数或空值(样例[字段]), `第 ${序号} 条 ${字段} 类型无效`);
    if (样例[字段] !== null) 断言(样例[字段] >= 0, `第 ${序号} 条 ${字段} 不能小于 0`);
  }

  断言(完成状态集合.has(样例.completion_status), `第 ${序号} 条 completion_status 无效`);
  断言(Array.isArray(样例.anomaly_tags) && 样例.anomaly_tags.length >= 1, `第 ${序号} 条 anomaly_tags 不能为空`);
  断言(样例.anomaly_tags.every((标签) => typeof 标签 === "string" && 标签.trim().length > 0), `第 ${序号} 条 anomaly_tags 包含空标签`);
  断言(typeof 样例.recommendation_text === "string" && 样例.recommendation_text.trim().length > 0, `第 ${序号} 条 recommendation_text 不能为空`);

  const 数据质量 = 样例.data_quality;
  断言(数据质量 && typeof 数据质量 === "object" && !Array.isArray(数据质量), `第 ${序号} 条 data_quality 必须是对象`);
  校验集合字段(数据质量, 数据质量必填字段, "data_quality", 序号);
  断言(GPS状态集合.has(数据质量.gps_status), `第 ${序号} 条 gps_status 无效`);
  断言(距离来源集合.has(数据质量.distance_source), `第 ${序号} 条 distance_source 无效`);
  断言(配速来源集合.has(数据质量.pace_source), `第 ${序号} 条 pace_source 无效`);
  断言(typeof 数据质量.degraded === "boolean", `第 ${序号} 条 degraded 必须是布尔值`);
  if (数据质量.degrade_reason !== null) {
    断言(typeof 数据质量.degrade_reason === "string" && 数据质量.degrade_reason.trim().length > 0, `第 ${序号} 条 degrade_reason 无效`);
  }

  断言(!Number.isNaN(Date.parse(样例.generated_at)), `第 ${序号} 条 generated_at 不是合法时间`);
}

for (const [索引, 样例] of 样例列表.entries()) {
  校验复盘卡片(样例, 索引 + 1);
}

console.log(`训练复盘样例校验通过：${样例列表.length} 条`);
