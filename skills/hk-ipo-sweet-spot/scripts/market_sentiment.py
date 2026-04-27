#!/usr/bin/env python3
"""市场情绪修正模块 — V4.0 P2（超购爆发 + 暗盘冲高回落）
在模型基础预测之上，叠加动态市场环境因子修正。

设计思路：
  模型（engine.py）基于训练集的静态基本面（超购/基石/行业/募资）给出基准预测。
  但暗盘和首日的实际表现还受「动态市场因子」驱动：
    1. 近期新股情绪指数 — 最近N只新股的暗盘/首日超预期程度
    2. AH溢价因子 — AH股专属，A股实时价格锚定H股天花板
    3. A股联动因子 — 招股期间A股涨跌幅的情绪传导
    4. 恒指短期动量 — 大盘近期涨跌对新股的系统性影响
    5. 赛道叙事溢价 — (P1) 同赛道近期表现vs全量的超额
    6. 超购爆发弹性 — (P2) >3000x超购的非线性爆发修正（额外叠加）
    7. 暗盘冲高回落 — (P2) 暗盘过热→首日回落的模式识别（额外惩罚）

  修正公式：
    adjusted_return = base_return + Σ(factor_i × weight_i) + explosion_bonus + crash_penalty

技术约束：
  - 纯 Python 3 标准库，零依赖
  - 所有外部数据通过 fetcher.py 获取，不可用时静默降级
"""
import math


# ============================================
# 因子1: 近期新股情绪指数
# ============================================

def compute_ipo_sentiment(ipo_data, n_recent=5):
    """计算近期新股情绪指数。

    思路：取最近 n_recent 只已有暗盘数据的新股，
    计算它们的「超预期倍数」均值。

    Returns:
        dict: {
            "sentiment_ratio": float,  # 情绪倍数（>1=热, <1=冷）
            "sentiment_adj": float,    # 情绪修正值（百分点）
            "recent_avg_dark": float,
            "history_avg_dark": float,
            "n_recent": int,
            "recent_stocks": list,
        }
    """
    with_dark = [d for d in ipo_data if d.get("dark_return") is not None and d.get("date")]
    with_dark.sort(key=lambda x: x["date"], reverse=True)

    if len(with_dark) < 5:
        return _default_sentiment()

    recent = with_dark[:n_recent]
    history = with_dark[n_recent:]

    recent_avg = sum(d["dark_return"] for d in recent) / len(recent)
    history_avg = sum(d["dark_return"] for d in history) / len(history) if history else recent_avg

    if history_avg > 0:
        sentiment_ratio = recent_avg / history_avg
    elif history_avg == 0:
        sentiment_ratio = 1.5 if recent_avg > 0 else 0.5
    else:
        sentiment_ratio = 2.0 if recent_avg > 0 else 0.8

    sentiment_adj = 20.0 * math.log(max(sentiment_ratio, 0.1))
    sentiment_adj = max(-30.0, min(40.0, sentiment_adj))

    recent_stocks = [{"name": d.get("name", ""), "dark_return": d["dark_return"],
                      "day1_return": d.get("day1_return")} for d in recent]

    return {
        "sentiment_ratio": round(sentiment_ratio, 3),
        "sentiment_adj": round(sentiment_adj, 1),
        "recent_avg_dark": round(recent_avg, 1),
        "history_avg_dark": round(history_avg, 1),
        "n_recent": len(recent),
        "recent_stocks": recent_stocks,
    }


def _default_sentiment():
    return {
        "sentiment_ratio": 1.0, "sentiment_adj": 0.0,
        "recent_avg_dark": 0.0, "history_avg_dark": 0.0,
        "n_recent": 0, "recent_stocks": [],
    }


# ============================================
# 因子2: AH溢价因子
# ============================================

def compute_ah_premium_factor(a_share_price_cny, h_ipo_price_hkd, cny_hkd_rate=None, fundraising=None):
    """计算 AH 溢价因子。

    V4.0 P2: 加入大盘AH股的募资规模衰减
    """
    if not a_share_price_cny or not h_ipo_price_hkd or h_ipo_price_hkd <= 0:
        return None

    if cny_hkd_rate is None:
        cny_hkd_rate = 1.099

    a_price_hkd = a_share_price_cny * cny_hkd_rate
    discount_pct = (a_price_hkd / h_ipo_price_hkd - 1) * 100

    if discount_pct > 0:
        ah_adj = 2.0 * math.sqrt(discount_pct)
        ah_adj = min(ah_adj, 25.0)
        # [P2] 大盘衰减：募资>30亿时打折
        if fundraising and fundraising > 30:
            scale = min(1.0, 30.0 / fundraising)
            ah_adj *= scale
    else:
        ah_adj = max(-15.0, discount_pct * 0.3)

    return {
        "a_price_hkd": round(a_price_hkd, 1),
        "h_ipo_price": h_ipo_price_hkd,
        "discount_pct": round(discount_pct, 1),
        "ceiling_return": round(discount_pct, 1),
        "ah_adj": round(ah_adj, 1),
    }


# ============================================
# 因子3: A股联动因子
# ============================================

def compute_a_share_momentum(a_kline_data, subscription_start_date=None, n_days=5):
    """计算 A 股招股期间的涨跌幅动量。"""
    if not a_kline_data or len(a_kline_data) < 2:
        return None

    kline = sorted(a_kline_data, key=lambda x: x.get("date", ""))

    if subscription_start_date:
        before_sub = [k for k in kline if k.get("date", "") < subscription_start_date]
        start_price = before_sub[-1].get("last") if before_sub else kline[0].get("last")
        period_label = "招股期"
    else:
        start_idx = max(0, len(kline) - n_days - 1)
        start_price = kline[start_idx].get("last")
        period_label = f"近{n_days}日"

    end_price = kline[-1].get("last")
    if not start_price or not end_price or start_price <= 0:
        return None

    momentum_pct = (end_price - start_price) / start_price * 100
    a_momentum_adj = momentum_pct * 0.5
    a_momentum_adj = max(-15.0, min(20.0, a_momentum_adj))

    return {
        "momentum_pct": round(momentum_pct, 1),
        "a_momentum_adj": round(a_momentum_adj, 1),
        "period": period_label,
        "a_close": end_price,
        "a_start": start_price,
    }


# ============================================
# 因子4: 恒指短期动量
# ============================================

def compute_hsi_short_momentum(hsi_kline_data, n_days=5):
    """计算恒指短期动量。"""
    if not hsi_kline_data or len(hsi_kline_data) < 2:
        return None

    kline = sorted(hsi_kline_data, key=lambda x: x.get("date", ""))
    if len(kline) < n_days + 1:
        start_price = kline[0].get("last") or kline[0].get("open")
    else:
        start_price = kline[-(n_days + 1)].get("last")

    end_price = kline[-1].get("last")
    if not start_price or not end_price or start_price <= 0:
        return None

    hsi_momentum_pct = (end_price - start_price) / start_price * 100
    hsi_adj = hsi_momentum_pct * 0.6
    hsi_adj = max(-8.0, min(10.0, hsi_adj))

    return {
        "hsi_momentum_pct": round(hsi_momentum_pct, 1),
        "hsi_adj": round(hsi_adj, 1),
        "hsi_close": end_price,
        "n_days": n_days,
    }


# ============================================
# 因子5: 赛道叙事溢价 (P1)
# ============================================

_NARRATIVE_GROUPS = {
    "AI": ["AI", "SaaS", "软件", "云计算", "数据", "光计算", "大模型"],
    "半导体": ["半导体", "芯片", "CMOS", "GPU", "光"],
    "医药": ["医药", "生物科技", "创新药", "医疗器械", "CXO", "生物", "医疗", "医疗AI"],
    "新能源": ["新能源", "储能", "电池", "光伏"],
    "科技": ["科技", "机器人", "自动驾驶", "互联网"],
    "消费": ["消费", "餐饮", "零售", "电商", "食品"],
    "制造": ["制造", "PCB", "汽车", "工业", "材料"],
}


def _get_narrative_group(category):
    for group, keywords in _NARRATIVE_GROUPS.items():
        for kw in keywords:
            if kw in category:
                return group
    return "其他"


def compute_narrative_premium(ipo_data, target_category, n_recent=3):
    """计算赛道叙事溢价因子。"""
    target_group = _get_narrative_group(target_category)

    with_dark = [d for d in ipo_data if d.get("dark_return") is not None and d.get("date")]
    if len(with_dark) < 5:
        return _default_narrative(target_group)

    overall_avg = sum(d["dark_return"] for d in with_dark) / len(with_dark)

    same_sector = [d for d in with_dark if _get_narrative_group(d.get("category", "")) == target_group]
    same_sector.sort(key=lambda x: x["date"], reverse=True)

    if not same_sector:
        return _default_narrative(target_group)

    recent = same_sector[:n_recent]
    sector_avg = sum(d["dark_return"] for d in recent) / len(recent)
    sector_premium = sector_avg - overall_avg

    if sector_premium > 0:
        narrative_adj = 4.0 * math.sqrt(sector_premium)
        narrative_adj = min(narrative_adj, 40.0)
    else:
        narrative_adj = sector_premium * 0.3
        narrative_adj = max(narrative_adj, -15.0)

    same_sector_stocks = [{"name": d.get("name", ""), "dark_return": d["dark_return"],
                           "category": d.get("category", "")} for d in recent]

    return {
        "narrative_group": target_group,
        "same_sector_avg_dark": round(sector_avg, 1),
        "overall_avg_dark": round(overall_avg, 1),
        "sector_premium": round(sector_premium, 1),
        "narrative_adj": round(narrative_adj, 1),
        "same_sector_stocks": same_sector_stocks,
        "n_sector": len(same_sector),
    }


def _default_narrative(group):
    return {
        "narrative_group": group, "same_sector_avg_dark": 0,
        "overall_avg_dark": 0, "sector_premium": 0,
        "narrative_adj": 0, "same_sector_stocks": [], "n_sector": 0,
    }


# ============================================
# 因子6: 超购爆发弹性 (P2) — 额外叠加，不走权重
# ============================================

_SUB_EXPLOSION_THRESHOLD = 3000

def compute_subscription_explosion(subscription_mult, ipo_data, target_category=None):
    """超购>3000x时的非线性爆发修正。

    背景：log(sub)压缩了3000-12000x的差异。
    此因子直接额外叠加到最终修正上（不经过权重归一化）。
    """
    if subscription_mult < _SUB_EXPLOSION_THRESHOLD:
        return None

    excess = subscription_mult - _SUB_EXPLOSION_THRESHOLD
    # 基础弹性：3000→0, 4000→+7, 5000→+9.9, 8000→+15.7, 12000→+21
    base_boost = 7.0 * math.sqrt(excess / 1000.0)
    base_boost = min(base_boost, 45.0)

    narrative_group = _get_narrative_group(target_category or "其他")

    # 从数据集统计赛道乘数
    high_sub_same = [
        d for d in ipo_data
        if d.get("subscription_mult", 0) >= 2000
        and d.get("day1_return") is not None
        and _get_narrative_group(d.get("category", "")) == narrative_group
    ]
    high_sub_all = [
        d for d in ipo_data
        if d.get("subscription_mult", 0) >= 2000
        and d.get("day1_return") is not None
    ]

    if high_sub_same and len(high_sub_same) >= 3:
        # 排除最低值（翻车案例）
        sr = sorted([d["day1_return"] for d in high_sub_same])
        trimmed = sr[1:] if len(sr) > 3 else sr
        sector_avg = sum(trimmed) / len(trimmed)

        ar = sorted([d["day1_return"] for d in high_sub_all])
        all_trimmed = ar[1:-1] if len(ar) > 5 else ar
        all_avg = sum(all_trimmed) / len(all_trimmed) if all_trimmed else 50

        sector_multiplier = sector_avg / all_avg if all_avg > 0 else 1.0
        sector_multiplier = max(0.3, min(2.5, sector_multiplier))
    else:
        _SECTOR_MULT = {
            "AI": 2.2, "半导体": 1.8, "医药": 1.4, "新能源": 1.2,
            "科技": 1.0, "消费": 0.7, "制造": 0.3, "其他": 0.4,
        }
        sector_multiplier = _SECTOR_MULT.get(narrative_group, 0.4)

    explosion_adj = base_boost * sector_multiplier
    explosion_adj = min(explosion_adj, 60.0)

    return {
        "subscription_mult": subscription_mult,
        "excess": excess,
        "base_boost": round(base_boost, 1),
        "narrative_group": narrative_group,
        "sector_multiplier": round(sector_multiplier, 2),
        "explosion_adj": round(explosion_adj, 1),
        "n_same_sector": len(high_sub_same),
    }


# ============================================
# 因子7: 暗盘冲高回落模式 (P2) — 额外惩罚
# ============================================

def compute_dark_crash_pattern(dark_return, ipo_data, subscription_mult=None):
    """识别暗盘冲高回落→首日跌破暗盘的模式。

    只在暗盘数据已知时用于修正首日预期。
    """
    if dark_return is None:
        return None

    with_both = [
        d for d in ipo_data
        if d.get("dark_return") is not None
        and d.get("day1_return") is not None
    ]
    if len(with_both) < 10:
        return None

    all_dark = [d["dark_return"] for d in with_both]
    dark_avg = sum(all_dark) / len(all_dark)

    # 历史暗盘回落统计
    crash_cases = [d for d in with_both if d["dark_return"] - d["day1_return"] > 8]
    crash_rate = len(crash_cases) / len(with_both) * 100

    is_crash_risk = False
    crash_penalty = 0.0
    risk_reason = ""

    if dark_return > 0:
        dark_premium = dark_return / max(dark_avg, 1) if dark_avg > 0 else dark_return / 10

        if subscription_mult and subscription_mult < 1000 and dark_return > 80:
            is_crash_risk = True
            crash_penalty = -min(15.0, dark_return * 0.08)
            risk_reason = f"超购仅{subscription_mult:.0f}x但暗盘+{dark_return:.0f}%（炒作风险）"
        elif dark_premium > 3.0 and dark_return > 100:
            is_crash_risk = True
            crash_penalty = -min(12.0, (dark_premium - 3) * 5)
            risk_reason = f"暗盘是均值的{dark_premium:.1f}倍（极端过热）"
        elif dark_premium > 2.0 and dark_return > 50:
            is_crash_risk = True
            crash_penalty = -min(8.0, (dark_premium - 2) * 4)
            risk_reason = f"暗盘是均值的{dark_premium:.1f}倍（中等过热）"

    return {
        "dark_return": dark_return,
        "dark_avg": round(dark_avg, 1),
        "is_crash": is_crash_risk,
        "crash_penalty": round(crash_penalty, 1),
        "risk_reason": risk_reason,
        "crash_rate_historical": round(crash_rate, 1),
    }


# ============================================
# 综合修正引擎
# ============================================

# 基础因子权重（explosion和dark_crash不在此系统内，额外叠加）
_FACTOR_WEIGHTS = {
    "sentiment": 0.25,
    "narrative": 0.20,
    "ah_premium": 0.20,
    "a_momentum": 0.20,
    "hsi_momentum": 0.15,
}


def compute_market_adjustment(
    ipo_data,
    h_ipo_price=None,
    a_share_price_cny=None,
    a_kline=None,
    hsi_kline=None,
    subscription_start=None,
    cny_hkd_rate=None,
    n_recent=5,
    target_category=None,
    subscription_mult=None,
    dark_return=None,
    fundraising=None,
):
    """综合市场情绪修正引擎 V4.0 P2。"""
    is_ah = a_share_price_cny is not None and a_share_price_cny > 0

    # 1. 计算各因子
    sentiment = compute_ipo_sentiment(ipo_data, n_recent)

    narrative = None
    if target_category:
        narrative = compute_narrative_premium(ipo_data, target_category)

    explosion = None
    if subscription_mult and subscription_mult >= _SUB_EXPLOSION_THRESHOLD:
        explosion = compute_subscription_explosion(subscription_mult, ipo_data, target_category)

    dark_crash = None
    if dark_return is not None:
        dark_crash = compute_dark_crash_pattern(dark_return, ipo_data, subscription_mult)

    ah_factor = None
    a_momentum = None
    if is_ah and h_ipo_price:
        ah_factor = compute_ah_premium_factor(a_share_price_cny, h_ipo_price, cny_hkd_rate,
                                               fundraising=fundraising)
        if a_kline:
            a_momentum = compute_a_share_momentum(a_kline, subscription_start)

    hsi_factor = None
    if hsi_kline:
        hsi_factor = compute_hsi_short_momentum(hsi_kline)

    # 2. 权重分配
    weights = dict(_FACTOR_WEIGHTS)

    if not is_ah:
        ah_w = weights["ah_premium"] + weights["a_momentum"]
        weights["ah_premium"] = 0
        weights["a_momentum"] = 0
        weights["narrative"] += ah_w * 0.45
        weights["sentiment"] += ah_w * 0.35
        weights["hsi_momentum"] += ah_w * 0.20
    else:
        if a_momentum is None:
            extra_w = weights["a_momentum"]
            weights["a_momentum"] = 0
            weights["ah_premium"] += extra_w * 0.5
            weights["sentiment"] += extra_w * 0.5

    if narrative is None:
        extra_w = weights["narrative"]
        weights["narrative"] = 0
        weights["sentiment"] += extra_w

    if hsi_factor is None:
        extra_w = weights["hsi_momentum"]
        weights["hsi_momentum"] = 0
        weights["sentiment"] += extra_w

    w_total = sum(weights.values())
    if w_total > 0:
        weights = {k: v / w_total for k, v in weights.items()}

    # 3. 加权汇总（基础因子）
    adj_parts = {}
    adj_parts["sentiment"] = sentiment["sentiment_adj"] * weights.get("sentiment", 0)
    adj_parts["narrative"] = (narrative["narrative_adj"] if narrative else 0) * weights.get("narrative", 0)

    if ah_factor:
        adj_parts["ah_premium"] = ah_factor["ah_adj"] * weights.get("ah_premium", 0)
    else:
        adj_parts["ah_premium"] = 0

    if a_momentum:
        a_adj = a_momentum["a_momentum_adj"]
        if a_adj < 0:
            a_adj *= 1.5
        adj_parts["a_momentum"] = a_adj * weights.get("a_momentum", 0)
    else:
        adj_parts["a_momentum"] = 0

    if hsi_factor:
        adj_parts["hsi_momentum"] = hsi_factor["hsi_adj"] * weights.get("hsi_momentum", 0)
    else:
        adj_parts["hsi_momentum"] = 0

    total_adj = sum(adj_parts.values())

    # [P2] 超购爆发：额外叠加
    explosion_bonus = 0
    if explosion:
        explosion_bonus = explosion["explosion_adj"]
        adj_parts["explosion"] = explosion_bonus
        total_adj += explosion_bonus

    # [P2] 暗盘冲高回落惩罚：额外扣减
    dark_crash_penalty = 0
    if dark_crash and dark_crash.get("is_crash"):
        dark_crash_penalty = dark_crash["crash_penalty"]
        total_adj += dark_crash_penalty

    total_adj = max(-30.0, min(80.0, total_adj))

    # 4. 置信度
    active_factors = [sentiment, narrative, explosion, ah_factor, a_momentum, hsi_factor]
    n_factors = sum(1 for v in active_factors if v is not None)
    confidence = "高" if n_factors >= 5 else ("中" if n_factors >= 3 else "低")

    return {
        "total_adj": round(total_adj, 1),
        "is_ah": is_ah,
        "factors": {
            "sentiment": sentiment,
            "narrative": narrative,
            "explosion": explosion,
            "dark_crash": dark_crash,
            "ah_premium": ah_factor,
            "a_momentum": a_momentum,
            "hsi_momentum": hsi_factor,
        },
        "weights_used": {k: round(v, 3) for k, v in weights.items()},
        "adj_breakdown": {k: round(v, 1) for k, v in adj_parts.items()},
        "dark_crash_penalty": round(dark_crash_penalty, 1),
        "confidence": confidence,
        "n_factors_active": n_factors,
    }


def apply_adjustment(base_predictions, market_adj):
    """将市场情绪修正应用到模型基准预测上。

    暗盘预测不含crash_penalty（暗盘还没发生时不用暗盘数据修正暗盘）。
    首日预测含crash_penalty。
    """
    if not market_adj:
        return base_predictions

    total_adj = market_adj["total_adj"]
    dark_crash_penalty = market_adj.get("dark_crash_penalty", 0)
    adj_for_dark = total_adj - dark_crash_penalty
    adj_for_day1 = total_adj

    adjusted = {}
    for key in ["dark_expected", "day1_expected", "day3_expected", "day5_expected"]:
        base = base_predictions.get(key)
        if base is not None:
            if "dark" in key:
                adj_val = adj_for_dark * 1.0
            elif "day1" in key:
                adj_val = adj_for_day1 * 0.8
            else:
                adj_val = adj_for_day1 * 0.5
            adjusted[key] = round(base + adj_val, 1)
            adjusted[f"{key}_base"] = base
            adjusted[f"{key}_adj"] = round(adj_val, 1)
    return adjusted


# ============================================
# 格式化输出
# ============================================

def format_adjustment_summary(market_adj):
    """格式化市场修正摘要，供 CLI 输出。"""
    if not market_adj:
        return "市场修正: 无数据"

    lines = []
    total = market_adj["total_adj"]
    sign = "+" if total >= 0 else ""
    lines.append(f"📊 市场情绪修正: {sign}{total:.1f}pp (置信度: {market_adj['confidence']})")

    breakdown = market_adj.get("adj_breakdown", {})
    factor_names = {
        "sentiment": "近期新股情绪",
        "narrative": "赛道叙事溢价",
        "explosion": "超购爆发弹性",
        "ah_premium": "AH溢价",
        "a_momentum": "A股联动",
        "hsi_momentum": "恒指动量",
    }

    for key, name in factor_names.items():
        val = breakdown.get(key, 0)
        if val != 0 or market_adj["weights_used"].get(key, 0) > 0:
            w = market_adj["weights_used"].get(key, 0)
            s = "+" if val >= 0 else ""
            if key == "explosion":
                lines.append(f"   🚀 {name}: {s}{val:.1f}pp (额外叠加)")
            else:
                lines.append(f"   {name}: {s}{val:.1f}pp (权重{w*100:.0f}%)")

    dark_crash_p = market_adj.get("dark_crash_penalty", 0)
    if dark_crash_p != 0:
        lines.append(f"   ⚠️ 暗盘冲高回落惩罚: {dark_crash_p:+.1f}pp")

    factors = market_adj.get("factors", {})
    sentiment = factors.get("sentiment")
    if sentiment and sentiment.get("recent_stocks"):
        lines.append(f"   近期情绪: 最近{sentiment['n_recent']}只暗盘均值{sentiment['recent_avg_dark']:+.1f}% "
                     f"vs 历史{sentiment['history_avg_dark']:+.1f}% → 倍数{sentiment['sentiment_ratio']:.2f}x")

    narrative = factors.get("narrative")
    if narrative and narrative.get("narrative_group"):
        lines.append(f"   赛道[{narrative['narrative_group']}]: 同赛道暗盘均值{narrative['same_sector_avg_dark']:+.1f}% "
                     f"vs 全量{narrative['overall_avg_dark']:+.1f}% → 溢价{narrative['sector_premium']:+.1f}pp")

    explosion = factors.get("explosion")
    if explosion:
        lines.append(f"   🚀 超购爆发: {explosion['subscription_mult']:.0f}x > 3000x | "
                     f"基础+{explosion['base_boost']:.1f}pp × [{explosion['narrative_group']}]{explosion['sector_multiplier']:.1f}x "
                     f"= +{explosion['explosion_adj']:.1f}pp")

    dark_crash = factors.get("dark_crash")
    if dark_crash and dark_crash.get("is_crash"):
        lines.append(f"   ⚠️ 暗盘冲高回落: {dark_crash['risk_reason']}")

    ah = factors.get("ah_premium")
    if ah:
        lines.append(f"   AH折价: H{ah['h_ipo_price']} vs A≈{ah['a_price_hkd']:.0f}HKD → 折价{ah['discount_pct']:.1f}%")

    a_mom = factors.get("a_momentum")
    if a_mom:
        lines.append(f"   A股{a_mom['period']}: {a_mom['momentum_pct']:+.1f}%")

    hsi = factors.get("hsi_momentum")
    if hsi:
        lines.append(f"   恒指{hsi['n_days']}日: {hsi['hsi_momentum_pct']:+.1f}%")

    return "\n".join(lines)


# ============================================
# 测试
# ============================================

if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    from data import ipo_data

    print("=== 市场情绪修正模块 V4.0 P2 测试 ===\n")
    sentiment = compute_ipo_sentiment(ipo_data)
    print(f"情绪倍数: {sentiment['sentiment_ratio']:.3f}x | 修正: {sentiment['sentiment_adj']:+.1f}pp")

    adj = compute_market_adjustment(ipo_data, target_category="AI", subscription_mult=4405)
    print(f"\n综合修正(AI 4405x): {adj['total_adj']:+.1f}pp")
    print(format_adjustment_summary(adj))
    print("\n=== 测试完成 ===")
