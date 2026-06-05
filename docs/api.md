# API 文档

本文档描述当前仓库中已经实现的后端接口。所有对外接口都以 `/api/v1` 为统一前缀，响应体统一包装在 `ApiResponse` 中，核心业务数据都放在 `data` 字段里。

## 1. 通用约定

### 1.1 Base URL

```text
/api/v1
```

### 1.2 请求与响应格式

- 请求体：`application/json`
- 响应体：`application/json`
- 时间字段：ISO 8601 字符串
- 认证方式：`Authorization: Bearer <token>`

### 1.3 通用返回结构

正常返回示例：

```json
{
  "data": {}
}
```

出错时，FastAPI 会返回标准 HTTP 状态码，并在 `detail` 中给出错误原因，例如：

```json
{
  "detail": "forbidden"
}
```

### 1.4 角色说明

系统支持以下角色：

- `member`：普通成员
- `leader`：团长或运营负责人
- `admin`：管理员

除注册接口外，角色提升只能由管理员或团长在后台执行。

## 2. 数据模型

### 2.1 Member

```json
{
  "id": 1,
  "name": "张三",
  "phone": "13800000000",
  "role": "member",
  "running_years": 3,
  "pace": "5'30/km",
  "usual_distance_km": 10,
  "training_goal": "完成半马",
  "created_at": "2026-06-06T08:30:00+08:00",
  "updated_at": "2026-06-06T08:30:00+08:00"
}
```

### 2.2 Announcement

```json
{
  "id": 3,
  "title": "周末活动通知",
  "body": "本周六晨跑照常进行。",
  "status": "published",
  "is_pinned": true,
  "created_at": "2026-06-06T08:30:00+08:00"
}
```

### 2.3 Activity

```json
{
  "id": 10,
  "title": "周六晨跑",
  "start_time": "2026-06-08T07:00:00+08:00",
  "location": "人民公园东门",
  "route": "环湖 5 公里",
  "distance_km": 5,
  "pace_group": "5'30-6'00",
  "description": "适合新老成员一起参加",
  "created_at": "2026-06-06T08:30:00+08:00",
  "updated_at": "2026-06-06T08:30:00+08:00"
}
```

### 2.4 Registration

```json
{
  "id": 88,
  "activity_id": 10,
  "member_id": 1,
  "status": "registered",
  "created_at": "2026-06-06T08:30:00+08:00"
}
```

### 2.5 Attendance

```json
{
  "id": 12,
  "activity_id": 10,
  "member_id": 1,
  "status": "signed_in",
  "signed_in_at": "2026-06-08T06:58:00+08:00",
  "gps_checked": true
}
```

## 3. 认证接口

### 3.1 POST /auth/register

注册新成员并直接返回 token。

请求示例：

```json
{
  "name": "张三",
  "phone": "13800000000",
  "password": "secret123",
  "role": "member",
  "running_years": 3,
  "pace": "5'30/km",
  "usual_distance_km": 10,
  "training_goal": "完成半马"
}
```

返回示例：

```json
{
  "data": {
    "token_type": "Bearer",
    "access_token": "1:member:2026-06-13T08:30:00+00:00",
    "member": {
      "id": 1,
      "name": "张三",
      "phone": "13800000000",
      "role": "member"
    }
  }
}
```

错误：

- `409 Conflict`：手机号已注册
- `403 Forbidden`：尝试注册为非 `member` 角色

### 3.2 POST /auth/login

使用手机号和密码登录。

请求示例：

```json
{
  "phone": "13800000000",
  "password": "secret123"
}
```

返回示例：

```json
{
  "data": {
    "token_type": "Bearer",
    "access_token": "1:member:2026-06-13T08:30:00+00:00",
    "member": {
      "id": 1,
      "name": "张三",
      "phone": "13800000000",
      "role": "member"
    }
  }
}
```

错误：

- `401 Unauthorized`：手机号或密码错误

## 4. 成员接口

### 4.1 GET /members

获取成员列表。仅 `admin` 和 `leader` 可访问。

### 4.2 POST /members

创建成员。仅 `admin` 和 `leader` 可访问，且只能创建 `member` 角色。

请求示例：

```json
{
  "name": "李四",
  "phone": "13900000000",
  "role": "member",
  "running_years": 1,
  "pace": "6'00/km",
  "usual_distance_km": 5,
  "training_goal": "完成首次 5 公里"
}
```

### 4.3 GET /members/me

获取当前登录用户信息。

### 4.4 GET /members/{member_id}

获取单个成员信息。

- `admin` 和 `leader` 可以查看任意成员
- 普通成员只能查看自己的资料

### 4.5 PATCH /members/{member_id}

更新成员信息。

- `admin` 和 `leader` 可以修改任意成员
- 普通成员只能修改自己的资料
- `role` 只能在允许的角色范围内变化

### 4.6 DELETE /members/{member_id}

删除成员。

- 仅 `admin` 和 `leader` 可访问
- 只能删除普通成员，不能删除管理员或团长

## 5. 公告接口

### 5.1 GET /announcements

获取公告列表。

可选查询参数：

- `status`：例如 `draft` 或 `published`

### 5.2 POST /announcements

创建公告。仅 `admin` 和 `leader` 可访问。

请求示例：

```json
{
  "title": "周末活动通知",
  "body": "本周六晨跑照常进行。",
  "status": "published",
  "is_pinned": true
}
```

### 5.3 GET /announcements/{announcement_id}

获取单条公告详情。

### 5.4 PATCH /announcements/{announcement_id}

更新公告。

### 5.5 DELETE /announcements/{announcement_id}

删除公告。

## 6. 活动接口

### 6.1 GET /activities

获取活动列表。

可选查询参数：

- `status`：活动状态
- `keyword`：标题或描述关键词

### 6.2 POST /activities

创建活动。仅 `admin` 和 `leader` 可访问。

请求示例：

```json
{
  "title": "周六晨跑",
  "start_time": "2026-06-08T07:00:00+08:00",
  "location": "人民公园东门",
  "route": "环湖 5 公里",
  "distance_km": 5,
  "pace_group": "5'30-6'00",
  "description": "适合新老成员一起参加"
}
```

### 6.3 GET /activities/{activity_id}

获取活动详情。

### 6.4 PATCH /activities/{activity_id}

更新活动。

### 6.5 DELETE /activities/{activity_id}

删除活动。

## 7. 报名接口

### 7.1 POST /activities/{activity_id}/register

当前登录成员报名活动。

返回示例：

```json
{
  "data": {
    "status": "registered"
  }
}
```

常见错误：

- `409 Conflict`：重复报名
- `404 Not Found`：活动不存在
- `403 Forbidden`：无权限或状态不允许报名

### 7.2 DELETE /activities/{activity_id}/register

当前登录成员取消报名。

## 8. 签到接口

### 8.1 POST /activities/{activity_id}/attendance

当前登录成员签到。

返回示例：

```json
{
  "data": {
    "status": "signed_in",
    "gps_checked": true
  }
}
```

常见错误：

- `409 Conflict`：已签到
- `403 Forbidden`：未报名或不在允许签到范围内
- `404 Not Found`：活动不存在

### 8.2 GET /activities/{activity_id}/attendance

查看活动签到记录。通常仅管理员和团长可访问。

## 9. 健康检查

### GET /health

用于部署环境和容器探活。

返回示例：

```json
{
  "data": {
    "status": "ok"
  }
}
```

## 10. 使用建议

- 先调用登录或注册接口获取 token，再访问需要权限的接口
- 普通成员只应访问自己的资料和自己的报名/签到操作
- 管理员与团长应优先检查活动时间、报名人数和签到数据
- 如果接口返回 `403`，通常表示角色不足或状态不符合要求
