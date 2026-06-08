# 活动参与率异常波动数据模型说明

日期：2026-06-06
任务：t_127bea78

## 1. 现有活动、报名、签到字段梳理

### activities
- id：活动主键。
- title：活动标题，用于看板展示。
- start_time：活动开始时间；参与率按 date(start_time) 落到 metric_date。
- location / route / distance_km / pace_group / description：活动维度说明字段，可用于后续按路线、配速组扩展分析。
- created_at / updated_at：审计时间。

### registrations
- id：报名主键。
- activity_id：活动外键，关联 activities(id)。
- member_id：成员外键，关联 members(id)。
- status：报名状态，registered/cancelled；参与率分母默认使用 registered，cancelled 单独计数。
- created_at：报名时间，可用于报名提前量、报名趋势扩展分析。
- UNIQUE(activity_id, member_id)：数据库层防重复报名。

### attendances
- id：签到主键。
- activity_id：活动外键，关联 activities(id)。
- member_id：成员外键，关联 members(id)。
- status：签到状态，signed_in/absent；signed_in 计入参与率分子，absent 计入缺席数。
- signed_in_at：签到/缺席记录时间。
- gps_checked：是否 GPS 校验签到。
- created_at / updated_at：审计时间。
- UNIQUE(activity_id, member_id)：数据库层防重复签到。

## 2. 新增模型设计

### member_groups
成员分组维表，用于按新人组、进阶组、领队组等维度分析参与率。

字段：
- id：主键。
- group_key：稳定业务键，唯一约束 uq_member_groups_group_key。
- name：展示名称。
- description：分组说明。
- is_active：是否启用。
- created_at / updated_at：审计时间。

### member_group_memberships
成员分组关系表。用 valid_from/valid_to 支持成员跨时间段归属变化，避免历史指标因分组调整失真。

字段：
- id：主键。
- group_id：成员分组外键，ON DELETE CASCADE。
- member_id：成员外键，ON DELETE CASCADE。
- valid_from：归属开始日期。
- valid_to：归属结束日期，可为空。
- created_at / updated_at：审计时间。
- uq_member_group_memberships_group_member_from：同一成员同一分组同一生效日期唯一。

### activity_participation_anomaly_thresholds
异常波动阈值表。支持 global、activity、member_group 三种作用域。

字段：
- scope_type：global/activity/member_group。
- activity_id：activity 作用域对应活动外键。
- group_id：member_group 作用域对应分组外键。
- baseline_window_days：基线窗口天数。
- min_sample_activities：计算基线所需最少历史活动数。
- warning_drop_pp：预警级参与率下降百分点。
- critical_drop_pp：严重级参与率下降百分点。
- warning_z_score：预警级 z-score 阈值。
- critical_z_score：严重级 z-score 阈值。
- min_participation_rate：最低可接受参与率。
- is_active：阈值是否启用。
- created_at / updated_at：审计时间。

判定建议：
- 样本活动数 < min_sample_activities：anomaly_level = insufficient_data。
- rate_delta_pp <= -critical_drop_pp 或 z_score <= critical_z_score 或 participation_rate < min_participation_rate：critical。
- rate_delta_pp <= -warning_drop_pp 或 z_score <= warning_z_score：warning。
- 否则 normal。

### activity_participation_daily_metrics
参与率指标事实表，面向看板和告警读取。粒度为 activity_id + metric_date + group_id；group_id 为 NULL 表示活动整体。

字段：
- activity_id：活动外键。
- metric_date：指标日期，来自 date(activities.start_time)。
- group_id：成员分组外键；NULL 表示整体。
- registered_count：有效报名人数。
- signed_in_count：签到人数。
- absent_count：缺席人数。
- cancelled_count：取消报名人数。
- participation_rate：signed_in_count / registered_count，0 到 1。
- baseline_participation_rate：基线参与率。
- rate_delta_pp：当前参与率相对基线变化，单位百分点。
- z_score：相对历史波动的标准分。
- anomaly_level：normal/warning/critical/insufficient_data。
- threshold_id：本次判定使用的阈值外键。
- calculated_at：指标计算时间。
- created_at / updated_at：审计时间。

### activity_participation_metric_inputs
指标输入视图，合并活动、报名、签到和成员分组关系：
- group_id = NULL 的记录用于活动整体聚合。
- group_id 非 NULL 的记录用于成员分组聚合。
- 后端可按 activity_id、metric_date、group_id GROUP BY 后写入 activity_participation_daily_metrics。

## 3. 索引覆盖

- idx_member_group_memberships_group：按分组查成员。
- idx_member_group_memberships_member：按成员查分组。
- idx_activity_participation_thresholds_scope：按作用域查启用阈值。
- idx_activity_participation_thresholds_activity：按活动查阈值。
- idx_activity_participation_thresholds_group：按成员分组查阈值。
- idx_activity_participation_metrics_activity_date：活动详情页按活动查看指标趋势。
- idx_activity_participation_metrics_date_group：看板按日期范围和分组筛选指标。
- idx_activity_participation_metrics_group_date：分组详情页按分组查看趋势。
- idx_activity_participation_metrics_anomaly：告警列表按异常等级和日期排序。
- idx_activity_participation_metrics_threshold：追踪指标使用的阈值。
- uq_activity_participation_daily_metrics_activity_date_group：保证同一活动/日期/分组只有一条指标。

## 4. 前后端消费验收说明

后端消费方式：后端定时任务或活动结束后的聚合任务从 activity_participation_metric_inputs 读取明细，按 activity_id、metric_date、group_id 聚合 registered_count、signed_in_count、absent_count、cancelled_count，并根据 activity_participation_anomaly_thresholds 计算 participation_rate、baseline_participation_rate、rate_delta_pp、z_score 和 anomaly_level 后写入 activity_participation_daily_metrics。告警服务只需查询 anomaly_level IN ('warning', 'critical') 的指标行，并读取 threshold_id 解释触发规则。

前端消费方式：活动详情页按 activity_id 读取 activity_participation_daily_metrics 展示整体参与率、报名人数、签到人数、缺席人数和异常等级；运营看板按 metric_date 范围、group_id 和 anomaly_level 筛选趋势图与告警列表；成员分组页按 group_id 展示新人组/进阶组等分组参与率变化。展示时 participation_rate 和 baseline_participation_rate 以百分比显示，rate_delta_pp 直接显示为“较基线下降/上升 N 个百分点”，anomaly_level 映射为正常、预警、严重、样本不足。

## 5. 最小回归验证建议

1. 在临时 SQLite 数据库中执行 backend.database.SCHEMA_SQL（或通过 backend.database.init_db 初始化核心表），再执行 migrations/007_activity_participation_anomaly_model.sql。
2. 执行 scripts/seed_activity_participation_anomalies.sql。
3. 验证 activity_participation_daily_metrics 中存在 normal、warning、critical、insufficient_data 四类 anomaly_level。
4. 使用 EXPLAIN QUERY PLAN 验证以下高频查询命中索引：
   - 按活动查指标：activity_id + metric_date。
   - 按日期范围和分组查看板指标：metric_date + group_id。
   - 按异常等级查告警：anomaly_level + metric_date。
   - 按成员查分组：member_id + group_id。
5. 执行 migrations/007_activity_participation_anomaly_model.rollback.sql，确认新增表和视图被移除，schema_migrations 中版本 7 被删除。
