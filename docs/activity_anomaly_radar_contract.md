# 活动数据异常趋势雷达图数据契约

日期：2026-06-06
对应迁移：`migrations/20260606_activity_anomaly_radar_trends.sql`
回滚脚本：`migrations/20260606_rollback_activity_anomaly_radar_trends.sql`

## 设计目标

为跑团系统提供“活动数据异常趋势雷达图”的持久化模型和前端输出契约，帮助运营快速发现：

- 配速突变
- 距离异常
- 重复上传
- GPS 点过少
- 来源平台异常

本模型不重复实现正在运行的数据质量评分任务。已有 `activity_data_quality_scores` 继续负责质量评分原始输入、总分、扣分原因；本模型只保存雷达图趋势快照与维度数组，作为前端可视化契约和跨活动趋势分析入口。

## ERD 摘要

- `activities` 1 -- N `activity_data_quality_scores`
- `activities` 1 -- N `activity_anomaly_radar_snapshots`
- `activity_data_quality_scores` 1 -- N `activity_anomaly_radar_snapshots`（可选引用，质量评分删除时雷达快照保留，`quality_score_id` 置空）
- `activity_anomaly_radar_snapshots` 1 -- N `activity_anomaly_radar_dimensions`

## 表存在理由

### activity_anomaly_radar_snapshots

活动级雷达图快照。保存活动、版本、来源平台、趋势总分、趋势等级、基线窗口和前端 payload 缓存。

存在理由：同一活动可能按不同雷达版本重新计算；快照层用于固定一次可解释的雷达图结果，并让前端无需重新拼装维度即可读取缓存 payload。

### activity_anomaly_radar_dimensions

雷达图维度数组明细。每条记录是一根雷达轴，包含维度键、中文标签、0-100 分值、严重度、趋势方向、基线值和观测值。

存在理由：维度是结构化、可排序、可索引的可视化合同，不应塞进单个 JSON 字段；同时保留 `radar_payload_json` 作为前端缓存，属于受控反范式。

## 评分语义

所有维度 `score` 均为 0-100，含义统一为“异常风险分”：

- 0-20：normal，基本正常
- 21-50：watch，需要关注
- 51-80：warning，明显异常
- 81-100：critical，高风险异常

`snapshots.anomaly_trend_score` 建议由维度分加权得出，也保持 0-100。权重不写死在 schema，便于后续模型版本升级。

## 前端雷达图输出契约

建议 repository/API 读取 `activity_anomaly_radar_snapshots` + `activity_anomaly_radar_dimensions` 后输出以下结构：

```json
{
  "activity_id": 101,
  "radar_version": "activity-anomaly-radar-v1",
  "source_platform": "garmin",
  "anomaly_trend_score": 68,
  "trend_level": "warning",
  "baseline_window_days": 30,
  "assessed_at": "2026-06-06T19:30:00Z",
  "dimensions": [
    {"key": "pace_shift", "label": "配速突变", "score": 72, "severity": "warning", "trend": "up"},
    {"key": "distance_outlier", "label": "距离异常", "score": 35, "severity": "watch", "trend": "flat"},
    {"key": "duplicate_upload", "label": "重复上传", "score": 12, "severity": "normal", "trend": "down"},
    {"key": "gps_sparse", "label": "GPS点过少", "score": 58, "severity": "warning", "trend": "up"},
    {"key": "source_platform", "label": "来源平台异常", "score": 44, "severity": "watch", "trend": "flat"}
  ]
}
```

固定维度键与中文标签：

| dimension_key | label_zh | 说明 |
| --- | --- | --- |
| `pace_shift` | 配速突变 | 当前活动配速相对成员/团体近 30 天基线的偏离风险 |
| `distance_outlier` | 距离异常 | 当前距离相对历史活动、报名活动距离或导入距离分布的偏离风险 |
| `duplicate_upload` | 重复上传 | 同标题、同开始时间、同距离或来源记录重复的风险 |
| `gps_sparse` | GPS点过少 | GPS 点数量不足以支撑轨迹可信度的风险 |
| `source_platform` | 来源平台异常 | 来源平台不常见、字段缺失率高或来源记录 ID 异常的风险 |

## 样例活动输出

### 样例 1：晨跑配速突增且 GPS 稀疏

```json
{
  "activity_id": 101,
  "title": "西湖晨跑",
  "radar_version": "activity-anomaly-radar-v1",
  "source_platform": "garmin",
  "anomaly_trend_score": 68,
  "trend_level": "warning",
  "baseline_window_days": 30,
  "dimensions": [
    {"key": "pace_shift", "label": "配速突变", "score": 76, "severity": "warning", "trend": "up", "baseline_value": 360, "observed_value": 285, "unit": "sec/km"},
    {"key": "distance_outlier", "label": "距离异常", "score": 28, "severity": "watch", "trend": "flat", "baseline_value": 5.2, "observed_value": 5.0, "unit": "km"},
    {"key": "duplicate_upload", "label": "重复上传", "score": 8, "severity": "normal", "trend": "down"},
    {"key": "gps_sparse", "label": "GPS点过少", "score": 72, "severity": "warning", "trend": "up", "baseline_value": 420, "observed_value": 46, "unit": "points"},
    {"key": "source_platform", "label": "来源平台异常", "score": 18, "severity": "normal", "trend": "flat"}
  ]
}
```

### 样例 2：重复上传风险高

```json
{
  "activity_id": 102,
  "title": "滨江夜跑",
  "radar_version": "activity-anomaly-radar-v1",
  "source_platform": "coros",
  "anomaly_trend_score": 54,
  "trend_level": "warning",
  "baseline_window_days": 30,
  "dimensions": [
    {"key": "pace_shift", "label": "配速突变", "score": 22, "severity": "watch", "trend": "flat"},
    {"key": "distance_outlier", "label": "距离异常", "score": 18, "severity": "normal", "trend": "flat"},
    {"key": "duplicate_upload", "label": "重复上传", "score": 91, "severity": "critical", "trend": "up"},
    {"key": "gps_sparse", "label": "GPS点过少", "score": 15, "severity": "normal", "trend": "down"},
    {"key": "source_platform", "label": "来源平台异常", "score": 25, "severity": "watch", "trend": "flat"}
  ]
}
```

### 样例 3：来源平台和距离同时异常

```json
{
  "activity_id": 103,
  "title": "周末 LSD",
  "radar_version": "activity-anomaly-radar-v1",
  "source_platform": "manual_file",
  "anomaly_trend_score": 82,
  "trend_level": "critical",
  "baseline_window_days": 30,
  "dimensions": [
    {"key": "pace_shift", "label": "配速突变", "score": 47, "severity": "watch", "trend": "up"},
    {"key": "distance_outlier", "label": "距离异常", "score": 88, "severity": "critical", "trend": "up", "baseline_value": 12.0, "observed_value": 42.195, "unit": "km"},
    {"key": "duplicate_upload", "label": "重复上传", "score": 34, "severity": "watch", "trend": "flat"},
    {"key": "gps_sparse", "label": "GPS点过少", "score": 62, "severity": "warning", "trend": "up", "baseline_value": 1200, "observed_value": 155, "unit": "points"},
    {"key": "source_platform", "label": "来源平台异常", "score": 86, "severity": "critical", "trend": "up"}
  ]
}
```

## 高频查询与索引覆盖

- 按活动读取雷达快照：`idx_activity_anomaly_radar_snapshots_activity`
- 由质量评分追踪雷达快照：`idx_activity_anomaly_radar_snapshots_quality_score`
- 按评估时间范围筛选趋势：`idx_activity_anomaly_radar_snapshots_assessed_at`
- 运营看板按等级筛选：`idx_activity_anomaly_radar_snapshots_trend_level`
- 按来源平台定位异常：`idx_activity_anomaly_radar_snapshots_source_platform`
- 读取快照维度数组：`idx_activity_anomaly_radar_dimensions_snapshot_order` 覆盖 `radar_snapshot_id + display_order`
- 查某维度高风险活动：`idx_activity_anomaly_radar_dimensions_key_score`

## 最小验证命令

```bash
python - <<'PY'
import sqlite3
from pathlib import Path
from backend.database import SCHEMA_SQL

root = Path('.')
db = sqlite3.connect(':memory:')
db.executescript(SCHEMA_SQL)
db.executescript((root / 'migrations/20260606_activity_data_quality_scores.sql').read_text())
db.executescript((root / 'migrations/20260606_activity_anomaly_radar_trends.sql').read_text())
print('migration ok')
db.executescript((root / 'migrations/20260606_rollback_activity_anomaly_radar_trends.sql').read_text())
print('rollback ok')
PY
```

推荐额外使用 `EXPLAIN QUERY PLAN` 验证：

- `activity_anomaly_radar_snapshots(activity_id)` 用于按活动查雷达快照
- `activity_anomaly_radar_dimensions(radar_snapshot_id)` 用于按快照查维度数组
- `activity_anomaly_radar_dimensions(dimension_key, score)` 用于按异常维度筛选高风险活动
