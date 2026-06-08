## t_dce18a4a 活动照片墙组件经验
- 现有前端入口页可通过追加挂载区块与模块化 script 渐进接入新组件，避免推倒 index.html 现有结构。
- 照片墙适合使用 CSS 多列瀑布流与 dialog 灯箱组合实现，移动端通过 column-width 与 max-width: 100% 避免 375px 横向滚动。
- 对接图片上传接口时可在 api.js 中补充 FormData 上传方法，并在组件内同时覆盖 loading、empty、error、upload error 四类状态。
## t_70351938 成员跑量排行榜经验
- 现有单页入口可通过新增独立 section + 独立脚本模块接入排行榜组件，避免改动 app.js 主逻辑。
- 排行榜类组件适合拆成 summary / toggle / podium / list / state 五层结构，能同时覆盖加载、空态、错误、重试与移动端布局。
- 前三名高亮可复用现有 warning/danger/line 变量模拟金银铜层级，避免新增固定色值。
- 失败类型：[tool_error]
- 根因分析：首次用 execute_code 生成 leaderboard.js 时把模板字符串当作 Python 代码片段拼接，导致输出文件语法损坏。
- 规避方案：生成 JS 文件时优先整段原样写入，再用最小量命令做语法校验。
- 禁止重复：同类多层字符串拼接场景先做独立文件写入，不在 Python 字符串中混杂未转义模板片段。
