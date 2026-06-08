# Kanban Task

- Assignee: backend-dev
- Title: 增强健康检查接口的可观测性
- Description: 为 /health/readiness 增加更清晰的诊断信息输出，包括依赖检查结果、缺失环境变量列表和建议修复提示，便于前端与运维快速定位启动失败原因。
- Acceptance Criteria:
  1. /health/readiness 返回结构化诊断信息。
  2. 当依赖或环境变量缺失时，响应中包含可读的错误说明。
  3. 正常就绪时返回简洁的 ready 状态。
  4. 不影响现有健康检查路由的兼容性。
- Suggested Files: backend/*.py, backend/health*.py
