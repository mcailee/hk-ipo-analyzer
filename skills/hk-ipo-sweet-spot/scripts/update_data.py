#!/usr/bin/env python3
"""港股打新甜蜜区间分析器 - 数据批量更新脚本
通过 westock-data 从腾讯自选股拉取已上市新股的真实 K 线数据，
更新 data.py 中的估算值（day3_return / day5_return），并追加恒指最新月度数据。

Usage:
  python3 update_data.py                # 更新所有缺失数据
  python3 update_data.py --dry-run      # 仅预览，不写入
  python3 update_data.py --hsi-only     # 仅更新恒指月度数据
  python3 update_data.py --code 01021   # 仅更新指定股票
"""
import sys
import os
import time
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data import ipo_data, hsi_monthly
from fetcher import (
    is_available, fetch_kline, fetch_hsi_monthly,
    compute_day_returns, clear_cache,
)


def find_ipo_price(stock):
    """从 day1_return 和 K 线反推发行价"""
    day1 = stock.get("day1_return")
    if day1 is None:
        return None

    code = stock["code"]
    kline = fetch_kline(code, period="day", count=15)
    if not kline:
        return None

    # 按日期排序
    kline_sorted = sorted(kline, key=lambda x: x.get("date", ""))
    listing_date = stock.get("date", "")
    if listing_date:
        kline_sorted = [k for k in kline_sorted if k.get("date", "") >= listing_date]

    if not kline_sorted:
        return None

    first_close = kline_sorted[0].get("last")
    if first_close and day1 != -100:
        return first_close / (1 + day1 / 100)
    return None


def update_stock_returns(stock, dry_run=False):
    """更新单只股票的缺失 dayN 收益率"""
    code = stock["code"]
    name = stock["name"]

    # 检查是否有缺失值
    fields_to_check = ["day3_return", "day5_return"]
    missing = [f for f in fields_to_check if stock.get(f) is None]

    if not missing:
        return 0, []

    # 获取发行价
    ipo_price = find_ipo_price(stock)
    if ipo_price is None:
        return 0, []

    # 获取 K 线
    kline = fetch_kline(code, period="day", count=15)
    if not kline:
        return 0, []

    kline_sorted = sorted(kline, key=lambda x: x.get("date", ""))
    listing_date = stock.get("date", "")
    if listing_date:
        kline_sorted = [k for k in kline_sorted if k.get("date", "") >= listing_date]

    if not kline_sorted:
        return 0, []

    # 计算收益率
    day_map = {3: "day3_return", 5: "day5_return"}
    updates = []

    for idx, row in enumerate(kline_sorted):
        trading_day = idx + 1
        if trading_day in day_map:
            key = day_map[trading_day]
            if stock.get(key) is None:
                close = row.get("last")
                if close and ipo_price > 0:
                    new_val = round((close - ipo_price) / ipo_price * 100, 2)
                    if not dry_run:
                        stock[key] = new_val
                    updates.append((key, new_val))
        if trading_day >= 5:
            break

    return len(updates), updates


def update_hsi_monthly(dry_run=False):
    """更新恒指月度涨跌幅"""
    fresh = fetch_hsi_monthly(months=24)
    if not fresh:
        return 0, {}

    new_months = {}
    for ym, val in fresh.items():
        if ym not in hsi_monthly:
            new_months[ym] = val
            if not dry_run:
                hsi_monthly[ym] = val

    return len(new_months), new_months


def write_data_py(ipo_data_list, hsi_monthly_dict, output_path=None):
    """将更新后的数据写回 data.py"""
    if output_path is None:
        output_path = os.path.join(os.path.dirname(__file__), "data.py")

    lines = []
    lines.append('#!/usr/bin/env python3')
    lines.append('"""港股打新甜蜜区间分析器 - 数据集模块')
    lines.append('数据来源：东方财富、华盛通、富途牛牛、财联社等公开数据 + westock-data 自动更新')
    lines.append('字段说明：')
    lines.append('  name: 证券简称 | code: 股票代码 | date: 上市日期')
    lines.append('  subscription_mult: 公开认购倍数 | day1_return: 首日涨跌幅(%)')
    lines.append('  fundraising: 募资额(亿港元) | has_cornerstone: 是否有基石投资者')
    lines.append('  category: 行业分类 | dark_return: 暗盘涨跌幅(%) [可为None]')
    lines.append('  day3_return: 上市后第3日涨跌幅(%) [可为None]')
    lines.append('  day5_return: 上市后第5日涨跌幅(%) [可为None]')
    lines.append('  is_18c: 是否为18C/B类未盈利上市机制 [V3.4新增]')
    lines.append('"""')
    lines.append('')
    lines.append('ipo_data = [')

    for d in ipo_data_list:
        parts = []
        for k in ["name", "code", "date", "subscription_mult", "day1_return",
                   "fundraising", "has_cornerstone", "category", "dark_return",
                   "day3_return", "day5_return", "is_18c"]:
            v = d.get(k)
            if v is None:
                parts.append(f'"{k}": None')
            elif isinstance(v, bool):
                parts.append(f'"{k}": {v}')
            elif isinstance(v, str):
                parts.append(f'"{k}": "{v}"')
            elif isinstance(v, (int, float)):
                parts.append(f'"{k}": {v}')
            else:
                parts.append(f'"{k}": {repr(v)}')
        line = "    {" + ", ".join(parts) + "},"
        lines.append(line)

    lines.append(']')
    lines.append('')
    lines.append('# ============================================')
    lines.append('# 恒生指数月度涨跌幅 (%)')
    lines.append('# 数据来源：港交所 HKEX 2024 Fact Book 及公开行情数据 + westock-data 自动更新')
    lines.append('# 用途：市场状态分类（牛/熊/震荡）')
    lines.append('# ============================================')
    lines.append('hsi_monthly = {')

    for ym in sorted(hsi_monthly_dict.keys()):
        val = hsi_monthly_dict[ym]
        lines.append(f'    "{ym}": {val},')

    lines.append('}')
    lines.append('')

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return output_path


def main():
    import argparse
    parser = argparse.ArgumentParser(description="港股打新甜蜜区间分析器 - 数据批量更新")
    parser.add_argument("--dry-run", action="store_true", help="仅预览，不写入文件")
    parser.add_argument("--hsi-only", action="store_true", help="仅更新恒指月度数据")
    parser.add_argument("--code", type=str, help="仅更新指定股票代码")
    parser.add_argument("--output", type=str, help="输出文件路径（默认覆盖 data.py）")
    args = parser.parse_args()

    if not is_available():
        print("❌ westock-data 不可用，请确保已安装 Node.js 和 npx")
        sys.exit(1)

    print("📡 港股打新甜蜜区间分析器 - 数据更新")
    print(f"📊 当前数据集: {len(ipo_data)} 只新股, 恒指 {len(hsi_monthly)} 个月")
    print(f"{'🔍 预览模式' if args.dry_run else '✏️ 写入模式'}")
    print()

    # 1. 更新恒指
    print("=== 恒指月度数据 ===")
    n_hsi, new_hsi = update_hsi_monthly(dry_run=args.dry_run)
    if n_hsi > 0:
        for ym, val in sorted(new_hsi.items()):
            print(f"  ✅ {ym}: {val:+.2f}%")
        print(f"  新增 {n_hsi} 个月")
    else:
        print("  ✅ 已是最新")

    if args.hsi_only:
        if not args.dry_run:
            path = write_data_py(ipo_data, hsi_monthly, args.output)
            print(f"\n✅ 已更新: {path}")
        return

    # 2. 更新股票 dayN 收益率
    print("\n=== 股票收益率补充 ===")
    total_updates = 0
    stocks_updated = 0

    targets = ipo_data
    if args.code:
        code = args.code.zfill(5)
        targets = [d for d in ipo_data if d["code"] == code]
        if not targets:
            print(f"  ❌ 未找到股票 {args.code}")
            return

    for i, stock in enumerate(targets):
        n, updates = update_stock_returns(stock, dry_run=args.dry_run)
        if n > 0:
            stocks_updated += 1
            total_updates += n
            update_str = ", ".join(f"{k}={v:+.2f}%" for k, v in updates)
            print(f"  ✅ {stock['name']} ({stock['code']}): {update_str}")

        # 进度显示（每 10 只）
        if (i + 1) % 10 == 0 and len(targets) > 10:
            print(f"  ... 已处理 {i+1}/{len(targets)}")

        # 避免 API 限流
        if n > 0:
            time.sleep(0.5)

    print(f"\n📊 总结: 更新 {stocks_updated} 只股票的 {total_updates} 个字段")

    # 3. 写入文件
    if not args.dry_run and (n_hsi > 0 or total_updates > 0):
        path = write_data_py(ipo_data, hsi_monthly, args.output)
        print(f"✅ 已写入: {path}")
    elif args.dry_run:
        print("\n🔍 预览模式，未写入文件。去掉 --dry-run 执行实际更新。")
    else:
        print("\n✅ 无需更新")


if __name__ == "__main__":
    main()
