"""
产品增量分析基础数据导入脚本

读取 docs/request_src/产品增量分析/ 下的 3 张 Excel 表，
调用 app.core.db 模块入库到 SQLite，并输出导入结果摘要。

执行方式:  python -m scripts.import_data
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pandas as pd

# 确保项目根目录在 sys.path 中
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core import db as db_manager  # noqa: E402

# ── 数据源定义 ──────────────────────────────────────────────────
SRC_DIR = ROOT / "docs" / "request_src" / "产品增量分析"

FILES = [
    {
        "file": "每日规模余额表.xlsx",
        "table_name": "daily_balance",
        "description": "各产品系列每日规模余额",
    },
    {
        "file": "每日规模增量明细表.xlsx",
        "table_name": "daily_increment_detail",
        "description": "子产品维度每日增长/流失/净增长明细",
    },
    {
        "file": "每月增量目标表.xlsx",
        "table_name": "monthly_increment_target",
        "description": "按期限分类和渠道的月度增量目标及预测",
    },
]


def _preprocess_monthly(df: pd.DataFrame) -> pd.DataFrame:
    """将每月增量目标表的 Excel 序列号月份列转为标准日期格式 YYYY-MM，并重命名渠道列"""
    if "月份" in df.columns:
        df["月份"] = pd.to_datetime(
            df["月份"], origin="1899-12-30", unit="D", errors="coerce"
        ).dt.strftime("%Y-%m")
    # 重命名列: 渠道I类 -> 目标标签, 渠道II类 -> 目标标签说明
    rename_map = {}
    if "渠道I类" in df.columns:
        rename_map["渠道I类"] = "目标标签"
    if "渠道II类" in df.columns:
        rename_map["渠道II类"] = "目标标签说明"
    if rename_map:
        df = df.rename(columns=rename_map)
    return df


def _preprocess_increment(df: pd.DataFrame) -> pd.DataFrame:
    """将增量明细表的列名中的中文括号去掉: 增长(元) -> 增长"""
    rename_map = {
        "增长(元)": "增长",
        "流失(元)": "流失",
        "净增长(元)": "净增长",
    }
    df = df.rename(columns=rename_map)
    return df


def _preprocess_balance(df: pd.DataFrame) -> pd.DataFrame:
    """将每日规模余额表的日期列格式化为 YYYY-MM-DD（去除时间部分）"""
    if "数据日期" in df.columns:
        df["数据日期"] = pd.to_datetime(
            df["数据日期"], errors="coerce"
        ).dt.strftime("%Y-%m-%d")
    return df


async def main():
    print("=" * 60)
    print("  产品增量分析 — 基础数据导入")
    print("=" * 60)

    # 1. 初始化数据库
    await db_manager.init_db()
    print("\n[1/4] 数据库初始化完成\n")

    # 2. 逐文件读取并入库
    results = []
    for item in FILES:
        filepath = SRC_DIR / item["file"]
        print(f"  读取: {item['file']} ... ", end="")

        if not filepath.exists():
            print(f"文件不存在: {filepath}")
            continue

        df = pd.read_excel(filepath)
        print(f"{len(df)} 行, {len(df.columns)} 列")

        # 预处理
        if item["table_name"] == "monthly_increment_target":
            df = _preprocess_monthly(df)
        elif item["table_name"] == "daily_balance":
            df = _preprocess_balance(df)
        elif item["table_name"] == "daily_increment_detail":
            df = _preprocess_increment(df)

        # 入库
        meta = await db_manager.ingest_dataframe(
            df=df,
            table_name=item["table_name"],
            filename=item["file"],
            description=item["description"],
            file_type="excel",
            mode="create",
        )
        results.append(meta)
        print(f"  -> 入库成功: table={meta['table_name']}, id={meta['id']}")

    # 3. 验证
    print(f"\n[2/4] 共入库 {len(results)} 张表\n")
    datasets = await db_manager.list_datasets()
    print("[3/4] 当前数据库中的数据集列表:")
    print("-" * 60)
    for ds in datasets:
        print(f"  {ds['table_name']:30s} | {ds['filename']:30s} | {ds['row_count']:>6d} 行")
    print("-" * 60)

    # 4. 抽样验证
    print("\n[4/4] 抽样验证 (每表前 3 行):")
    for r in results:
        detail = await db_manager.get_dataset(r["id"], preview=3)
        if detail and "preview" in detail:
            print(f"\n  [{r['table_name']}]")
            cols = detail["columns"]
            print(f"    列: {cols}")
            for row in detail["preview"]:
                print(f"    {row}")

    print("\n" + "=" * 60)
    print("  导入完成!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
