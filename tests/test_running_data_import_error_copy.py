from __future__ import annotations

from backend.import_error_copy import (
    check_import_error_messages,
    format_import_error_report,
    get_import_error_rules,
)


def test_import_error_rules_cover_required_chinese_scenarios() -> None:
    """规则表覆盖导入场景所需的五类中文错误文案。"""
    rules = get_import_error_rules()
    categories = {rule.category for rule in rules}

    assert categories == {'缺少字段', '格式错误', '重复活动', '权限不足', '来源平台不支持', '内容不一致'}
    assert all(rule.expected_message for rule in rules)
    assert all(rule.suggestion for rule in rules)
    assert '高驰' in {source for rule in rules for source in rule.sources}
    assert '佳明' in {source for rule in rules for source in rule.sources}


def test_import_error_checker_reports_no_error_for_consistent_messages() -> None:
    """一致中文文案不会产生不一致项。"""
    report = check_import_error_messages(
        [
            {'location': '后端 JSON 解析', 'category': '格式错误', 'message': '文件内容格式错误，请检查 CSV/JSON 后重试'},
            {'location': '前端高驰入口', 'category': '来源平台不支持', 'message': '暂不支持该来源平台，请选择高驰、佳明或通用 CSV/JSON'},
            {'location': '页面配置', 'category': '内容不一致', 'message': '导入内容与当前页面配置不一致，请重新选择来源平台'},
        ]
    )

    assert report.total_checked == 3
    assert report.inconsistencies == []
    assert format_import_error_report(report) == '检查完成：3 项文案一致，未发现不一致。'


def test_import_error_checker_reports_single_error_with_chinese_suggestion() -> None:
    """单个不一致项返回稳定中文建议。"""
    report = check_import_error_messages(
        [{'location': '启动授权', 'category': '权限不足', 'message': 'running data import requires explicit consent precheck acknowledgement'}]
    )

    assert len(report.inconsistencies) == 1
    item = report.inconsistencies[0]
    assert item.location == '启动授权'
    assert item.expected_message == '请先确认导入授权范围后再继续'
    assert '建议改为：请先确认导入授权范围后再继续' in format_import_error_report(report)


def test_import_error_checker_reports_multiple_errors_in_stable_order() -> None:
    """多个不一致项按输入顺序输出中文说明。"""
    report = check_import_error_messages(
        [
            {'location': 'CSV 表头', 'category': '格式错误', 'message': '无法解析 CSV 表头'},
            {'location': '重复检测', 'category': '重复活动', 'message': '活动已存在'},
        ]
    )
    output = format_import_error_report(report)

    assert report.total_checked == 2
    assert [item.location for item in report.inconsistencies] == ['CSV 表头', '重复检测']
    assert '发现 2 项导入错误文案不一致' in output
    assert '第 1 项：CSV 表头' in output
    assert '第 2 项：重复检测' in output
