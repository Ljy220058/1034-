from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from typing import Any

WORKSPACE_PATH = "/root/autodl-tmp/projects/hermes-swarm-lab"


@dataclass(frozen=True)
class Template:
    template_id: str
    title_pattern: str
    default_topic: str
    artifact_pattern: str
    priority: int
    capability_keywords: tuple[str, ...]
    dedupe_checks: tuple[str, ...]


TEMPLATES: tuple[Template, ...] = (
    Template(
        template_id="frontend_experience",
        title_pattern="中文创意：{topic}前端体验优化",
        default_topic="活动报名入口",
        artifact_pattern="docs/{topic}前端体验优化.md",
        priority=8,
        capability_keywords=("frontend", "前端", "ui", "界面", "交互", "javascript"),
        dedupe_checks=("检查同页面同入口任务", "检查同名界面文档", "检查批次内是否已有前端模板"),
    ),
    Template(
        template_id="backend_api",
        title_pattern="中文创意：{topic}后端接口",
        default_topic="活动报名统计",
        artifact_pattern="docs/{topic}后端接口说明.md",
        priority=8,
        capability_keywords=("backend", "api", "后端", "接口", "fastapi", "sqlite"),
        dedupe_checks=("检查相同接口路径", "检查同主题后端任务", "检查批次内是否争用同一路由文件"),
    ),
    Template(
        template_id="quality_gate",
        title_pattern="中文创意：{topic}验收冒烟清单",
        default_topic="活动报名流程",
        artifact_pattern="docs/{topic}验收冒烟清单.md",
        priority=7,
        capability_keywords=("qa", "test", "quality", "测试", "验收", "质量门禁", "pytest"),
        dedupe_checks=("检查同对象验收清单", "检查重复测试名", "检查上游实现或方案是否存在"),
    ),
    Template(
        template_id="documentation_plan",
        title_pattern="中文创意：{topic}方案文档",
        default_topic="新手任务接力",
        artifact_pattern="docs/{topic}方案文档.md",
        priority=7,
        capability_keywords=("docs", "writer", "文档", "方案", "中文写作", "产品"),
        dedupe_checks=("检查同主题方案文档", "检查目标产物路径是否已存在", "检查是否只是改写旧标题"),
    ),
    Template(
        template_id="review_security",
        title_pattern="中文创意：{topic}风险审查",
        default_topic="成员权限边界",
        artifact_pattern="docs/{topic}风险审查.md",
        priority=7,
        capability_keywords=("review", "security", "audit", "审查", "安全", "合规", "风险"),
        dedupe_checks=("检查同对象评审文档", "检查是否已有进行中实现任务", "检查是否重复创建合规清单"),
    ),
    Template(
        template_id="ops_analysis",
        title_pattern="中文创意：{topic}运营分析方案",
        default_topic="活动留存指标",
        artifact_pattern="docs/{topic}运营分析方案.md",
        priority=6,
        capability_keywords=("data", "ops", "运营", "指标", "分析", "摘要"),
        dedupe_checks=("检查同指标分析文档", "检查同数据源任务", "检查指标口径是否明确"),
    ),
)


def _worker_text(worker: dict[str, Any]) -> str:
    values: list[str] = []
    for key in ("worker_key", "name"):
        if worker.get(key):
            values.append(str(worker[key]))
    capabilities = worker.get("capabilities") or []
    values.extend(str(item) for item in capabilities)
    return " ".join(values).lower()


def choose_template(worker: dict[str, Any], used_template_ids: set[str]) -> Template | None:
    text = _worker_text(worker)
    matched = [
        template
        for template in TEMPLATES
        if any(keyword.lower() in text for keyword in template.capability_keywords)
    ]
    if not matched:
        return None
    for template in matched:
        if template.template_id not in used_template_ids:
            return template
    return matched[0]


def build_body(template: Template, topic: str, artifact_path: str) -> str:
    if template.template_id == "frontend_experience":
        return (
            f"目标：为跑团成员优化{topic}的前端体验，明确入口、状态展示和异常提示。\n\n"
            "具体要求：\n"
            "1. 说明入口位置：活动详情页报名按钮区域。\n"
            "2. 覆盖至少三种交互状态：默认、加载中、异常或空状态。\n"
            f"3. 优先输出方案到 {artifact_path}；如需改代码，仅修改 frontend/ 下的轻量文件。\n"
            "4. 给出最小验收步骤，说明如何打开页面或检查文档。\n\n"
            "验收标准：中文说明清晰；入口、状态和失败提示可执行；产物路径明确；不重复已有同主题前端任务。"
        )
    if template.template_id == "backend_api":
        return (
            f"目标：实现或设计{topic}后端接口，服务于跑团运营统计场景。\n\n"
            "具体要求：\n"
            f"1. 接口路径：/api/v1/{topic}/summary，由 worker 根据现有路由命名规范调整为英文路径。\n"
            "2. 请求字段：时间范围、活动编号、分页参数。\n"
            "3. 返回字段：总数、成功数、失败数、中文摘要。\n"
            "4. 权限要求：管理员或团长可访问。\n"
            f"5. 若实现代码，补充最小测试；若仅做方案，输出接口说明到 {artifact_path}。\n\n"
            "验收标准：字段定义完整；错误处理有中文说明；权限边界清楚；至少包含一个成功示例和一个失败示例。"
        )
    if template.template_id == "quality_gate":
        return (
            f"目标：为{topic}建立测试与质量门禁，确保后续 worker 能按同一标准验收。\n\n"
            "具体要求：\n"
            "1. 覆盖测试范围：成功路径、失败路径、边界输入。\n"
            "2. 至少列出三个最小用例。\n"
            "3. 写清失败提示应包含哪些中文字段。\n"
            "4. 提供复测命令：pytest。\n"
            f"5. 产物输出到 {artifact_path}；如新增测试，放在 tests/ 下。\n\n"
            "验收标准：用例可执行；失败信息可定位；复测命令清楚；不与已有验收清单重复。"
        )
    if template.template_id == "documentation_plan":
        return (
            f"目标：为跑团管理员整理{topic}的中文方案文档，作为后续实现、测试或评审的依据。\n\n"
            "具体要求：\n"
            f"1. 输出到 {artifact_path}。\n"
            "2. 必含章节：背景、用户角色、任务流程、异常场景、验收步骤。\n"
            "3. 明确它与已有文档的关系：补充新手接力流程，不重复已有说明页。\n"
            "4. 每个关键建议都要给出可执行下一步。\n"
            "5. 附最小验收步骤，说明如何检查文档是否完整。\n\n"
            "验收标准：全文中文；章节完整；下一步可执行；产物路径不与近期任务重复。"
        )
    if template.template_id == "review_security":
        return (
            f"目标：审查{topic}在权限、数据和操作流程内的风险，并输出中文结论和整改建议。\n\n"
            "具体要求：\n"
            "1. 风险分级：高、中、低。\n"
            "2. 每条发现必须包含证据位置、影响、建议和是否阻塞。\n"
            f"3. 产物输出到 {artifact_path}。\n"
            "4. 不直接修改线上调度配置；如需修复，另建下游任务。\n"
            "5. 给出最小复核步骤。\n\n"
            "验收标准：风险分级一致；证据可定位；建议可执行；没有把评审任务写成重复实现任务。"
        )
    return (
        f"目标：围绕{topic}建立中文运营分析方案，帮助跑团管理员进行运营复盘。\n\n"
        "具体要求：\n"
        "1. 数据来源：活动、成员、报名和签到记录。\n"
        "2. 指标口径：总量、转化率、留存率和异常数。\n"
        "3. 输出格式：中文摘要、指标表和后续建议。\n"
        "4. 说明异常、缺失或权限不足时的处理方式。\n"
        f"5. 产物输出到 {artifact_path}。\n\n"
        "验收标准：指标可计算；数据来源明确；输出格式可复用；不重复已有周报、留存或异常分析任务。"
    )


def generate_cards(idle_workers: list[dict[str, Any]]) -> dict[str, Any]:
    used_template_ids: set[str] = set()
    used_artifacts: set[str] = set()
    cards: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []

    for worker in idle_workers:
        template = choose_template(worker, used_template_ids)
        worker_key = str(worker.get("worker_key") or worker.get("name") or "未命名worker")
        if template is None:
            skipped.append({"worker": worker_key, "reason": "无法识别 worker 能力"})
            continue
        used_template_ids.add(template.template_id)
        topic = str(worker.get("topic") or template.default_topic)
        artifact_path = template.artifact_pattern.format(topic=topic)
        if artifact_path in used_artifacts:
            skipped.append({"worker": worker_key, "reason": "批次内目标产物路径重复"})
            continue
        used_artifacts.add(artifact_path)
        cards.append(
            {
                "title": template.title_pattern.format(topic=topic),
                "assignee": worker_key,
                "template_id": template.template_id,
                "workspace_kind": "dir",
                "workspace_path": WORKSPACE_PATH,
                "artifact_path": artifact_path,
                "priority": template.priority,
                "body": build_body(template, topic, artifact_path),
                "dedupe_checks": list(template.dedupe_checks),
            }
        )

    return {
        "cards": cards,
        "skipped_workers": skipped,
        "summary": {
            "input_idle_workers": len(idle_workers),
            "generated_cards": len(cards),
            "skipped_workers": len(skipped),
            "used_templates": [card["template_id"] for card in cards],
        },
    }


def example_workers() -> list[dict[str, Any]]:
    return [
        {"worker_key": "frontend-dev", "name": "前端开发工人", "capabilities": ["前端", "界面", "交互"]},
        {"worker_key": "docs-writer", "name": "文档方案工人", "capabilities": ["文档", "方案", "中文写作"]},
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="中文创意任务模板选择器示例")
    parser.add_argument("--example", action="store_true", help="使用内置两个空闲 worker 示例")
    parser.add_argument("--input-json", help="包含 idle_workers 字段的 JSON 字符串")
    args = parser.parse_args()

    if args.example:
        workers = example_workers()
    elif args.input_json:
        payload = json.loads(args.input_json)
        workers = payload.get("idle_workers", [])
    else:
        parser.error("请使用 --example，或通过 --input-json 传入 idle_workers")

    print(json.dumps(generate_cards(workers), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
