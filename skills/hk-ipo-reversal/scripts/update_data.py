#!/usr/bin/env python3
"""港股新股暗盘反转猎手 V2 - 数据批量更新脚本
通过 westock-data 从腾讯自选股拉取已上市新股的真实 K 线数据，
更新 data.py 中标注★的估算值（day2/day7/day10/day1_high/day1_low/turnover 等），
并追加恒指最新月度数据。

Usage:
  python3 update_data.py                # 更新所有缺失数据
  python3 update_data.py --dry-run      # 仅预览，不写入
  python3 update_data.py --hsi-only     # 仅更新恒指月度数据
  python3 update_data.py --code 01021   # 仅更新指定股票
"""
import sys
import os
import time

_this_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _this_dir)

# 引用 sweet-spot 的 fetcher
_sweet_spot_dir = os.path.join(_this_dir, "..", "..", "hk-ipo-sweet-spot", "scripts")
if os.path.isdir(_sweet_spot_dir):
    sys.path.append(os.path.abspath(_sweet_spot_dir))

from data import ipo_data, hsi_monthly
from fetcher import (
    is_available, fetch_kline, fetch_hsi_monthly,
    compute_day_returns, clear_cache,
)


# reversal 的 data.py 有 22 个字段
REVERSAL_FIELDS = [
    "name", "code", "date", "subscription_mult", "fundraising",
    "has_cornerstone", "category",
    "dark_return", "dark_high", "dark_low",
    "day1_return", "day1_high", "day1_low",
    "day2_return", "day3_return", "day5_return",
    "day7_return", "day10_return",
    "day1_turnover", "day1_volume_hkd",
    "expected_return", "deviation",
]

# 可通过 K 线更新的字段（对应交易日）
KLINE_FIELDS = {
    1: {"return": "day1_return", "high": "day1_high", "low": "day1_low"},
    2: {"return": "day2_return"},
    3: {"return": "day3_return"},
    5: {"return": "day5_return"},
    7: {"return": "day7_return"},
    10: {"return": "day10_return"},
}


def find_ipo_price(stock):
    """从 day1_return 和 K 线反推发行价"""
    day1 = stock.get("day1_return")
    if day1 is None:
        return None

    kline = fetch_kline(stock["code"], period="day", count=20)
    if not kline:
        return None

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
    """更新单只股票的缺失字段（比 sweet-spot 版更多字段）"""
    code = stock["code"]

    # 查找需要更新的 None 字段
    kline_updatable = []
    for day, fields in KLINE_FIELDS.items():
        for field_type, field_name in fields.items():
            if stock.get(field_name) is None:
                kline_updatable.append((day, field_type, field_name))

    # 检查换手率
    need_turnover = stock.get("day1_turnover") is None

    if not kline_updatable and not need_turnover:
        return 0, []

    # 获取发行价
    ipo_price = find_ipo_price(stock)
    if ipo_price is None:
        return 0, []

    # 获取 K 线
    kline = fetch_kline(code, period="day", count=20)
    if not kline:
        return 0, []

    kline_sorted = sorted(kline, key=lambda x: x.get("date", ""))
    listing_date = stock.get("date", "")
    if listing_date:
        kline_sorted = [k for k in kline_sorted if k.get("date", "") >= listing_date]

    if not kline_sorted:
        return 0, []

    updates = []

    for idx, row in enumerate(kline_sorted):
        trading_day = idx + 1
        close = row.get("last")
        high = row.get("high")
        low = row.get("low")

        if close is None:
            continue

        for day, field_type, field_name in kline_updatable:
            if trading_day != day:
                continue
            if field_type == "return":
                new_val = round((close - ipo_price) / ipo_price * 100, 2)
            elif field_type == "high" and high:
                new_val = round((high - ipo_price) / ipo_price * 100, 2)
            elif field_type == "low" and low:
                new_val = round((low - ipo_price) / ipo_price * 100, 2)
            else:
                continue

            if not dry_run:
                stock[field_name] = new_val
            updates.append((field_name, new_val))

        # 首日换手率
        if trading_day == 1 and need_turnover:
            turnover = row.get("exchange")
            if turnover is not None:
                if not dry_run:
                    stock["day1_turnover"] = turnover
                updates.append(("day1_turnover", turnover))

                # 成交额
                amount = row.get("amount")
                if amount is not None:
                    # amount 单位可能是元，转为百万港元
                    vol_hkd = round(amount / 1_000_000, 1) if amount > 10_000_000 else amount
                    if not dry_run:
                        stock["day1_volume_hkd"] = vol_hkd
                    updates.append(("day1_volume_hkd", vol_hkd))

        if trading_day >= 10:
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
    """将更新后的数据写回 data.py（reversal 版，22个字段）"""
    if output_path is None:
        output_path = os.path.join(_this_dir, "data.py")

    lines = []
    lines.append('#!/usr/bin/env python3')
    lines.append('"""港股新股暗盘反转猎手 - 增强版数据集 V2 (含期望偏差)')
    lines.append('数据来源：东方财富、华盛通、富途牛牛、财联社等公开数据 + westock-data 自动更新')
    lines.append('基础字段继承自 hk-ipo-sweet-spot，新增字段（标注 ★）为统计估算值，')
    lines.append('部分已通过 westock-data 替换为真实数据。')
    lines.append('')
    lines.append('字段说明：')
    lines.append('  name: 证券简称 | code: 股票代码 | date: 上市日期')
    lines.append('  subscription_mult: 公开认购倍数 | fundraising: 募资额(亿港元)')
    lines.append('  has_cornerstone: 是否有基石投资者 | category: 行业分类')
    lines.append('  dark_return: 暗盘收盘涨跌幅(%) | ★dark_high: 暗盘最高涨跌幅(%)')
    lines.append('  ★dark_low: 暗盘最低涨跌幅(%)')
    lines.append('  day1_return: 首日涨跌幅(%) | ★day1_high: 首日最高涨跌幅(%)')
    lines.append('  ★day1_low: 首日最低涨跌幅(%)')
    lines.append('  ★day2_return: 第2日涨跌幅(%) | day3_return: 第3日涨跌幅(%)')
    lines.append('  day5_return: 第5日涨跌幅(%) | ★day7_return: 第7日涨跌幅(%)')
    lines.append('  ★day10_return: 第10日涨跌幅(%)')
    lines.append('  ★day1_turnover: 首日换手率(%) | ★day1_volume_hkd: 首日成交额(百万港元)')
    lines.append('  ★expected_return: 预期首日涨幅(%) | ★deviation: 期望偏差(%)')
    lines.append('"""')
    lines.append('')
    lines.append('ipo_data = [')

    for d in ipo_data_list:
        parts = []
        for k in REVERSAL_FIELDS:
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
    parser = argparse.ArgumentParser(description="港股新股暗盘反转猎手 V2 - 数据批量更新")
    parser.add_argument("--dry-run", action="store_true", help="仅预览，不写入文件")
    parser.add_argument("--hsi-only", action="store_true", help="仅更新恒指月度数据")
    parser.add_argument("--code", type=str, help="仅更新指定股票代码")
    parser.add_argument("--output", type=str, help="输出文件路径（默认覆盖 data.py）")
    args = parser.parse_args()

    if not is_available():
        print("❌ westock-data 不可用，请确保已安装 Node.js 和 npx")
        sys.exit(1)

    print("📡 港股新股暗盘反转猎手 V2 - 数据更新")
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

    # 2. 更新股票 dayN 收益率（reversal 版：更多字段）
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
            update_str = ", ".join(f"{k}={v}" for k, v in updates[:3])
            if len(updates) > 3:
                update_str += f" (+{len(updates)-3} more)"
            print(f"  ✅ {stock['name']} ({stock['code']}): {update_str}")

        if (i + 1) % 10 == 0 and len(targets) > 10:
            print(f"  ... 已处理 {i+1}/{len(targets)}")

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
