#!/usr/bin/env python3
"""一次性脚本：从 sweet-spot 的 data.py 生成 reversal 的增强版 data.py
基于已有数据的统计规律推导新字段，后续会用爬虫替换为真实数据。

推导规则：
1. dark_high: 暗盘最高 ≈ max(dark_return + |dark_return|*0.15, dark_return + 3)
2. dark_low:  暗盘最低 ≈ min(dark_return - |dark_return|*0.15, dark_return - 3)
3. day1_high: 首日最高 ≈ max(day1_return + |day1_return|*0.12, day1_return + 2)
4. day1_low:  首日最低 ≈ min(day1_return - |day1_return|*0.12, day1_return - 2)
5. day2_return: 插值 day1 和 day3 之间，加随机扰动
6. day7_return: 插值 day5 和 趋势延伸，加随机扰动
7. day10_return: 从 day7 趋势延伸，加随机扰动
8. day1_turnover: 基于募资规模估算（小盘高换手）
9. day1_volume_hkd: 基于募资规模和首日涨幅估算
"""
import sys, os, math, random

# 添加 sweet-spot 的 scripts 目录到路径
sys.path.insert(0, os.path.expanduser("~/.workbuddy/skills/hk-ipo-sweet-spot/scripts"))
from data import ipo_data, hsi_monthly

random.seed(42)  # 可复现

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

def estimate_dark_high(d):
    dr = d["dark_return"]
    if dr is None: return None
    spread = max(abs(dr) * 0.15, 3.0)
    return round(dr + spread + random.uniform(0, spread * 0.3), 2)

def estimate_dark_low(d):
    dr = d["dark_return"]
    if dr is None: return None
    spread = max(abs(dr) * 0.15, 3.0)
    return round(dr - spread - random.uniform(0, spread * 0.3), 2)

def estimate_day1_high(d):
    r = d["day1_return"]
    spread = max(abs(r) * 0.12, 2.0)
    return round(r + spread + random.uniform(0, spread * 0.2), 2)

def estimate_day1_low(d):
    r = d["day1_return"]
    spread = max(abs(r) * 0.12, 2.0)
    return round(r - spread - random.uniform(0, spread * 0.2), 2)

def estimate_day2(d):
    d1 = d["day1_return"]
    d3 = d.get("day3_return")
    if d3 is None: return round(d1 * 0.95 + random.uniform(-2, 2), 2)
    # 线性插值 + 随机噪声
    base = d1 + (d3 - d1) * 0.5
    noise = random.uniform(-3, 3)
    return round(base + noise, 2)

def estimate_day7(d):
    d5 = d.get("day5_return")
    d3 = d.get("day3_return")
    if d5 is None: return None
    if d3 is None: return round(d5 * 0.92 + random.uniform(-3, 3), 2)
    # 趋势延伸：day5→day7 ≈ day3→day5 的趋势继续
    trend = (d5 - d3) * 0.6  # 衰减
    noise = random.uniform(-4, 4)
    return round(d5 + trend + noise, 2)

def estimate_day10(d):
    d7 = d.get("_day7_return")
    d5 = d.get("day5_return")
    if d7 is None and d5 is None: return None
    base = d7 if d7 is not None else d5
    if d5 is not None and d7 is not None:
        trend = (d7 - d5) * 0.5
    else:
        trend = 0
    noise = random.uniform(-5, 5)
    return round(base + trend + noise, 2)

def estimate_turnover(d):
    """首日换手率估算：小盘股高换手"""
    f = d["fundraising"]
    base = 60 if f < 5 else 40 if f < 20 else 25 if f < 50 else 15 if f < 100 else 8
    # 高涨幅增加换手
    r = abs(d["day1_return"])
    mult = 1.0 + r / 100 * 0.5
    noise = random.uniform(0.8, 1.2)
    return round(base * mult * noise, 1)

def estimate_volume(d):
    """首日成交额(百万港元)估算"""
    f = d["fundraising"]  # 亿港元
    # 大盘股成交额高，首日成交约 募资额的 5%-30%
    ratio = 0.25 if f < 5 else 0.15 if f < 20 else 0.10 if f < 50 else 0.07 if f < 100 else 0.05
    r = abs(d["day1_return"])
    mult = 1.0 + r / 100 * 0.8
    noise = random.uniform(0.7, 1.3)
    volume_yi = f * ratio * mult * noise
    return round(volume_yi * 100, 1)  # 亿→百万 (*100)

def enhance_record(d):
    """增强单条记录"""
    e = dict(d)  # 复制
    
    # 暗盘高低价
    e["dark_high"] = estimate_dark_high(d)
    e["dark_low"] = estimate_dark_low(d)
    
    # 首日高低价
    e["day1_high"] = estimate_day1_high(d)
    e["day1_low"] = estimate_day1_low(d)
    
    # day2
    e["day2_return"] = estimate_day2(d)
    
    # day7
    e["_day7_return"] = estimate_day7(d)
    e["day7_return"] = e["_day7_return"]
    
    # day10 (需要先有day7)
    e["day10_return"] = estimate_day10(e)
    
    # 清理临时字段
    if "_day7_return" in e:
        del e["_day7_return"]
    
    # 成交量
    e["day1_turnover"] = estimate_turnover(d)
    e["day1_volume_hkd"] = estimate_volume(d)
    
    return e


# ============================================
# 期望涨幅推算 (数据驱动)
# ============================================

def estimate_expected_returns(enhanced_data):
    """基于全量数据集的分档统计映射，为每只股票推算 expected_return
    
    逻辑：
    1. 按超购区间分档，计算各档首日涨幅均值作为基准
    2. 有基石 vs 无基石的修正
    3. 行业目标编码修正（各行业首日均值偏差）
    4. 募资规模修正（大盘股折价）
    5. 综合加权
    """
    # === Step 1: 按超购区间分档计算基准 ===
    sub_ranges = [
        (0, 20, "< 20倍"),
        (20, 100, "20-100倍"),
        (100, 500, "100-500倍"),
        (500, 2000, "500-2000倍"),
        (2000, 5000, "2000-5000倍"),
        (5000, 999999, "> 5000倍"),
    ]
    
    sub_baselines = {}
    for lo, hi, label in sub_ranges:
        group = [d for d in enhanced_data
                 if d.get("subscription_mult") is not None
                 and lo <= d["subscription_mult"] < hi
                 and d.get("day1_return") is not None]
        if group:
            avg = sum(d["day1_return"] for d in group) / len(group)
            sub_baselines[(lo, hi)] = avg
        else:
            sub_baselines[(lo, hi)] = 0
    
    # === Step 2: 基石修正 ===
    cs_yes = [d for d in enhanced_data if d.get("has_cornerstone") and d.get("day1_return") is not None]
    cs_no = [d for d in enhanced_data if not d.get("has_cornerstone") and d.get("day1_return") is not None]
    cs_avg = sum(d["day1_return"] for d in cs_yes) / len(cs_yes) if cs_yes else 0
    no_cs_avg = sum(d["day1_return"] for d in cs_no) / len(cs_no) if cs_no else 0
    global_avg = sum(d["day1_return"] for d in enhanced_data if d.get("day1_return") is not None) / max(1, sum(1 for d in enhanced_data if d.get("day1_return") is not None))
    cs_bonus = cs_avg - global_avg  # 有基石相对全局均值的偏差
    no_cs_penalty = no_cs_avg - global_avg
    
    # === Step 3: 行业目标编码修正 ===
    cat_groups = {}
    for d in enhanced_data:
        cat = d.get("category", "其他")
        if d.get("day1_return") is None:
            continue
        cat_groups.setdefault(cat, []).append(d["day1_return"])
    cat_offsets = {}
    for cat, vals in cat_groups.items():
        cat_offsets[cat] = sum(vals) / len(vals) - global_avg if vals else 0
    
    # === Step 4: 募资规模修正 ===
    def fundraising_adj(f):
        if f >= 100: return -12  # 超大盘折价
        if f >= 50: return -8
        if f >= 20: return -3
        if f >= 10: return 0
        if f >= 5: return 2
        return 5  # 小盘股溢价
    
    # === Step 5: 综合计算 ===
    for d in enhanced_data:
        sub = d.get("subscription_mult", 1)
        
        # 基准：超购区间均值
        baseline = 0
        for (lo, hi), avg in sub_baselines.items():
            if lo <= sub < hi:
                baseline = avg
                break
        
        # 修正
        cs_adj = cs_bonus if d.get("has_cornerstone") else no_cs_penalty
        cat_adj = cat_offsets.get(d.get("category", "其他"), 0)
        fund_adj = fundraising_adj(d.get("fundraising", 5))
        
        # 加权合成：基准权重60% + 修正项40%
        expected = baseline * 0.6 + (baseline + cs_adj + cat_adj + fund_adj) * 0.4
        
        d["expected_return"] = round(expected, 1)
        
        # 计算偏差
        dr = d.get("dark_return")
        if dr is not None:
            d["deviation"] = round(dr - d["expected_return"], 1)
        else:
            d["deviation"] = None
    
    return enhanced_data

def format_val(v):
    if v is None: return "None"
    if isinstance(v, bool): return str(v)
    if isinstance(v, str): return f'"{v}"'
    return str(v)

def format_record(e):
    """格式化一条记录为Python dict字面量"""
    fields = [
        "name", "code", "date", "subscription_mult", "fundraising",
        "has_cornerstone", "category",
        "dark_return", "dark_high", "dark_low",
        "day1_return", "day1_high", "day1_low",
        "day2_return", "day3_return", "day5_return", "day7_return", "day10_return",
        "day1_turnover", "day1_volume_hkd",
        "expected_return", "deviation",
    ]
    parts = []
    for f in fields:
        v = e.get(f)
        parts.append(f'"{f}": {format_val(v)}')
    return "    {" + ", ".join(parts) + "}"

def main():
    enhanced = [enhance_record(d) for d in ipo_data]
    
    # 计算 expected_return 和 deviation
    estimate_expected_returns(enhanced)
    
    # 输出 Python 文件
    lines = []
    lines.append('#!/usr/bin/env python3')
    lines.append('"""港股新股暗盘反转猎手 - 增强版数据集 V2 (含期望偏差)')
    lines.append('数据来源：东方财富、华盛通、富途牛牛、财联社等公开数据')
    lines.append('基础字段继承自 hk-ipo-sweet-spot，新增字段（标注 ★）为统计估算值，')
    lines.append('后续将通过爬虫替换为真实数据。')
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
    lines.append('  ★expected_return: 预期首日涨幅(%) — 基于超购/基石/行业/募资分档统计映射')
    lines.append('  ★deviation: 期望偏差(%) = dark_return - expected_return')
    lines.append('"""')
    lines.append('')
    lines.append('ipo_data = [')
    
    # 按季度分组
    current_section = ""
    for e in enhanced:
        date = e["date"]
        y = int(date[:4])
        m = int(date[5:7])
        q = (m - 1) // 3 + 1
        h = "H1" if q <= 2 else "H2"
        section = f"{y} {'Q'+str(q)}" if y >= 2025 else f"{y} {h}"
        if m >= 7 and y == 2024:
            section = "2024 H2"
        
        if section != current_section:
            current_section = section
            lines.append(f'    # ==================== {section} ====================')
        
        lines.append(format_record(e) + ",")
    
    lines.append(']')
    lines.append('')
    
    # HSI monthly
    lines.append('# ============================================')
    lines.append('# 恒生指数月度涨跌幅 (%)')
    lines.append('# ============================================')
    lines.append('hsi_monthly = {')
    for k in sorted(hsi_monthly.keys()):
        lines.append(f'    "{k}": {hsi_monthly[k]},')
    lines.append('}')
    
    # 写文件
    out_path = os.path.expanduser("~/.workbuddy/skills/hk-ipo-reversal/scripts/data.py")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    
    print(f"✅ 生成增强版数据集 V2: {out_path}")
    print(f"   总记录数: {len(enhanced)}")
    
    # 统计
    dark_down = [e for e in enhanced if e.get("dark_return") is not None and e["dark_return"] < 0]
    dev_neg = [e for e in enhanced if e.get("deviation") is not None and e["deviation"] < 0]
    dev_neg10 = [e for e in enhanced if e.get("deviation") is not None and e["deviation"] <= -10]
    dev_neg15 = [e for e in enhanced if e.get("deviation") is not None and e["deviation"] <= -15]
    
    print(f"   暗盘下跌: {len(dark_down)} 只")
    print(f"   偏差为负(不及预期): {len(dev_neg)} 只")
    print(f"   偏差 ≤ -10: {len(dev_neg10)} 只")
    print(f"   偏差 ≤ -15: {len(dev_neg15)} 只")
    
    # 输出偏差分布
    print(f"\n📊 偏差分布:")
    for e in sorted(enhanced, key=lambda x: x.get("deviation") or 0):
        dev = e.get("deviation")
        exp = e.get("expected_return")
        dr = e.get("dark_return")
        if dev is not None and dev <= -10:
            print(f"   {e['name']:12s} ({e['code']}) 暗盘{dr:+6.1f}% 预期{exp:+6.1f}% 偏差{dev:+6.1f}%")
    
    # 潜力释放案例
    print(f"\n🚀 潜力释放候选(暗盘>0且day10-暗盘>15pp):")
    for e in enhanced:
        dr = e.get("dark_return", 0)
        d10 = e.get("day10_return")
        if dr > 0 and d10 is not None and d10 - dr > 15:
            print(f"   {e['name']:12s} ({e['code']}) 暗盘{dr:+.0f}% → day10{d10:+.0f}% 增幅{d10-dr:+.0f}pp")

if __name__ == "__main__":
    main()
