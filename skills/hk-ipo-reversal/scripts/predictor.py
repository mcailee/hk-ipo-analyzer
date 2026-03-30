#!/usr/bin/env python3
"""港股新股暗盘反转猎手 V2 - 实时修正预测器 (期望偏差版)
输入新股的暗盘数据+基本面参数，输出修正概率预测和买卖建议
核心升级：不再限制暗盘必须下跌，改为基于期望偏差分析
"""
import math
from utils import (
    mean, std_dev, bootstrap_ci,
    logistic_predict_proba, sigmoid,
    euclidean_distance, standardize,
    classify_market_state, get_current_market_state,
    BULL, BEAR, NEUTRAL, STATE_LABELS,
)
from reversal_engine import (
    extract_reversal_features, extract_price_path,
    train_reversal_model, PATH_TIMEPOINTS,
    auto_estimate_expected_return, compute_deviation,
    classify_deviation_type, DEVIATION_CATEGORIES,
)


# ============================================
# 信心等级定义
# ============================================

def get_confidence_level(prob, n_similar, model_auc):
    """综合判断信心等级 (1-5星)"""
    clarity = abs(prob - 0.5) * 2
    case_score = min(n_similar / 5, 1.0)
    model_score = max(model_auc - 0.5, 0) * 2

    score = clarity * 0.4 + case_score * 0.3 + model_score * 0.3
    if score >= 0.8: return 5
    if score >= 0.6: return 4
    if score >= 0.4: return 3
    if score >= 0.2: return 2
    return 1

def stars(n):
    return "★" * n + "☆" * (5 - n)


# ============================================
# 建议生成 (偏差版)
# ============================================

def generate_advice(prob, dark_return, deviation, expected_return=None,
                    day1_return=None, confidence=3):
    """基于修正概率和偏差类型生成买卖建议"""

    # 偏差类型判断
    if deviation is None or deviation >= -5:
        # 偏差不大，表现正常
        return {
            "action": "表现正常",
            "reason": f"暗盘{dark_return:+.1f}%，偏差仅{deviation:+.1f}%，表现基本符合预期" if deviation is not None else "数据不足",
            "detail": ["暗盘表现符合或接近预期，不属于偏差修正分析范畴",
                       "请参考 hk-ipo-sweet-spot 的卖出策略建议"],
            "risk_level": "低",
        }

    # 区分暗盘下跌 vs 涨幅不及预期
    is_dark_positive = dark_return is not None and dark_return >= 0

    if is_dark_positive:
        # 暗盘上涨但不及预期
        prefix = f"暗盘{dark_return:+.1f}%，但预期{expected_return:+.1f}%，偏差{deviation:+.1f}%" if expected_return is not None else f"偏差{deviation:+.1f}%"

        if prob >= 0.7:
            action = "持有等待修正"
            reason = f"{prefix}。修正概率 {prob:.0%}，历史类似案例多数后续补涨"
            risk_level = "中"
            advices = [
                "暗盘涨幅虽不及预期，但修正概率较高",
                "建议持有，关注首日和Day3的走势修复",
                "类似案例Day5-Day10通常回归预期区间",
            ]
        elif prob >= 0.5:
            action = "谨慎持有观望"
            reason = f"{prefix}。修正概率 {prob:.0%}，有一定修正空间但不确定"
            risk_level = "中"
            advices = [
                "涨幅不及预期，但暗盘未破发，风险可控",
                "如果首日继续走弱，可考虑减仓",
                "设置止盈/止损位，不要追加仓位",
            ]
        elif prob >= 0.3:
            action = "考虑首日卖出"
            reason = f"{prefix}。修正概率仅 {prob:.0%}，多数类似案例未能修正"
            risk_level = "中高"
            advices = [
                "涨幅不及预期且修正概率偏低",
                "建议首日有利润即卖出锁定",
                "不要期待后续大幅补涨",
            ]
        else:
            action = "建议尽早卖出"
            reason = f"{prefix}。修正概率仅 {prob:.0%}，历史类似案例多数持续走弱"
            risk_level = "高"
            advices = [
                "严重不及预期，后续大概率继续走弱",
                "建议暗盘或首日开盘即卖出",
                "历史数据显示此类股票后续往往转跌",
            ]
    else:
        # 暗盘下跌（原有逻辑增强版）
        if prob >= 0.7:
            action = "持有等待反弹"
            reason = f"反转概率 {prob:.0%}，历史相似案例多数反弹成功"
            risk_level = "中"
            advices = [
                "建议持有，不要在暗盘割肉",
                "关注首日开盘走势，如果首日企稳则大概率反转",
                "Day3-Day5是关键观察窗口",
            ]
        elif prob >= 0.5:
            action = "谨慎持有"
            reason = f"反转概率 {prob:.0%}，反弹可能性存在但不确定"
            risk_level = "中高"
            advices = [
                "可以小仓位持有观察",
                "如果首日继续下跌超过暗盘跌幅的1.5倍，建议止损",
                "设置心理止损位，不要加仓",
            ]
        elif prob >= 0.3:
            action = "考虑止损"
            reason = f"反转概率 {prob:.0%}，多数类似案例未能反弹"
            risk_level = "高"
            advices = [
                "建议在暗盘或首日早盘止损",
                "不要抱有侥幸心理等待反弹",
                "少数反转案例通常有特殊催化剂",
            ]
        else:
            action = "建议立即止损"
            reason = f"反转概率仅 {prob:.0%}，历史相似案例几乎全部持续下跌"
            risk_level = "极高"
            advices = [
                "强烈建议暗盘或首日开盘即止损",
                "历史数据显示此类股票Day5平均进一步下跌",
                "越早止损，损失越小",
            ]

    # 首日数据补充判断
    if day1_return is not None:
        if dark_return is not None and day1_return > dark_return:
            advices.append("✅ 首日已出现修复迹象，修正概率进一步提升")
        elif dark_return is not None and day1_return < dark_return * 1.5:
            advices.append("⚠️ 首日加速恶化，修正希望渺茫，建议尽快离场")

    return {
        "action": action,
        "reason": reason,
        "detail": advices,
        "risk_level": risk_level,
    }


# ============================================
# 因子诊断 (偏差版)
# ============================================

def diagnose_factors(params, data, model=None):
    """对输入参数进行因子诊断"""
    diagnostics = []

    # 获取偏差分析参考池
    underperform = [d for d in data if d.get("deviation") is not None and d["deviation"] < 0]

    # 0. 期望偏差 (新增核心因子)
    dev = params.get("deviation")
    exp = params.get("expected_return")
    dr = params.get("dark_return", 0)
    if dev is not None and exp is not None:
        if dev <= -30:
            diagnostics.append({
                "factor": "期望偏差",
                "value": f"{dev:+.1f}% (暗盘{dr:+.1f}% vs 预期{exp:+.1f}%)",
                "impact": "严重不及预期，偏差极大",
                "score": -15,
                "emoji": "🔴",
            })
        elif dev <= -15:
            diagnostics.append({
                "factor": "期望偏差",
                "value": f"{dev:+.1f}% (暗盘{dr:+.1f}% vs 预期{exp:+.1f}%)",
                "impact": "显著不及预期",
                "score": -10,
                "emoji": "⚠️",
            })
        elif dev <= -5:
            diagnostics.append({
                "factor": "期望偏差",
                "value": f"{dev:+.1f}% (暗盘{dr:+.1f}% vs 预期{exp:+.1f}%)",
                "impact": "轻微不及预期，有修正空间",
                "score": 5,
                "emoji": "🔄",
            })
        else:
            diagnostics.append({
                "factor": "期望偏差",
                "value": f"{dev:+.1f}% (暗盘{dr:+.1f}% vs 预期{exp:+.1f}%)",
                "impact": "基本符合或超越预期",
                "score": 10,
                "emoji": "✅",
            })

    # 1. 超购倍数
    sub = params.get("subscription_mult", 0)
    avg_sub = mean([d["subscription_mult"] for d in underperform]) if underperform else 100
    if sub > avg_sub * 2:
        diagnostics.append({
            "factor": "超购倍数",
            "value": f"{sub:.0f}倍",
            "impact": f"远高于不及预期组均值({avg_sub:.0f}倍)，市场热度高",
            "score": 15,
            "emoji": "✅",
        })
    elif sub > avg_sub:
        diagnostics.append({
            "factor": "超购倍数",
            "value": f"{sub:.0f}倍",
            "impact": f"高于不及预期组均值({avg_sub:.0f}倍)",
            "score": 8,
            "emoji": "✅",
        })
    else:
        diagnostics.append({
            "factor": "超购倍数",
            "value": f"{sub:.0f}倍",
            "impact": f"低于不及预期组均值({avg_sub:.0f}倍)，市场热度不足",
            "score": -10,
            "emoji": "⚠️",
        })

    # 2. 基石投资者
    has_cs = params.get("has_cornerstone", False)
    cs_pool = [d for d in underperform if d.get("has_cornerstone")]
    no_cs_pool = [d for d in underperform if not d.get("has_cornerstone")]
    cs_rev = sum(1 for d in cs_pool if d.get("day5_return") is not None and d["day5_return"] > 0)
    no_cs_rev = sum(1 for d in no_cs_pool if d.get("day5_return") is not None and d["day5_return"] > 0)
    cs_rate = cs_rev / len(cs_pool) * 100 if cs_pool else 0
    no_cs_rate = no_cs_rev / len(no_cs_pool) * 100 if no_cs_pool else 0

    if has_cs:
        diagnostics.append({
            "factor": "基石投资者",
            "value": "有",
            "impact": f"有基石组修正率{cs_rate:.0f}% vs 无基石{no_cs_rate:.0f}%",
            "score": 10 if cs_rate > no_cs_rate else 5,
            "emoji": "✅",
        })
    else:
        diagnostics.append({
            "factor": "基石投资者",
            "value": "无",
            "impact": f"无基石组修正率{no_cs_rate:.0f}%，缺乏机构背书",
            "score": -8,
            "emoji": "⚠️",
        })

    # 3. 暗盘表现
    if dr is not None:
        if dr < -20:
            diagnostics.append({
                "factor": "暗盘表现",
                "value": f"{dr:+.1f}%",
                "impact": "暗盘严重破发，修正难度极大",
                "score": -12,
                "emoji": "🔴",
            })
        elif dr < 0:
            diagnostics.append({
                "factor": "暗盘表现",
                "value": f"{dr:+.1f}%",
                "impact": "暗盘破发，但超跌可能带来物极必反",
                "score": 3,
                "emoji": "🔄",
            })
        elif dr < 10:
            diagnostics.append({
                "factor": "暗盘表现",
                "value": f"{dr:+.1f}%",
                "impact": "暗盘小幅上涨，但低于预期，修正空间存在",
                "score": 5,
                "emoji": "➡️",
            })
        else:
            diagnostics.append({
                "factor": "暗盘表现",
                "value": f"{dr:+.1f}%",
                "impact": "暗盘涨幅不错，不及预期可能只是暂时",
                "score": 8,
                "emoji": "✅",
            })

    # 4. 行业
    cat = params.get("category", "其他")
    cat_pool = [d for d in underperform if d.get("category") == cat]
    cat_rev = sum(1 for d in cat_pool if d.get("day5_return") is not None and d["day5_return"] > 0)
    cat_rate = cat_rev / len(cat_pool) * 100 if cat_pool else 0
    if len(cat_pool) >= 3:
        if cat_rate > 30:
            diagnostics.append({
                "factor": "行业",
                "value": cat,
                "impact": f"该行业不及预期后修正率{cat_rate:.0f}%({len(cat_pool)}只样本)",
                "score": 12,
                "emoji": "✅",
            })
        else:
            diagnostics.append({
                "factor": "行业",
                "value": cat,
                "impact": f"该行业不及预期后修正率仅{cat_rate:.0f}%({len(cat_pool)}只样本)",
                "score": -8,
                "emoji": "⚠️",
            })
    else:
        diagnostics.append({
            "factor": "行业",
            "value": cat,
            "impact": f"该行业不及预期样本不足({len(cat_pool)}只)，参考价值有限",
            "score": 0,
            "emoji": "❓",
        })

    # 5. 募资规模
    fund = params.get("fundraising", 5)
    if fund >= 50:
        diagnostics.append({
            "factor": "募资规模",
            "value": f"{fund:.1f}亿",
            "impact": "大盘股流动性好，修正基础扎实",
            "score": 8,
            "emoji": "✅",
        })
    elif fund >= 10:
        diagnostics.append({
            "factor": "募资规模",
            "value": f"{fund:.1f}亿",
            "impact": "中盘股，修正受市场情绪影响",
            "score": 3,
            "emoji": "➡️",
        })
    else:
        diagnostics.append({
            "factor": "募资规模",
            "value": f"{fund:.1f}亿",
            "impact": "小盘股波动大，修正不确定性高",
            "score": -5,
            "emoji": "⚠️",
        })

    return diagnostics


# ============================================
# 主预测函数 (偏差版)
# ============================================

def predict_reversal(params, data, hsi_monthly, model=None, expected_return=None):
    """预测新股修正概率

    Args:
        params: dict with code, dark_return, subscription_mult, etc.
        data: 完整历史数据集
        hsi_monthly: 恒指月度数据
        model: 预训练的Logistic回归模型 (None则自动训练)
        expected_return: 用户指定的预期涨幅 (None则自动推算)

    Returns:
        prediction dict
    """
    dark_return = params.get("dark_return", 0)

    # 推算 expected_return 和 deviation
    if expected_return is not None:
        params["expected_return"] = expected_return
    elif params.get("expected_return") is None:
        params["expected_return"] = auto_estimate_expected_return(params, data)

    deviation = compute_deviation(params, expected_return=params.get("expected_return"))
    params["deviation"] = deviation

    # 偏差类型
    dev_type = classify_deviation_type(params)

    # 如果偏差不足（表现正常或超预期），不适用修正分析
    if deviation is None or deviation >= -5:
        return {
            "probability": None,
            "confidence": 0,
            "advice": generate_advice(0, dark_return, deviation, params.get("expected_return")),
            "diagnostics": [],
            "similar_cases": [],
            "expected_returns": {},
            "model_info": None,
            "not_applicable": True,
            "reason": f"暗盘{dark_return:+.1f}%，预期{params.get('expected_return', 0):+.1f}%，偏差{deviation:+.1f}%，表现基本符合预期",
            "deviation_type": dev_type,
            "params": params,
        }

    # 1. 训练/使用模型
    if model is None:
        model = train_reversal_model(data, target_window="day5_return", deviation_threshold=-10)

    # 2. 提取特征
    feat, feat_names = extract_reversal_features(params)

    # 3. 计算修正概率
    probability = 0.3

    if model and feat:
        scaled_feat = []
        for j, (m, s) in enumerate(model["scalers"]):
            if s > 0:
                scaled_feat.append((feat[j] - m) / s)
            else:
                scaled_feat.append(0)

        probs = logistic_predict_proba([scaled_feat], model["weights"], model["bias"])
        probability = probs[0]

    # 4. 找相似案例（基于偏差而非仅暗盘下跌）
    similar_pool = [d for d in data
                    if d.get("deviation") is not None and d["deviation"] < 0]

    similar_cases = []
    if feat:
        for d in similar_pool:
            d_feat, _ = extract_reversal_features(d)
            if d_feat:
                dist = euclidean_distance(feat, d_feat)
                sim = 1.0 / (1.0 + dist)
                did_correct = (d.get("day5_return") is not None and d["day5_return"] > 0) or \
                              (d.get("day10_return") is not None and d["day10_return"] > 0)
                similar_cases.append({
                    "similarity": sim,
                    "stock": d,
                    "did_correct": did_correct,
                    "path": extract_price_path(d),
                    "deviation_type": classify_deviation_type(d),
                })
        similar_cases.sort(key=lambda x: -x["similarity"])
        similar_cases = similar_cases[:8]

    # 5. 信心等级
    model_auc = model["auc"] if model else 0.5
    confidence = get_confidence_level(probability, len(similar_cases), model_auc)

    # 6. 因子诊断
    diagnostics = diagnose_factors(params, data, model)

    # 7. 预期收益估算
    expected_returns = {}
    for key_label, key in [("Day1", "day1_return"), ("Day3", "day3_return"),
                           ("Day5", "day5_return"), ("Day7", "day7_return"),
                           ("Day10", "day10_return")]:
        if similar_cases:
            returns = [c["stock"].get(key) for c in similar_cases[:5]
                       if c["stock"].get(key) is not None]
            if returns:
                ci = bootstrap_ci(returns, n_bootstrap=500)
                expected_returns[key_label] = ci

    # 8. 生成建议
    advice = generate_advice(probability, dark_return, deviation,
                            params.get("expected_return"), params.get("day1_return"), confidence)

    return {
        "probability": probability,
        "confidence": confidence,
        "confidence_stars": stars(confidence),
        "advice": advice,
        "diagnostics": diagnostics,
        "similar_cases": similar_cases,
        "expected_returns": expected_returns,
        "model_info": {
            "accuracy": model["accuracy"] if model else 0,
            "auc": model["auc"] if model else 0.5,
            "n_samples": model["n_samples"] if model else 0,
            "feature_importance": model["feature_importance"] if model else {},
        } if model else None,
        "not_applicable": False,
        "deviation_type": dev_type,
        "deviation_type_label": DEVIATION_CATEGORIES.get(dev_type, "其他"),
        "params": params,
    }
