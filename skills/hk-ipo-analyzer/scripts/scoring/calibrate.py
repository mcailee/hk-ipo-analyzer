"""数据驱动的概率模型校准模块。

利用 sweet-spot（128只IPO历史数据）和 reversal（暗盘偏差模型）
的真实回测数据，为 probability.py 的 SCORE_RETURN_MAP 提供实证基础，
并实现期望偏差修正逻辑。

校准流程：
  1. 用 sweet-spot 的 score_ipo() 为 128 只历史 IPO 打代理评分
  2. 按代理评分分档，统计每档的真实 avg_return / up_ratio / std_dev
  3. 用 reversal 的 auto_estimate_expected_return() 计算期望偏差
  4. 分析偏差→首日修正的映射关系
"""
from __future__ import annotations

import math
import os
import sys

# 加载 sweet-spot 和 reversal 数据
SWEET_SPOT_DIR = os.path.expanduser("~/.workbuddy/skills/hk-ipo-sweet-spot/scripts")
REVERSAL_DIR = os.path.expanduser("~/.workbuddy/skills/hk-ipo-reversal/scripts")


def _load_sweet_spot_data():
    """加载 sweet-spot 的数据和引擎"""
    sys.path.insert(0, SWEET_SPOT_DIR)
    from data import ipo_data, hsi_monthly
    from engine import (compute_factor_weights, score_ipo, get_tier,
                        classify_market_state, label_data_market_state)
    return ipo_data, hsi_monthly, compute_factor_weights, score_ipo, get_tier


def _load_reversal_data():
    """加载 reversal 的数据和引擎"""
    sys.path.insert(0, REVERSAL_DIR)
    from data import ipo_data as rev_data
    from reversal_engine import auto_estimate_expected_return, compute_deviation
    return rev_data, auto_estimate_expected_return, compute_deviation


def calibrate_score_return_map():
    """用历史数据校准 SCORE_RETURN_MAP。

    Returns:
        calibrated_map: list of (score_low, score_high, avg_return, up_ratio, std_dev)
        stats: dict with calibration statistics
    """
    ipo_data, hsi_monthly, compute_factor_weights, score_ipo, get_tier = _load_sweet_spot_data()

    # 1. 训练 sweet-spot 因子模型
    weights, extra = compute_factor_weights(ipo_data)
    cat_encoding = extra.get("cat_encoding", {})
    norm_stats = extra.get("norm_stats", {})

    # 2. 为每只 IPO 打代理评分（0-100）
    scored_ipos = []
    for d in ipo_data:
        if d.get("day1_return") is None:
            continue
        proxy_score = score_ipo(d, weights, cat_encoding, norm_stats, extra)
        scored_ipos.append({
            "name": d["name"],
            "code": d["code"],
            "proxy_score": proxy_score,
            "day1_return": d["day1_return"],
            "dark_return": d.get("dark_return"),
            "day3_return": d.get("day3_return"),
            "day5_return": d.get("day5_return"),
            "subscription_mult": d["subscription_mult"],
            "has_cornerstone": d["has_cornerstone"],
            "category": d["category"],
            "fundraising": d["fundraising"],
        })

    # 3. 按代理评分分档（与 analyzer 的区间对齐）
    bins = [
        (80, 100),  # 强烈推荐
        (70, 80),   # 推荐偏高
        (65, 70),   # 推荐边界
        (55, 65),   # 中性偏上
        (50, 55),   # 中性偏下
        (40, 50),   # 回避偏上
        (0, 40),    # 回避
    ]

    calibrated_map = []
    stats = {"total": len(scored_ipos), "bins": []}

    for low, high in bins:
        # 分档
        if high == 100:
            bin_ipos = [s for s in scored_ipos if low <= s["proxy_score"] <= high]
        else:
            bin_ipos = [s for s in scored_ipos if low <= s["proxy_score"] < high]

        returns = [s["day1_return"] for s in bin_ipos]
        n = len(returns)

        if n >= 3:
            avg_return = sum(returns) / n
            up_count = sum(1 for r in returns if r > 0)
            up_ratio = up_count / n
            variance = sum((r - avg_return) ** 2 for r in returns) / n
            std_dev = variance ** 0.5
        elif n > 0:
            # 小样本：用中位数和保守估计
            avg_return = sorted(returns)[n // 2]
            up_ratio = sum(1 for r in returns if r > 0) / n
            std_dev = max(abs(max(returns) - min(returns)) / 2, 10.0) if n > 1 else 15.0
        else:
            # 无样本：保留原始硬编码值作为先验
            original = {
                (80, 100): (25.0, 0.88, 15.0),
                (70, 80): (12.0, 0.78, 12.0),
                (65, 70): (6.0, 0.68, 10.0),
                (55, 65): (1.5, 0.55, 9.0),
                (50, 55): (-1.0, 0.45, 8.0),
                (40, 50): (-5.0, 0.32, 10.0),
                (0, 40): (-12.0, 0.18, 14.0),
            }
            avg_return, up_ratio, std_dev = original[(low, high)]

        calibrated_map.append((low, high,
                               round(avg_return, 1),
                               round(up_ratio, 2),
                               round(std_dev, 1)))
        stats["bins"].append({
            "range": f"{low}-{high}",
            "count": n,
            "avg_return": round(avg_return, 1),
            "up_ratio": round(up_ratio * 100, 1),
            "std_dev": round(std_dev, 1),
            "samples": [s["name"] for s in bin_ipos[:5]],
        })

    return calibrated_map, stats


def calibrate_deviation_correction():
    """校准暗盘期望偏差→首日修正的映射关系。

    Returns:
        correction_params: dict with deviation correction coefficients
        stats: dict with calibration statistics
    """
    rev_data, auto_estimate_expected_return, compute_deviation = _load_reversal_data()

    # 为每只有暗盘数据的 IPO 计算偏差
    deviations = []
    for d in rev_data:
        dark_return = d.get("dark_return")
        day1_return = d.get("day1_return")
        deviation = d.get("deviation")
        expected_return = d.get("expected_return")

        if dark_return is None or day1_return is None:
            continue

        # 如果没有预存偏差，运行时计算
        if deviation is None:
            expected_return = auto_estimate_expected_return(d, rev_data)
            deviation = dark_return - expected_return

        deviations.append({
            "name": d["name"],
            "code": d["code"],
            "dark_return": dark_return,
            "day1_return": day1_return,
            "expected_return": expected_return,
            "deviation": deviation,
            "correction": day1_return - dark_return,  # 首日相对暗盘的修正
            "has_cornerstone": d.get("has_cornerstone", False),
            "subscription_mult": d.get("subscription_mult", 0),
        })

    if len(deviations) < 10:
        return None, {"error": "insufficient data"}

    # 按偏差方向分组分析
    neg_dev = [d for d in deviations if d["deviation"] < -10]  # 严重不及预期
    mild_neg = [d for d in deviations if -10 <= d["deviation"] < 0]  # 轻微不及预期
    mild_pos = [d for d in deviations if 0 <= d["deviation"] < 20]  # 轻微超预期
    strong_pos = [d for d in deviations if d["deviation"] >= 20]  # 大幅超预期

    def _group_stats(group, label):
        if not group:
            return {"label": label, "count": 0, "avg_correction": 0, "avg_dev": 0}
        n = len(group)
        return {
            "label": label,
            "count": n,
            "avg_deviation": round(sum(d["deviation"] for d in group) / n, 1),
            "avg_dark_return": round(sum(d["dark_return"] for d in group) / n, 1),
            "avg_day1_return": round(sum(d["day1_return"] for d in group) / n, 1),
            "avg_correction": round(sum(d["correction"] for d in group) / n, 1),
            "up_rate_d1": round(sum(1 for d in group if d["day1_return"] > 0) / n * 100, 1),
        }

    # 计算线性回归：deviation → day1_correction
    # correction = a * deviation + b
    n = len(deviations)
    devs = [d["deviation"] for d in deviations]
    corrs = [d["correction"] for d in deviations]
    mean_dev = sum(devs) / n
    mean_corr = sum(corrs) / n

    cov = sum((devs[i] - mean_dev) * (corrs[i] - mean_corr) for i in range(n))
    var_dev = sum((d - mean_dev) ** 2 for d in devs)

    if var_dev > 0:
        slope = cov / var_dev
        intercept = mean_corr - slope * mean_dev
    else:
        slope = 0.0
        intercept = mean_corr

    # R²
    ss_res = sum((corrs[i] - (slope * devs[i] + intercept)) ** 2 for i in range(n))
    ss_tot = sum((c - mean_corr) ** 2 for c in corrs)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0

    # 偏差→上涨概率修正的映射
    # 按偏差分档统计首日上涨概率
    prob_correction_map = []
    dev_bins = [(-999, -50), (-50, -30), (-30, -10), (-10, 0),
                (0, 10), (10, 30), (30, 50), (50, 999)]
    for lo, hi in dev_bins:
        group = [d for d in deviations if lo <= d["deviation"] < hi]
        if group:
            up_rate = sum(1 for d in group if d["day1_return"] > 0) / len(group)
            avg_d1 = sum(d["day1_return"] for d in group) / len(group)
            prob_correction_map.append({
                "dev_range": f"{lo} to {hi}",
                "count": len(group),
                "up_rate": round(up_rate, 3),
                "avg_day1": round(avg_d1, 1),
            })

    correction_params = {
        "slope": round(slope, 4),
        "intercept": round(intercept, 2),
        "r2": round(r2, 3),
        "deviation_groups": [
            _group_stats(neg_dev, "严重不及预期(dev<-10)"),
            _group_stats(mild_neg, "轻微不及预期(-10≤dev<0)"),
            _group_stats(mild_pos, "轻微超预期(0≤dev<20)"),
            _group_stats(strong_pos, "大幅超预期(dev≥20)"),
        ],
        "prob_correction_map": prob_correction_map,
    }

    stats = {
        "total_samples": n,
        "mean_deviation": round(mean_dev, 1),
        "mean_correction": round(mean_corr, 1),
    }

    return correction_params, stats


def calibrate_sell_timing():
    """用历史数据验证并校准卖出时机策略阈值。

    Returns:
        timing_params: dict with validated/corrected timing thresholds
        stats: dict with analysis statistics
    """
    ipo_data, hsi_monthly, compute_factor_weights, score_ipo, get_tier = _load_sweet_spot_data()
    rev_data, _, _ = _load_reversal_data()

    # 用 reversal 的更丰富数据（有 day2/day7/day10）
    # 按市值代理（fundraising）和超购分组
    timing_analysis = {
        "by_fundraising": [],
        "by_subscription": [],
        "overall_optimal_exit": {},
    }

    # 用 fundraising 作为市值代理
    size_bins = [
        ("微小盘(<3亿)", 0, 3),
        ("小盘(3-10亿)", 3, 10),
        ("中盘(10-30亿)", 10, 30),
        ("大盘(30-100亿)", 30, 100),
        ("超大盘(>100亿)", 100, 99999),
    ]

    timepoints = [
        ("dark", "dark_return"),
        ("day1", "day1_return"),
        ("day3", "day3_return"),
        ("day5", "day5_return"),
    ]

    # reversal 有更多时点
    rev_timepoints = [
        ("dark", "dark_return"),
        ("day1", "day1_return"),
        ("day2", "day2_return"),
        ("day3", "day3_return"),
        ("day5", "day5_return"),
        ("day7", "day7_return"),
        ("day10", "day10_return"),
    ]

    for label, lo, hi in size_bins:
        group_ss = [d for d in ipo_data if lo <= d["fundraising"] < hi]
        group_rev = [d for d in rev_data if lo <= d.get("fundraising", 0) < hi]

        best_tp = None
        best_expected = -999

        tp_results = []
        for tp_label, tp_key in rev_timepoints:
            vals = [d[tp_key] for d in group_rev if d.get(tp_key) is not None]
            if vals:
                avg = sum(vals) / len(vals)
                win_rate = sum(1 for v in vals if v > 0) / len(vals) * 100
                expected = avg * win_rate / 100  # 简化期望
                tp_results.append({
                    "timepoint": tp_label,
                    "count": len(vals),
                    "avg_return": round(avg, 1),
                    "win_rate": round(win_rate, 1),
                    "expected": round(expected, 1),
                })
                if expected > best_expected:
                    best_expected = expected
                    best_tp = tp_label

        timing_analysis["by_fundraising"].append({
            "label": label,
            "count": len(group_rev),
            "timepoints": tp_results,
            "best_exit": best_tp,
            "best_expected": round(best_expected, 1),
        })

    # 按超购倍数分组
    sub_bins = [
        ("<100x", 0, 100),
        ("100-500x", 100, 500),
        ("500-2000x", 500, 2000),
        ("2000-5000x", 2000, 5000),
        (">5000x", 5000, 999999),
    ]

    for label, lo, hi in sub_bins:
        group = [d for d in rev_data if lo <= d.get("subscription_mult", 0) < hi]
        tp_results = []
        best_tp = None
        best_expected = -999

        for tp_label, tp_key in rev_timepoints:
            vals = [d[tp_key] for d in group if d.get(tp_key) is not None]
            if vals:
                avg = sum(vals) / len(vals)
                win_rate = sum(1 for v in vals if v > 0) / len(vals) * 100
                expected = avg * win_rate / 100
                tp_results.append({
                    "timepoint": tp_label,
                    "count": len(vals),
                    "avg_return": round(avg, 1),
                    "win_rate": round(win_rate, 1),
                    "expected": round(expected, 1),
                })
                if expected > best_expected:
                    best_expected = expected
                    best_tp = tp_label

        timing_analysis["by_subscription"].append({
            "label": label,
            "count": len(group),
            "timepoints": tp_results,
            "best_exit": best_tp,
            "best_expected": round(best_expected, 1),
        })

    # 全局最优退出时点
    all_tps = {}
    for tp_label, tp_key in rev_timepoints:
        vals = [d[tp_key] for d in rev_data if d.get(tp_key) is not None]
        if vals:
            avg = sum(vals) / len(vals)
            win_rate = sum(1 for v in vals if v > 0) / len(vals) * 100
            all_tps[tp_label] = {
                "avg": round(avg, 1),
                "win_rate": round(win_rate, 1),
                "count": len(vals),
            }
    timing_analysis["overall_optimal_exit"] = all_tps

    return timing_analysis, {"total_ipos": len(rev_data)}


if __name__ == "__main__":
    import json

    print("=" * 60)
    print("港股 IPO 分析模型校准")
    print("=" * 60)

    # 1. SCORE_RETURN_MAP 校准
    print("\n📊 1. SCORE_RETURN_MAP 校准 (128只历史IPO)")
    print("-" * 50)
    cal_map, cal_stats = calibrate_score_return_map()
    print(f"总样本: {cal_stats['total']}")
    print(f"{'评分区间':<12} {'样本数':<8} {'平均收益':<10} {'上涨率':<10} {'标准差':<10}")
    for b in cal_stats["bins"]:
        print(f"{b['range']:<12} {b['count']:<8} {b['avg_return']:>+7.1f}% {b['up_ratio']:>7.1f}% {b['std_dev']:>7.1f}%")

    print("\n校准后 SCORE_RETURN_MAP:")
    for entry in cal_map:
        lo, hi, ret, up, std = entry
        print(f"  ({lo:>3}, {hi:>3}, {ret:>+6.1f}, {up:.2f}, {std:>5.1f}),")

    # 2. 偏差修正校准
    print("\n\n📈 2. 暗盘期望偏差修正校准")
    print("-" * 50)
    dev_params, dev_stats = calibrate_deviation_correction()
    if dev_params:
        print(f"总样本: {dev_stats['total_samples']}")
        print(f"线性模型: correction = {dev_params['slope']} × deviation + {dev_params['intercept']}")
        print(f"R²: {dev_params['r2']}")
        print(f"\n偏差分组统计:")
        for g in dev_params["deviation_groups"]:
            if g["count"] > 0:
                print(f"  {g['label']}: n={g['count']}, "
                      f"avg_dev={g['avg_deviation']:+.1f}%, "
                      f"avg_d1={g['avg_day1_return']:+.1f}%, "
                      f"correction={g['avg_correction']:+.1f}%, "
                      f"d1_up_rate={g['up_rate_d1']:.0f}%")
        print(f"\n偏差→首日上涨率映射:")
        for p in dev_params.get("prob_correction_map", []):
            print(f"  dev {p['dev_range']}: n={p['count']}, "
                  f"up_rate={p['up_rate']:.1%}, avg_d1={p['avg_day1']:+.1f}%")

    # 3. 卖出时机校准
    print("\n\n⏱️  3. 卖出时机策略校准")
    print("-" * 50)
    timing, timing_stats = calibrate_sell_timing()
    print(f"总样本: {timing_stats['total_ipos']}")
    print(f"\n按募资规模（市值代理）:")
    for g in timing["by_fundraising"]:
        if g["count"] > 0:
            print(f"  {g['label']}: n={g['count']}, best_exit={g['best_exit']} "
                  f"(expected={g['best_expected']:+.1f})")

    print(f"\n按超购倍数:")
    for g in timing["by_subscription"]:
        if g["count"] > 0:
            print(f"  {g['label']}: n={g['count']}, best_exit={g['best_exit']} "
                  f"(expected={g['best_expected']:+.1f})")
