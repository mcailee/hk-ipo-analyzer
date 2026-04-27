#!/usr/bin/env python3
"""westock-data CLI 封装层 — 港股 IPO 数据获取模块
通过 subprocess 调用腾讯自选股数据工具 CLI 获取港股行情数据。
所有函数在 CLI 不可用或调用失败时返回 None，由调用方 fallback 到静态数据。

数据源：腾讯自选股行情数据接口（westock-data-skillhub）
调用方式：npx --yes westock-data-skillhub@latest <command> <args>

供 hk-ipo-sweet-spot 和 hk-ipo-reversal 共享使用。
"""
import subprocess
import re
import os
import json

# ============================================
# 配置
# ============================================

# westock-data CLI 命令前缀
_CLI_PREFIX = ["npx", "--yes", "westock-data-skillhub@latest"]

# 超时（秒）
_TIMEOUT = 30

# 恒生指数代码
HSI_CODE = "hkHSI"

# 缓存（进程生命周期内）
_cache = {}

# ============================================
# 底层：CLI 调用 + Markdown 表格解析
# ============================================

def _run_cli(args, timeout=None):
    """调用 westock-data CLI，返回标准输出字符串。失败返回 None。"""
    timeout = timeout or _TIMEOUT
    cmd = _CLI_PREFIX + args
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, "NODE_NO_WARNINGS": "1"},
        )
        if result.returncode != 0:
            return None
        return result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None


def parse_markdown_table(output):
    """解析 westock-data 输出的 Markdown 表格为字典列表。

    输入格式：
        | col1 | col2 | col3 |
        | --- | --- | --- |
        | val1 | val2 | val3 |
        | val4 | val5 | val6 |

    返回：[{"col1": "val1", "col2": "val2", ...}, ...]
    """
    if not output:
        return []

    # 合并多行内容：有些字段（如 introduction）包含换行符，
    # 导致一条数据跨多行。我们需要把断行的内容拼接回去。
    raw_lines = output.strip().split("\n")

    merged = []
    for line in raw_lines:
        stripped = line.strip()
        if not stripped:
            continue
        if not merged:
            merged.append(stripped)
            continue

        prev = merged[-1]
        prev_is_complete = prev.startswith("|") and prev.endswith("|")
        cur_starts_pipe = stripped.startswith("|")

        if prev_is_complete and cur_starts_pipe:
            # 前行完整，当前行是新行
            merged.append(stripped)
        elif not prev_is_complete:
            # 前行不完整（数据跨行），拼接
            merged[-1] = prev + " " + stripped
        elif prev_is_complete and not cur_starts_pipe:
            # 前行完整但当前行不以 | 开头 → 奇怪情况，单独存
            merged.append(stripped)
        else:
            merged.append(stripped)

    lines = [l.strip() for l in merged if l.strip()]
    # 找到表格行（以 | 开头和结尾）
    table_lines = [l for l in lines if l.startswith("|") and l.endswith("|")]
    if len(table_lines) < 3:  # 至少需要 header + separator + 1 data row
        return []

    def parse_row(line):
        """解析一行表格"""
        cells = [c.strip() for c in line.split("|")]
        # 去掉首尾空元素（| 分割产生）
        return [c for c in cells if c != "" or cells.index(c) not in (0, len(cells) - 1)]

    # 解析 header
    headers = parse_row(table_lines[0])

    # 跳过分隔行（| --- | --- | --- |）
    data_lines = [l for l in table_lines[2:] if not re.match(r"^\|[\s\-|]+\|$", l)]

    rows = []
    for line in data_lines:
        values = parse_row(line)
        if len(values) >= len(headers):
            row = {}
            for i, h in enumerate(headers):
                val = values[i] if i < len(values) else ""
                row[h] = _auto_type(val)
            rows.append(row)

    return rows


def _auto_type(val):
    """自动类型转换：数字字符串转 float/int"""
    if not isinstance(val, str):
        return val
    val = val.strip()
    if val == "" or val == "--" or val == "N/A":
        return None
    # 尝试 float
    try:
        f = float(val.replace(",", ""))
        if f == int(f) and "." not in val:
            return int(f)
        return f
    except (ValueError, OverflowError):
        return val


# ============================================
# 可用性检测
# ============================================

_available = None

def is_available():
    """检测 npx + westock-data 是否可用（结果缓存）"""
    global _available
    if _available is not None:
        return _available
    try:
        result = subprocess.run(
            ["npx", "--version"],
            capture_output=True, text=True, timeout=10,
        )
        _available = result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        _available = False
    return _available


# ============================================
# K 线数据
# ============================================

def fetch_kline(code, period="day", count=20, adjust="bfq"):
    """获取 K 线数据（支持港股、A股、指数）。

    Args:
        code: 股票代码，支持多种格式：
              港股: '06656' (自动加hk前缀) 或 'hk06656' 或 'hkHSI'
              A股: 'sz300476' 或 'sh600000' (带sz/sh前缀直接透传)
        period: 周期 day/week/month
        count: K 线条数
        adjust: 复权 bfq(不复权)/qfq(前复权)/hfq(后复权)

    Returns:
        list[dict] 或 None: [{'date': '2026-04-16', 'open': 581, 'last': 612.5, ...}, ...]
    """
    if not is_available():
        return None

    # 智能前缀：sz/sh 开头的直接透传（A股），hk 开头的直接用，纯数字加 hk
    if code.startswith("sz") or code.startswith("sh"):
        full_code = code  # A股代码直接透传
    elif code.startswith("hk"):
        full_code = code  # 港股代码或指数
    else:
        full_code = f"hk{code.zfill(5)}"  # 纯数字默认港股

    cache_key = f"kline:{full_code}:{period}:{count}:{adjust}"
    if cache_key in _cache:
        return _cache[cache_key]

    args = ["kline", full_code, period, str(count)]
    if adjust and adjust != "bfq":
        args.append(adjust)

    output = _run_cli(args)
    rows = parse_markdown_table(output)
    if rows:
        _cache[cache_key] = rows
    return rows or None


def fetch_kline_batch(codes, period="day", count=20):
    """批量获取 K 线（逗号分隔，最多 5 只）。

    Args:
        codes: ['06656', '03277', ...]
        period: day/week/month
        count: K 线条数

    Returns:
        dict: {'06656': [kline_rows], '03277': [kline_rows], ...} 或 None
    """
    if not is_available() or not codes:
        return None

    hk_codes = [c if c.startswith("hk") else f"hk{c.zfill(5)}" for c in codes]
    joined = ",".join(hk_codes)

    output = _run_cli(["kline", joined, period, str(count)])
    if not output:
        return None

    # 批量查询返回 BatchResult JSON 或多段 Markdown
    # westock-data 批量 K 线返回多个 Markdown 表，按 code 分段
    # 简化处理：如果返回有效，尝试解析
    rows = parse_markdown_table(output)
    if not rows:
        return None

    # 按 code 分组（如果有 code 列）
    if "code" in rows[0]:
        result = {}
        for row in rows:
            c = str(row.get("code", "")).replace("hk", "")
            result.setdefault(c, []).append(row)
        return result

    # 如果没有 code 列（单股返回格式），直接返回第一个
    if len(codes) == 1:
        return {codes[0].lstrip("0").zfill(5): rows}

    return None


# ============================================
# 恒生指数月度数据
# ============================================

def fetch_hsi_monthly(months=12):
    """获取恒生指数月度涨跌幅。

    Args:
        months: 获取最近几个月的数据

    Returns:
        dict 或 None: {'2026-04': -5.7, '2026-03': 3.2, ...}
    """
    if not is_available():
        return None

    cache_key = f"hsi_monthly:{months}"
    if cache_key in _cache:
        return _cache[cache_key]

    rows = fetch_kline(HSI_CODE, period="month", count=months)
    if not rows:
        return None

    result = {}
    for row in rows:
        date_str = row.get("date", "")
        open_price = row.get("open")
        close_price = row.get("last")

        if not date_str or open_price is None or close_price is None:
            continue
        if open_price == 0:
            continue

        # 月度涨跌幅 = (收盘 - 开盘) / 开盘 * 100
        monthly_return = round((close_price - open_price) / open_price * 100, 2)

        # 提取 YYYY-MM
        parts = date_str.split("-")
        if len(parts) >= 2:
            ym_key = f"{parts[0]}-{parts[1]}"
            result[ym_key] = monthly_return

    if result:
        _cache[cache_key] = result
    return result or None


# ============================================
# 公司简况
# ============================================

def fetch_profile(code):
    """获取港股公司简况。

    Args:
        code: 港股代码，如 '06656'

    Returns:
        dict 或 None: {'name': '思格新能', 'listedDate': '2026-04-16', 'industry': '工业', ...}
    """
    if not is_available():
        return None

    hk_code = f"hk{code.zfill(5)}"
    cache_key = f"profile:{hk_code}"
    if cache_key in _cache:
        return _cache[cache_key]

    output = _run_cli(["profile", hk_code])
    rows = parse_markdown_table(output)
    if rows:
        _cache[cache_key] = rows[0]
        return rows[0]
    return None


# ============================================
# 港股资金流向
# ============================================

def fetch_hkfund(code, date=None):
    """获取港股资金流向。

    Args:
        code: 港股代码
        date: 可选，指定日期 'YYYY-MM-DD'

    Returns:
        dict 或 None: {'MainNetFlow': 180793000, 'TotalNetFlow': 183652000, ...}
    """
    if not is_available():
        return None

    hk_code = f"hk{code.zfill(5)}"
    args = ["hkfund", hk_code]
    if date:
        args.append(date)

    output = _run_cli(args)
    rows = parse_markdown_table(output)
    return rows[0] if rows else None


# ============================================
# 财务数据
# ============================================

def fetch_finance(code, periods=1, report_type=None):
    """获取港股财务报表。

    Args:
        code: 港股代码
        periods: 获取几期
        report_type: 可选 zhsy(综合损益)/zcfz(资产负债)/xjll(现金流)

    Returns:
        dict 或 None: 解析后的财务数据
    """
    if not is_available():
        return None

    hk_code = f"hk{code.zfill(5)}"
    args = ["finance", hk_code]
    if report_type:
        args.append(report_type)
    args.append(str(periods))

    output = _run_cli(args, timeout=45)
    if not output:
        return None

    # 财务数据可能包含多个表（zhsy + zcfz + xjll），按 **标题** 分段
    sections = {}
    current_section = "default"
    current_lines = []

    for line in output.split("\n"):
        stripped = line.strip()
        if stripped.startswith("**") and stripped.endswith("**"):
            if current_lines:
                rows = parse_markdown_table("\n".join(current_lines))
                if rows:
                    sections[current_section] = rows
            current_section = stripped.strip("*").strip()
            current_lines = []
        else:
            current_lines.append(line)

    # 处理最后一段
    if current_lines:
        rows = parse_markdown_table("\n".join(current_lines))
        if rows:
            sections[current_section] = rows

    return sections if sections else None


# ============================================
# IPO 日历
# ============================================

def fetch_ipo_calendar(market="hk", days=90):
    """获取港股新股日历。

    Args:
        market: 市场 hs/hk/us
        days: 天数

    Returns:
        list[dict] 或 None: [{'stage': '今日上市', 'code': '06656', 'name': '思格新能', ...}]
    """
    if not is_available():
        return None

    cache_key = f"ipo:{market}:{days}"
    if cache_key in _cache:
        return _cache[cache_key]

    output = _run_cli(["ipo", market, str(days)])
    rows = parse_markdown_table(output)
    if rows:
        _cache[cache_key] = rows
    return rows or None


# ============================================
# 股票搜索
# ============================================

def search_stock(keyword):
    """搜索股票。

    Args:
        keyword: 关键词（股票名称/代码）

    Returns:
        list[dict] 或 None: [{'code': 'hk06656', 'name': '思格新能', 'type': 'GP'}]
    """
    if not is_available():
        return None

    output = _run_cli(["search", keyword])
    return parse_markdown_table(output) or None


# ============================================
# 核心：K 线 → dayN 收益率计算
# ============================================

def compute_day_returns(code, ipo_price, listing_date=None):
    """从 K 线数据计算上市后各交易日收益率（相对发行价）。

    Args:
        code: 港股代码
        ipo_price: 发行价（港元）
        listing_date: 上市日期 'YYYY-MM-DD'（可选，用于过滤）

    Returns:
        dict 或 None: {
            'day1_return': 首日涨跌幅%,
            'day1_open': 首日开盘价,
            'day1_close': 首日收盘价,
            'day1_high': 首日最高涨跌幅%,
            'day1_low': 首日最低涨跌幅%,
            'day1_volume': 首日成交量,
            'day1_amount': 首日成交额,
            'day1_turnover': 首日换手率%,
            'day2_return': float, 'day3_return': float,
            'day5_return': float, 'day7_return': float, 'day10_return': float,
            'kline_raw': [原始K线列表],
        }
    """
    kline = fetch_kline(code, period="day", count=30)
    if not kline or ipo_price is None or ipo_price <= 0:
        return None

    # 按日期排序（升序）
    kline_sorted = sorted(kline, key=lambda x: x.get("date", ""))

    # 如果有上市日期，从上市日开始截取
    if listing_date:
        kline_sorted = [k for k in kline_sorted if k.get("date", "") >= listing_date]

    if not kline_sorted:
        return None

    result = {"kline_raw": kline_sorted}

    # 交易日映射：day1=第1个交易日, day2=第2个, day3=第3个, day5=第5个, day7=第7个, day10=第10个
    day_map = {1: "day1", 2: "day2", 3: "day3", 5: "day5", 7: "day7", 10: "day10"}

    for idx, kline_row in enumerate(kline_sorted):
        trading_day = idx + 1  # 第几个交易日
        close = kline_row.get("last")
        high = kline_row.get("high")
        low = kline_row.get("low")
        open_p = kline_row.get("open")

        if close is None:
            continue

        ret = round((close - ipo_price) / ipo_price * 100, 2)
        high_ret = round((high - ipo_price) / ipo_price * 100, 2) if high else None
        low_ret = round((low - ipo_price) / ipo_price * 100, 2) if low else None

        if trading_day in day_map:
            day_key = day_map[trading_day]
            result[f"{day_key}_return"] = ret
            if high_ret is not None:
                result[f"{day_key}_high"] = high_ret
            if low_ret is not None:
                result[f"{day_key}_low"] = low_ret

        # 首日额外信息
        if trading_day == 1:
            result["day1_open"] = open_p
            result["day1_close"] = close
            result["day1_volume"] = kline_row.get("volume")
            result["day1_amount"] = kline_row.get("amount")
            result["day1_turnover"] = kline_row.get("exchange")
            result["day1_date"] = kline_row.get("date")

        if trading_day >= 10:
            break

    return result


def compute_latest_price(code):
    """获取最新收盘价和涨跌幅。

    Args:
        code: 港股代码

    Returns:
        dict 或 None: {'date': '2026-04-16', 'close': 612.5, 'open': 581, 'high': 612.5, 'low': 560.5, 'volume': ..., 'turnover': ...}
    """
    kline = fetch_kline(code, period="day", count=1)
    if not kline:
        return None

    row = kline[0]
    return {
        "date": row.get("date"),
        "close": row.get("last"),
        "open": row.get("open"),
        "high": row.get("high"),
        "low": row.get("low"),
        "volume": row.get("volume"),
        "amount": row.get("amount"),
        "turnover": row.get("exchange"),
    }


# ============================================
# 便捷：一键获取新股完整数据
# ============================================

def fetch_ipo_full_data(code, ipo_price=None, listing_date=None):
    """一键获取新股完整数据：K线收益率 + 公司简况 + 资金流向。

    Args:
        code: 港股代码
        ipo_price: 发行价（如提供则计算 dayN 收益率）
        listing_date: 上市日期

    Returns:
        dict: {
            'day_returns': {...},  # compute_day_returns 结果
            'profile': {...},      # fetch_profile 结果
            'fund': {...},         # fetch_hkfund 结果
            'latest': {...},       # compute_latest_price 结果
        }
    """
    result = {}

    if ipo_price and ipo_price > 0:
        result["day_returns"] = compute_day_returns(code, ipo_price, listing_date)

    result["profile"] = fetch_profile(code)
    result["fund"] = fetch_hkfund(code)
    result["latest"] = compute_latest_price(code)

    return result


def clear_cache():
    """清除进程内缓存"""
    global _cache
    _cache = {}


# ============================================
# 测试入口
# ============================================

if __name__ == "__main__":
    import sys

    print("=== westock-data fetcher 测试 ===\n")

    # 1. 可用性检测
    avail = is_available()
    print(f"1. westock-data 可用: {avail}")
    if not avail:
        print("   ❌ npx 不可用，无法继续测试")
        sys.exit(1)

    # 2. 恒指月度
    print("\n2. 恒指月度数据:")
    hsi = fetch_hsi_monthly(6)
    if hsi:
        for k, v in sorted(hsi.items()):
            print(f"   {k}: {v:+.2f}%")
    else:
        print("   ❌ 获取失败")

    # 3. 思格新能 K 线
    print("\n3. 思格新能 06656 K线 (5日):")
    kl = fetch_kline("06656", count=5)
    if kl:
        for row in kl:
            print(f"   {row.get('date')}: 开{row.get('open')} 收{row.get('last')} "
                  f"高{row.get('high')} 低{row.get('low')} 换手{row.get('exchange')}%")
    else:
        print("   ❌ 获取失败")

    # 4. dayN 收益率（思格新能，发行价 324.20）
    print("\n4. 思格新能 dayN 收益率 (发行价 324.20):")
    dr = compute_day_returns("06656", 324.20, "2026-04-16")
    if dr:
        for k in ["day1_return", "day1_high", "day1_low", "day1_turnover",
                   "day2_return", "day3_return", "day5_return", "day7_return", "day10_return"]:
            v = dr.get(k)
            if v is not None:
                print(f"   {k}: {v}")
    else:
        print("   ❌ 获取失败")

    # 5. 公司简况
    print("\n5. 思格新能 公司简况:")
    p = fetch_profile("06656")
    if p:
        print(f"   名称: {p.get('name')}")
        print(f"   上市日: {p.get('listedDate')}")
        print(f"   行业: {p.get('industry')}")
    else:
        print("   ❌ 获取失败")

    # 6. 资金流向
    print("\n6. 思格新能 资金流向:")
    fund = fetch_hkfund("06656")
    if fund:
        print(f"   主力净流入: {fund.get('MainNetFlow')}")
        print(f"   总净流入: {fund.get('TotalNetFlow')}")
    else:
        print("   ❌ 获取失败")

    print("\n=== 测试完成 ===")
