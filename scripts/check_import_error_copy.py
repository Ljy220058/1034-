from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.import_error_copy import check_import_error_messages, format_import_error_report


CURRENT_IMPORT_ERROR_SAMPLES: tuple[dict[str, str], ...] = (
    {'location': '后端 CSV 表头解析', 'category': '格式错误', 'message': '无法解析 CSV 表头'},
    {'location': '后端 JSON 内容解析', 'category': '格式错误', 'message': '无法解析 JSON 内容'},
    {'location': '后端 JSON 活动记录解析', 'category': '缺少字段', 'message': 'JSON 内容缺少活动记录'},
    {'location': '导入向导行级校验', 'category': '缺少字段', 'message': '缺少必填字段'},
    {'location': '导入向导重复活动提示', 'category': '重复活动', 'message': '活动已存在'},
    {'location': '导入预检来源校验', 'category': '来源平台不支持', 'message': 'source must be one of: coros, garmin, generic, manual_file'},
    {'location': '导入启动来源校验', 'category': '来源平台不支持', 'message': 'source must be one of: coros, garmin, generic, manual_file'},
    {'location': '导入向导来源校验', 'category': '来源平台不支持', 'message': 'source must be one of: coros, garmin, generic, manual_file'},
    {'location': '导入启动授权校验', 'category': '权限不足', 'message': 'running data import requires explicit consent precheck acknowledgement'},
)

DEMO_SAMPLES: dict[str, tuple[dict[str, str], ...]] = {
    'none': (
        {'location': '演示 JSON 解析', 'category': '格式错误', 'message': '文件内容格式错误，请检查 CSV/JSON 后重试'},
        {'location': '演示来源平台', 'category': '来源平台不支持', 'message': '暂不支持该来源平台，请选择高驰、佳明或通用 CSV/JSON'},
    ),
    'single': (
        {'location': '演示授权', 'category': '权限不足', 'message': 'running data import requires explicit consent precheck acknowledgement'},
    ),
    'multiple': (
        {'location': '演示 CSV 表头', 'category': '格式错误', 'message': '无法解析 CSV 表头'},
        {'location': '演示重复活动', 'category': '重复活动', 'message': '活动已存在'},
    ),
}


def _build_parser() -> argparse.ArgumentParser:
    """创建命令行参数解析器。

    Returns:
        参数解析器。
    """
    parser = argparse.ArgumentParser(description='检查跑步数据导入中文错误文案一致性')
    parser.add_argument(
        '--demo',
        choices=sorted(DEMO_SAMPLES),
        help='运行最小验证样例：none 无错误，single 单个错误，multiple 多个错误',
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """执行导入错误文案一致性检查。

    Args:
        argv: 命令行参数列表。
    Returns:
        发现不一致时返回 1，否则返回 0。
    """
    args = _build_parser().parse_args(argv)
    samples = DEMO_SAMPLES[args.demo] if args.demo else CURRENT_IMPORT_ERROR_SAMPLES
    report = check_import_error_messages(samples)
    print(format_import_error_report(report))
    return 1 if report.inconsistencies else 0


if __name__ == '__main__':
    raise SystemExit(main())
