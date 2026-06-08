# 训练计划日历订阅导出质量门禁清单

## 一、适用范围

本清单用于检查训练计划日历订阅导出的 iCal/ICS 文件是否达到最小可上线标准。检查对象包括后端导出函数、活动数据转换、已有活动字段、测试契约以及人工导入日历客户端后的表现。当前仓库中与本门禁直接相关的文件包括：

- `tests/test_calendar_export.py`：训练计划 ICS 导出的验收契约测试。
- `backend/routes/activities.py`：活动读取接口与活动字段来源。
- `backend/task_import.py`：任务批量导入的中文错误处理参考。
- `docs/api.md`：活动模型、接口字段和时间字段约定。
- `docs/user-guide.md`：用户查看活动、报名和签到的业务语境。

## 二、最小验收原则

1. 导出的内容必须是合法文本格式，使用 `BEGIN:VCALENDAR` 开始，并使用 `END:VCALENDAR` 结束。
2. 每个训练活动必须映射为一个 `VEVENT`，并保留标题、开始时间、结束时间、说明和可选地点。
3. 时间字段必须稳定、可排序，并能表达跨天训练。
4. 中文标题和中文说明必须原样保留，不能出现乱码、丢字或转义破坏。
5. 空训练计划也必须返回合法空日历壳，不能报错或返回空字符串。
6. 错误场景必须给出清晰异常，不能静默生成错误日历。
7. 导出结果必须能被常见日历客户端识别，人工验收时至少覆盖一个本地或网页日历客户端。
8. 本门禁只判断导出质量，不要求在此任务中实现大规模业务代码。

## 三、门禁检查项

### 检查项 1：ICS 外壳合法

通过标准：导出内容以 `BEGIN:VCALENDAR` 开头，包含 `VERSION:2.0`，并以 `END:VCALENDAR` 结尾；换行使用日历客户端常见的回车换行格式。

失败示例：导出内容只有 JSON、缺少 `VERSION:2.0`、结尾没有 `END:VCALENDAR`，或多个字段粘在同一行导致客户端无法识别。

建议验证命令：

```bash
pytest -q tests/test_calendar_export.py -k '合法ics内容 or 空训练计划'
```

### 检查项 2：中文标题保留

通过标准：活动标题为中文时，`SUMMARY` 字段中应保留完整中文原文，例如 `雨中节奏跑` 或 `周末长距离训练`。

失败示例：中文标题被替换为问号、被截断、出现乱码，或被错误编码成不可读内容。

建议验证命令：

```bash
pytest -q tests/test_calendar_export.py -k '中文标题'
```

### 检查项 3：中文说明保留

通过标准：活动说明为中文时，`DESCRIPTION` 字段应保留完整中文语义，并允许包含训练提示、配速说明和集合提醒。

失败示例：说明字段缺失、只保留英文占位符、中文标点导致导出失败，或说明内容被写入错误字段。

建议验证命令：

```bash
pytest -q tests/test_calendar_export.py -k '中文标题和说明'
```

### 检查项 4：跨天训练时间正确

通过标准：跨天训练的 `DTSTART` 和 `DTEND` 必须分别使用真实开始日期和真实结束日期，不能把结束日期强制改回开始日。

失败示例：训练从六月七日晚上开始、六月八日凌晨结束，但导出结果把结束时间写成六月七日；或客户端显示为零时长事件。

建议验证命令：

```bash
pytest -q tests/test_calendar_export.py -k '跨天训练'
```

### 检查项 5：缺失地点不阻断导出

通过标准：地点为空或缺失时仍能导出事件；结果中不应出现空的 `LOCATION:` 字段，也不应抛出非必要异常。

失败示例：地点为 `None` 时导出函数崩溃，或生成 `LOCATION:None`、`LOCATION:null`、`LOCATION:` 这类污染字段。

建议验证命令：

```bash
pytest -q tests/test_calendar_export.py -k '缺失地点'
```

### 检查项 6：空训练计划输出合法空日历

通过标准：没有训练活动时返回合法 `VCALENDAR` 壳，并且不包含任何 `VEVENT`；调用方可直接把内容作为订阅文件返回。

失败示例：返回空字符串、返回 `None`、抛出异常，或生成一个没有标题和时间的伪事件。

建议验证命令：

```bash
pytest -q tests/test_calendar_export.py -k '空训练计划'
```

### 检查项 7：多个活动按开始时间升序排列

通过标准：输入活动即使乱序，导出的多个 `VEVENT` 也必须按 `start_time` 从早到晚排列，保证日历客户端展示顺序稳定。

失败示例：导出结果跟随输入乱序，导致清晨训练排在晚间训练之后，或同一订阅每次导出的顺序不稳定。

建议验证命令：

```bash
pytest -q tests/test_calendar_export.py -k '多个训练活动'
```

### 检查项 8：结束时间早于开始时间时失败清晰

通过标准：结束时间早于开始时间时必须抛出明确校验错误，错误信息中应包含 `end_time` 和 `start_time`，方便开发者定位问题。

失败示例：静默生成负时长事件、自动交换起止时间但不告警，或只抛出模糊的内部错误。

建议验证命令：

```bash
pytest -q tests/test_calendar_export.py -k '结束时间早于开始时间'
```

### 检查项 9：最小字段完整

通过标准：字段完整的训练活动应至少导出标题、开始时间、结束时间、地点、说明和活动链接；可选字段缺失时不能影响必填字段。

失败示例：只导出标题和时间，遗漏地点、说明或链接；或者把活动链接拼进说明导致客户端无法直接识别链接字段。

建议验证命令：

```bash
pytest -q tests/test_calendar_export.py -k '最小日历字段'
```

### 检查项 10：导出模块可被后端导入

通过标准：后端包可以正常导入；如果实现了 `backend.calendar_export`，该模块也应能直接导入，不出现语法错误或循环导入错误。

失败示例：`python -c "import backend"` 失败，或导入 `backend.calendar_export` 时触发缺失依赖、语法错误、循环导入。

建议验证命令：

```bash
python -c "import backend"
python -c "import backend.calendar_export"
```

### 检查项 11：安全红线扫描通过

通过标准：新增导出逻辑和文档中不得出现硬编码密钥，不得为了拼接查询或链接引入明显注入风险；至少确认仓库中没有形如“密码变量直接等于明文字符串”或“接口密钥变量直接等于明文字符串”的硬编码敏感值。

失败示例：在测试或示例中写入真实令牌、真实密码、真实日历订阅密钥，或把用户输入直接拼接到未转义的 SQL 查询里。

建议验证命令：

```bash
grep -RInE 'password\s*=\s*"|api_key\s*=\s*"|secret\s*=\s*"|token\s*=\s*"' backend tests docs || true
```

### 检查项 12：客户端可识别性人工抽查

通过标准：把导出的 `.ics` 文件保存到本地后，至少用一个常见日历客户端或在线解析器打开；应能看到正确标题、时间、地点和说明。

失败示例：客户端提示文件损坏、事件时间偏移明显、中文乱码、多个活动只显示一个，或空计划文件无法打开。

建议验证命令：

```bash
python - <<'PY'
from pathlib import Path
from datetime import datetime, timezone
from backend.calendar_export import export_training_plan_ics
content = export_training_plan_ics([
    {
        'title': '雨中节奏跑',
        'start_time': datetime(2026, 6, 7, 23, 0, tzinfo=timezone.utc),
        'end_time': datetime(2026, 6, 8, 1, 30, tzinfo=timezone.utc),
        'location': '奥森南园',
        'description': '集合后热身，注意补水',
        'activity_url': 'https://run.example.com/activities/42',
    }
])
Path('/tmp/training-plan-smoke.ics').write_text(content, encoding='utf-8')
print('/tmp/training-plan-smoke.ics')
PY
```

## 四、人工验收流程

1. 先执行 `python -c "import backend"`，确认后端包没有基础导入错误。
2. 执行 `pytest -q tests/test_calendar_export.py`，确认训练计划 ICS 契约测试的当前结果符合预期；如果测试仍被标记为预期失败，应记录为“实现未完成，契约已定义”。
3. 准备五组样例数据：中文标题、跨天训练、缺失地点、空训练计划、乱序多活动。
4. 生成 `/tmp/training-plan-smoke.ics`，并人工打开或导入一个常见日历客户端。
5. 在客户端中逐项核对：标题可读、时间正确、跨天显示正确、地点缺失时界面干净、多个活动顺序合理。
6. 执行安全扫描命令，确认没有硬编码密钥或明显注入红线。
7. 把命令输出、客户端截图或人工核对结论记录到任务评论或发布说明中。
8. 只有自动测试、导入检查、安全扫描和人工客户端抽查全部通过时，才允许标记训练计划日历导出质量门禁通过。

## 五、后续建议

- 如果 `backend.calendar_export` 尚未实现，应由后端任务补齐实现，再让本清单作为质量门禁复核依据。
- 建议后续增加一个真实 `.ics` 样例文件的快照测试，防止字段顺序、换行和中文编码被意外修改。
- 建议在接口文档中补充日历订阅端点、鉴权方式、缓存策略和订阅链接失效策略。
