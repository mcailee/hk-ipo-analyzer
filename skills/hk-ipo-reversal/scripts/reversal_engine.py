#!/usr/bin/env python3
"""港股新股暗盘反转猎手 V2 - 反转识别引擎 (期望偏差版)
核心升级：从"仅分析暗盘下跌"扩展为"分析暗盘表现偏差→后续修正"
关键概念：deviation = dark_return - expected_return
"""
import math
from utils import (
    mean, median, std_dev, calc_stats, safe_values,
    logistic_regression, logistic_predict_proba, logistic_accuracy, logistic_auc_approx,
    info_gain_continuous, info_gain_categorical,
    bootstrap_ci, bootstrap_proportion_ci,
    hierarchical_clustering, euclidean_distance,
    standardize, normalize_01,
    classify_market_state, label_data_market_state,
    BULL, BEAR, NEUTRAL, STATE_LABELS,
)

# ============================================
# 期望偏差推算（运行时，与 gen_enhanced_data.py 中逻辑一致）
# ============================================

def auto_estimate_expected_return(d, data):
    """基于全量数据集的分档统计映射，为单只股票推算 expected_return
    用于运行时预测模式（新股没有预存的 expected_return 时）
    """
    sub_ranges = [
        (0, 20), (20, 100), (100, 500), (500, 2000), (2000, 5000), (5000, 999999),
    ]

    sub = d.get("subscription_mult", 1)
    # 基准：同超购区间的首日涨幅均值
    baseline = 0
    for lo, hi in sub_ranges:
        group = [x for x in data
                 if x.get("subscription_mult") is not None
                 and lo <= x["subscription_mult"] < hi
                 and x.get("day1_return") is not None]
        if group and lo <= sub < hi:
            baseline = sum(x["day1_return"] for x in group) / len(group)
            break

    # 全局均值
    all_d1 = [x["day1_return"] for x in data if x.get("day1_return") is not None]
    global_avg = sum(all_d1) / len(all_d1) if all_d1 else 0

    # 基石修正
    cs_yes = [x["day1_return"] for x in data if x.get("has_cornerstone") and x.get("day1_return") is not None]
    cs_no = [x["day1_return"] for x in data if not x.get("has_cornerstone") and x.get("day1_return") is not None]
    cs_avg = sum(cs_yes) / len(cs_yes) if cs_yes else global_avg
    no_cs_avg = sum(cs_no) / len(cs_no) if cs_no else global_avg
    cs_adj = (cs_avg - global_avg) if d.get("has_cornerstone") else (no_cs_avg - global_avg)

    # 行业修正
    cat = d.get("category", "其他")
    cat_vals = [x["day1_return"] for x in data if x.get("category") == cat and x.get("day1_return") is not None]
    cat_adj = (sum(cat_vals) / len(cat_vals) - global_avg) if cat_vals else 0

    # 募资修正
    f = d.get("fundraising", 5)
    if f >= 100: fund_adj = -12
    elif f >= 50: fund_adj = -8
    elif f >= 20: fund_adj = -3
    elif f >= 10: fund_adj = 0
    elif f >= 5: fund_adj = 2
    else: fund_adj = 5

    expected = baseline * 0.6 + (baseline + cs_adj + cat_adj + fund_adj) * 0.4
    return round(expected, 1)


def compute_deviation(d, expected_return=None, data=None):
    """计算期望偏差 = dark_return - expected_return"""
    dr = d.get("dark_return")
    if dr is None:
        return None

    # 优先使用已有 deviation
    if expected_return is None and d.get("deviation") is not None:
        return d["deviation"]

    # 使用外部指定的 expected_return
    if expected_return is not None:
        return round(dr - expected_return, 1)

    # 使用数据内嵌的 expected_return
    exp = d.get("expected_return")
    if exp is not None:
        return round(dr - exp, 1)

    # 运行时推算
    if data is not None:
        exp = auto_estimate_expected_return(d, data)
        return round(dr - exp, 1)

    return None


# ============================================
# 偏差分析参数空间
# ============================================

# 偏差阈值（越负表示越不及预期）
DEVIATION_THRESHOLDS = [-5, -10, -15, -20, -25, -30, -40, -50]

# 回正观察窗口
RECOVERY_WINDOWS = [
    ("day1", "day1_return"),
    ("day3", "day3_return"),
    ("day5", "day5_return"),
    ("day7", "day7_return"),
    ("day10", "day10_return"),
]

# 修正标准（相对于暗盘表现的改善）
RECOVERY_CRITERIA = [
    ("回正(>0%)", lambda val, dark: val is not None and val > 0),
    ("超越预期", lambda val, dark, exp: val is not None and exp is not None and val > exp),
    ("修正50%偏差", lambda val, dark, exp: val is not None and exp is not None and dark is not None and (val - dark) > abs(dark - exp) * 0.5 if (dark - exp) < 0 else False),
]

# 价格路径时点
PATH_TIMEPOINTS = [
    ("暗盘", "dark_return"),
    ("Day1", "day1_return"),
    ("Day2", "day2_return"),
    ("Day3", "day3_return"),
    ("Day5", "day5_return"),
    ("Day7", "day7_return"),
    ("Day10", "day10_return"),
]

# 路径模式标签
PATTERN_LABELS = {
    0: "V型修正",
    1: "U型缓慢修正",
    2: "L型持续低迷",
    3: "断崖式下跌",
}

PATTERN_COLORS = {
    0: "#ff4444",   # V型 - 红色（好）
    1: "#ffaa00",   # U型 - 橙色（中等）
    2: "#4488ff",   # L型 - 蓝色（差）
    3: "#888888",   # 断崖 - 灰色（最差）
}

PATTERN_EMOJIS = {
    0: "📈",
    1: "📊",
    2: "📉",
    3: "💥",
}

# 偏差分类标签
DEVIATION_CATEGORIES = {
    "dark_down": "暗盘下跌",
    "below_expectation": "涨幅不及预期",
    "potential_release": "潜力释放",
    "normal": "表现正常",
}


def classify_deviation_type(d):
    """分类一只股票的偏差类型"""
    dr = d.get("dark_return")
    dev = d.get("deviation")
    d10 = d.get("day10_return")

    if dr is None:
        return "normal"

    if dr < 0:
        return "dark_down"

    if dev is not None and dev <= -10:
        return "below_expectation"

    if dr > 0 and d10 is not None and d10 - dr > 15:
        return "potential_release"

    return "normal"


# ============================================
# 1. 自动阈值寻优 (偏差版)
# ============================================

def scan_reversal_thresholds(data):
    """扫描所有偏差阈值组合，找出最优修正定义

    Returns:
        results: [{
            "deviation_threshold": -10,
            "window": "day5",
            "window_key": "day5_return",
            "criterion": "回正(>0%)",
            "total_underperform": int,
            "corrected": int,
            "correction_rate": float,
            "avg_corrected_return": float,
            "avg_uncorrected_return": float,
            "score": float,
            "bootstrap_ci": {...}
        }, ...]
        best: 最优组合
    """
    results = []

    for threshold in DEVIATION_THRESHOLDS:
        # 筛选偏差达到阈值的股票（不仅限于暗盘下跌）
        underperform = [d for d in data
                        if d.get("deviation") is not None and d["deviation"] <= threshold]

        if len(underperform) < 3:
            continue

        for win_label, win_key in RECOVERY_WINDOWS:
            # 只用第一个criterion（回正>0%）做热力图和基础分析
            for crit_label, crit_fn in [RECOVERY_CRITERIA[0]]:
                corrected = [d for d in underperform
                             if crit_fn(d.get(win_key), d.get("dark_return"))]
                uncorrected = [d for d in underperform if d not in corrected]

                n_total = len(underperform)
                n_corrected = len(corrected)
                rate = n_corrected / n_total * 100 if n_total > 0 else 0

                # 修正组的平均收益
                corr_returns = [d[win_key] for d in corrected if d.get(win_key) is not None]
                avg_corr = mean(corr_returns) if corr_returns else 0

                # 未修正组
                uncorr_returns = [d[win_key] for d in uncorrected if d.get(win_key) is not None]
                avg_uncorr = mean(uncorr_returns) if uncorr_returns else 0

                # 综合评分
                sample_weight = min(n_total / 10, 1.0)
                corr_gain = math.log(max(avg_corr + 1, 0.1)) if avg_corr > -1 else -2
                score = rate * max(corr_gain, 0) * sample_weight / 100

                # Bootstrap置信区间
                if n_total >= 5:
                    ci = bootstrap_proportion_ci(n_corrected, n_total, n_bootstrap=500)
                else:
                    ci = {"estimate": rate / 100, "ci_lower": 0, "ci_upper": 1, "std_error": 0.5}

                results.append({
                    "deviation_threshold": threshold,
                    "window": win_label,
                    "window_key": win_key,
                    "criterion": crit_label,
                    "total_underperform": n_total,
                    "corrected": n_corrected,
                    "correction_rate": rate,
                    "avg_corrected_return": avg_corr,
                    "avg_uncorrected_return": avg_uncorr,
                    "score": score,
                    "bootstrap_ci": ci,
                    # 分类统计
                    "n_dark_down": sum(1 for d in underperform if d.get("dark_return", 0) < 0),
                    "n_below_exp": sum(1 for d in underperform if d.get("dark_return", 0) >= 0),
                })

    # 按综合评分排序
    results.sort(key=lambda x: -x["score"])

    best = results[0] if results else None
    return results, best


def build_reversal_heatmap(results):
    """构建偏差阈值×窗口的修正率热力图数据"""
    heatmap = {}
    for r in results:
        if r["criterion"] != "回正(>0%)":
            continue
        t = r["deviation_threshold"]
        w = r["window"]
        if t not in heatmap:
            heatmap[t] = {}
        heatmap[t][w] = {
            "rate": r["correction_rate"],
            "count": r["total_underperform"],
            "corrected": r["corrected"],
        }
    return heatmap


# ============================================
# 2. 多因子修正分析 (偏差版)
# ============================================

def extract_reversal_features(d, data_stats=None):
    """从一条记录提取修正分析特征向量

    Returns:
        features: [f1, f2, ...] 或 None (数据不足)
        feature_names: [name1, name2, ...]
    """
    dr = d.get("dark_return")
    if dr is None:
        return None, []

    features = []
    names = []

    # F1: 超购倍数(log)
    sub = d.get("subscription_mult", 1)
    features.append(math.log(max(sub, 1)))
    names.append("超购倍数(log)")

    # F2: 基石投资者
    features.append(1.0 if d.get("has_cornerstone") else 0.0)
    names.append("基石投资者")

    # F3: 募资规模(log)
    fund = d.get("fundraising", 5)
    features.append(math.log(max(fund, 0.1)))
    names.append("募资规模(log)")

    # F4: 期望偏差 (核心新因子)
    dev = d.get("deviation")
    if dev is None:
        dev = dr  # 退化为暗盘涨跌幅
    features.append(dev)
    names.append("期望偏差")

    # F5: 偏差绝对值（偏离程度）
    features.append(abs(dev))
    names.append("偏差绝对值")

    # F6: 暗盘波动幅度 (high - low)
    dh = d.get("dark_high")
    dl = d.get("dark_low")
    if dh is not None and dl is not None:
        features.append(dh - dl)
    else:
        features.append(abs(dr) * 0.3)
    names.append("暗盘波幅")

    # F7: 首日成交量标准化
    vol = d.get("day1_turnover", 30)
    features.append(vol)
    names.append("首日换手率")

    # F8: 暗盘绝对涨跌幅（区分暗盘跌 vs 涨幅不及预期）
    features.append(dr)
    names.append("暗盘涨跌幅")

    return features, names


def train_reversal_model(data, target_window="day5_return", deviation_threshold=-10):
    """训练修正预测 Logistic 回归模型

    Args:
        data: 完整数据集
        target_window: 用哪个时点判断是否修正
        deviation_threshold: 偏差阈值

    Returns:
        model dict or None
    """
    # 筛选偏差达到阈值的样本（不再限制暗盘必须下跌）
    samples = [d for d in data
               if d.get("deviation") is not None
               and d["deviation"] <= deviation_threshold
               and d.get(target_window) is not None]

    if len(samples) < 5:
        return None

    # 构建特征和标签
    X = []
    y = []
    valid_samples = []

    for d in samples:
        feat, names = extract_reversal_features(d)
        if feat is None:
            continue
        X.append(feat)
        # 修正标准：后续收益 > 0（绝对回正）
        y.append(1 if d[target_window] > 0 else 0)
        valid_samples.append(d)

    if len(X) < 5 or sum(y) == 0 or sum(y) == len(y):
        return None

    feature_names = names

    # 标准化特征
    n_features = len(X[0])
    X_scaled = []
    scalers = []
    for j in range(n_features):
        col = [X[i][j] for i in range(len(X))]
        scaled, m, s = standardize(col)
        scalers.append((m, s))
        for i in range(len(X)):
            if len(X_scaled) <= i:
                X_scaled.append([])
            X_scaled[i].append(scaled[i] if i < len(scaled) else 0)

    # 训练
    weights, bias, history = logistic_regression(X_scaled, y, lr=0.1, epochs=2000, reg_lambda=0.1)

    # 评估
    acc = logistic_accuracy(X_scaled, y, weights, bias)
    auc = logistic_auc_approx(X_scaled, y, weights, bias)

    # 特征重要性（权重绝对值归一化）
    abs_weights = [abs(w) for w in weights]
    total = sum(abs_weights) if sum(abs_weights) > 0 else 1
    importance = {feature_names[i]: abs_weights[i] / total for i in range(n_features)}

    # 信息增益作为第二轨
    ig_values = []
    for j in range(n_features):
        col = [X[i][j] for i in range(len(X))]
        ig = info_gain_continuous(col, y)
        ig_values.append(ig)
    ig_total = sum(ig_values) if sum(ig_values) > 0 else 1
    ig_importance = {feature_names[i]: ig_values[i] / ig_total for i in range(n_features)}

    # 综合重要性 = 50% logistic + 50% IG
    combined_importance = {}
    for name in feature_names:
        combined_importance[name] = 0.5 * importance.get(name, 0) + 0.5 * ig_importance.get(name, 0)

    return {
        "weights": weights,
        "bias": bias,
        "feature_names": feature_names,
        "scalers": scalers,
        "accuracy": acc,
        "auc": auc,
        "n_samples": len(X),
        "n_positive": sum(y),
        "n_negative": len(y) - sum(y),
        "feature_importance": combined_importance,
        "logistic_importance": importance,
        "ig_importance": ig_importance,
        "training_samples": valid_samples,
        "target_window": target_window,
        "deviation_threshold": deviation_threshold,
    }


# ============================================
# 3. 价格路径聚类 (偏差版)
# ============================================

def extract_price_path(d):
    """提取价格路径向量 (暗盘→day1→day2→day3→day5→day7→day10)
    缺失值用线性插值填充
    """
    keys = ["dark_return", "day1_return", "day2_return", "day3_return",
            "day5_return", "day7_return", "day10_return"]
    raw = [d.get(k) for k in keys]

    # 线性插值填充None
    path = raw[:]
    for i in range(len(path)):
        if path[i] is None:
            prev_val = None
            next_val = None
            for j in range(i - 1, -1, -1):
                if path[j] is not None:
                    prev_val = (j, path[j])
                    break
            for j in range(i + 1, len(path)):
                if raw[j] is not None:
                    next_val = (j, raw[j])
                    break

            if prev_val and next_val:
                pi, pv = prev_val
                ni, nv = next_val
                path[i] = pv + (nv - pv) * (i - pi) / (ni - pi)
            elif prev_val:
                path[i] = prev_val[1]
            elif next_val:
                path[i] = next_val[1]
            else:
                path[i] = 0

    return path


def classify_price_patterns(data, n_clusters=4):
    """对偏差为负的股票进行价格路径聚类（不再限制暗盘必须下跌）"""
    # 分析所有偏差为负的股票
    underperform = [d for d in data
                    if d.get("deviation") is not None and d["deviation"] < 0]

    if len(underperform) < n_clusters:
        n_clusters = max(len(underperform), 1)

    paths = []
    valid_stocks = []
    for d in underperform:
        path = extract_price_path(d)
        paths.append(path)
        valid_stocks.append(d)

    if not paths:
        return {}, []

    labels = hierarchical_clustering(paths, n_clusters=n_clusters)

    # 整理结果
    clusters = {}
    for i, (d, path, label) in enumerate(zip(valid_stocks, paths, labels)):
        if label not in clusters:
            clusters[label] = {"stocks": [], "paths": []}
        clusters[label]["stocks"].append(d)
        clusters[label]["paths"].append(path)

    # 按平均最终收益排序
    cluster_end_values = {}
    for cid, cdata in clusters.items():
        end_vals = [p[-1] for p in cdata["paths"]]
        cluster_end_values[cid] = mean(end_vals)

    sorted_ids = sorted(cluster_end_values.keys(), key=lambda x: -cluster_end_values[x])

    id_map = {}
    for new_id, old_id in enumerate(sorted_ids):
        id_map[old_id] = new_id

    patterns = {}
    all_paths = []

    for old_id, cdata in clusters.items():
        new_id = id_map[old_id]
        n_pts = len(cdata["paths"][0])
        avg_path = [mean([p[t] for p in cdata["paths"]]) for t in range(n_pts)]

        stocks = cdata["stocks"]
        dark_returns = [d["dark_return"] for d in stocks if d.get("dark_return") is not None]
        day1_returns = [d["day1_return"] for d in stocks if d.get("day1_return") is not None]
        day10_returns = [d.get("day10_return") for d in stocks if d.get("day10_return") is not None]
        deviations = [d.get("deviation") for d in stocks if d.get("deviation") is not None]
        subs = [d["subscription_mult"] for d in stocks]
        cs_rate = sum(1 for d in stocks if d.get("has_cornerstone")) / len(stocks) * 100

        # 偏差类型统计
        n_dark_down = sum(1 for d in stocks if d.get("dark_return", 0) < 0)
        n_below_exp = sum(1 for d in stocks if d.get("dark_return", 0) >= 0)

        patterns[new_id] = {
            "label": PATTERN_LABELS.get(new_id, f"模式{new_id}"),
            "emoji": PATTERN_EMOJIS.get(new_id, "📊"),
            "color": PATTERN_COLORS.get(new_id, "#888"),
            "stocks": stocks,
            "avg_path": avg_path,
            "count": len(stocks),
            "characteristics": {
                "avg_dark_return": mean(dark_returns) if dark_returns else 0,
                "avg_day1_return": mean(day1_returns) if day1_returns else 0,
                "avg_day10_return": mean(day10_returns) if day10_returns else 0,
                "avg_deviation": mean(deviations) if deviations else 0,
                "avg_subscription": mean(subs) if subs else 0,
                "cornerstone_rate": cs_rate,
                "n_dark_down": n_dark_down,
                "n_below_exp": n_below_exp,
                "correction_rate": sum(1 for p in cdata["paths"] if p[-1] > p[0]) / len(cdata["paths"]) * 100,
            },
        }

        for d, path in zip(stocks, cdata["paths"]):
            all_paths.append((d, path, new_id))

    return patterns, all_paths


# ============================================
# 4. 交叉维度分析 (偏差版)
# ============================================

def analyze_reversal_by_dimension(data, dim_name, dim_fn, deviation_threshold=-10,
                                   recovery_key="day5_return"):
    """按维度分组分析修正率"""
    groups = {}
    for d in data:
        key = dim_fn(d)
        if key is None:
            continue
        groups.setdefault(key, []).append(d)

    results = []
    for g_key in sorted(groups.keys(), key=str):
        group = groups[g_key]
        underperform = [d for d in group
                        if d.get("deviation") is not None and d["deviation"] <= deviation_threshold]
        corrected = [d for d in underperform
                     if d.get(recovery_key) is not None and d[recovery_key] > 0]

        n_underperform = len(underperform)
        n_corrected = len(corrected)

        dev_values = [d["deviation"] for d in underperform if d.get("deviation") is not None]
        corr_returns = [d[recovery_key] for d in corrected if d.get(recovery_key) is not None]

        results.append({
            "dim_label": str(g_key),
            "total": len(group),
            "underperform": n_underperform,
            "corrected": n_corrected,
            "correction_rate": n_corrected / n_underperform * 100 if n_underperform > 0 else 0,
            "avg_deviation": mean(dev_values) if dev_values else 0,
            "avg_correction_return": mean(corr_returns) if corr_returns else 0,
        })

    return results


def get_sub_range_label(d):
    mult = d.get("subscription_mult", 0)
    if mult < 20: return "< 20倍"
    if mult < 100: return "20-100倍"
    if mult < 500: return "100-500倍"
    if mult < 2000: return "500-2000倍"
    if mult < 5000: return "2000-5000倍"
    return "> 5000倍"

def get_fundraising_label(d):
    f = d.get("fundraising", 0)
    if f < 5: return "< 5亿"
    if f < 20: return "5-20亿"
    if f < 50: return "20-50亿"
    if f < 100: return "50-100亿"
    return "> 100亿"

def get_deviation_type_label(d):
    dt = classify_deviation_type(d)
    return DEVIATION_CATEGORIES.get(dt, "其他")


# ============================================
# 5. 潜力释放分析 (新增)
# ============================================

def analyze_potential_release(data, threshold_pp=15):
    """识别暗盘小涨但后续大幅补涨的股票

    条件: dark_return > 0 且 max(day5, day10) - dark_return > threshold_pp

    Returns:
        cases: [{"stock": d, "dark": float, "peak": float, "release_pp": float,
                 "path": [...], "characteristics": {...}}, ...]
        summary: dict with 共性特征统计
    """
    cases = []
    for d in data:
        dr = d.get("dark_return")
        if dr is None or dr <= 0:
            continue

        d5 = d.get("day5_return")
        d7 = d.get("day7_return")
        d10 = d.get("day10_return")

        peak = max(v for v in [d5, d7, d10] if v is not None) if any(v is not None for v in [d5, d7, d10]) else dr
        release_pp = peak - dr

        if release_pp > threshold_pp:
            path = extract_price_path(d)
            cases.append({
                "stock": d,
                "dark": dr,
                "peak": peak,
                "release_pp": release_pp,
                "path": path,
                "deviation": d.get("deviation"),
                "expected_return": d.get("expected_return"),
            })

    cases.sort(key=lambda x: -x["release_pp"])

    # 共性特征统计
    summary = {}
    if cases:
        stocks = [c["stock"] for c in cases]
        summary = {
            "count": len(cases),
            "avg_dark_return": mean([c["dark"] for c in cases]),
            "avg_release_pp": mean([c["release_pp"] for c in cases]),
            "avg_subscription": mean([s["subscription_mult"] for s in stocks]),
            "cornerstone_rate": sum(1 for s in stocks if s.get("has_cornerstone")) / len(stocks) * 100,
            "avg_fundraising": mean([s.get("fundraising", 0) for s in stocks]),
            "top_categories": _top_categories(stocks),
            "avg_deviation": mean([c["deviation"] for c in cases if c["deviation"] is not None]),
        }

    return cases, summary


def _top_categories(stocks):
    """统计TOP行业"""
    counts = {}
    for s in stocks:
        cat = s.get("category", "其他")
        counts[cat] = counts.get(cat, 0) + 1
    return sorted(counts.items(), key=lambda x: -x[1])[:5]


# ============================================
# 6. 单股分析 (偏差版)
# ============================================

def analyze_single_reversal(target, data, model=None):
    """分析单只股票的修正路径和特征"""
    path = extract_price_path(target)

    dr = target.get("dark_return", 0)
    dev = target.get("deviation")
    exp = target.get("expected_return")
    d1 = target.get("day1_return", 0)
    d5 = target.get("day5_return")
    d10 = target.get("day10_return")

    # 偏差类型
    dev_type = classify_deviation_type(target)

    # 修正判定
    is_underperform = dev is not None and dev < 0
    recovery_points = {}
    for label, key in [("Day1", "day1_return"), ("Day3", "day3_return"),
                       ("Day5", "day5_return"), ("Day7", "day7_return"),
                       ("Day10", "day10_return")]:
        val = target.get(key)
        if val is not None:
            recovery_points[label] = val

    # 最终结局
    final_key = "day10_return"
    final_val = target.get(final_key)
    if final_val is None:
        final_key = "day5_return"
        final_val = target.get(final_key)

    # 是否修正成功：后续表现改善（绝对回正 或 相对暗盘有显著改善）
    did_correct = False
    if is_underperform and final_val is not None:
        if final_val > 0:
            did_correct = True  # 绝对回正
        elif dr is not None and final_val > dr + 10:
            did_correct = True  # 相对暗盘改善10pp以上

    # 找同类比较（按偏差类型）
    similar_pool = [d for d in data
                    if d.get("deviation") is not None and d["deviation"] < 0
                    and d["code"] != target["code"]]

    target_feat, _ = extract_reversal_features(target)
    similar = []
    if target_feat:
        for d in similar_pool:
            feat, _ = extract_reversal_features(d)
            if feat:
                dist = euclidean_distance(target_feat, feat)
                sim = 1.0 / (1.0 + dist)
                similar.append((sim, d))
        similar.sort(key=lambda x: -x[0])

    return {
        "target": target,
        "path": path,
        "path_labels": [l for l, _ in PATH_TIMEPOINTS],
        "is_underperform": is_underperform,
        "did_correct": did_correct,
        "deviation_type": dev_type,
        "deviation_type_label": DEVIATION_CATEGORIES.get(dev_type, "其他"),
        "deviation": dev,
        "expected_return": exp,
        "recovery_points": recovery_points,
        "final_key": final_key,
        "final_val": final_val,
        "similar_cases": similar[:8],
    }


# ============================================
# 7. 综合报告数据生成 (偏差版)
# ============================================

def run_full_analysis(data, hsi_monthly):
    """运行完整的偏差修正分析流程"""
    # 0. 标注市场状态
    label_data_market_state(data, hsi_monthly)

    # 1. 基础统计 (偏差视角)
    total = len(data)
    underperform = [d for d in data
                    if d.get("deviation") is not None and d["deviation"] < 0]
    overperform = [d for d in data
                   if d.get("deviation") is not None and d["deviation"] >= 0]

    # 同时保留暗盘涨跌统计（兼容性）
    dark_down = [d for d in data
                 if d.get("dark_return") is not None and d["dark_return"] < 0]
    dark_up = [d for d in data
               if d.get("dark_return") is not None and d["dark_return"] >= 0]

    # 偏差分类统计
    dev_types = {}
    for d in data:
        dt = classify_deviation_type(d)
        dev_types.setdefault(dt, []).append(d)

    # 2. 自动阈值寻优
    threshold_results, best_threshold = scan_reversal_thresholds(data)

    # 3. 热力图数据
    heatmap = build_reversal_heatmap(threshold_results)

    # 4. 训练修正模型（用最优窗口）
    best_window = best_threshold["window_key"] if best_threshold else "day5_return"
    best_dev = best_threshold["deviation_threshold"] if best_threshold else -10
    model = train_reversal_model(data, target_window=best_window, deviation_threshold=best_dev)

    # 多窗口模型
    models_by_window = {}
    for win_label, win_key in RECOVERY_WINDOWS:
        m = train_reversal_model(data, target_window=win_key, deviation_threshold=-10)
        if m:
            models_by_window[win_label] = m

    # 5. 价格路径聚类
    patterns, all_paths = classify_price_patterns(data)

    # 6. 潜力释放分析
    pr_cases, pr_summary = analyze_potential_release(data)

    # 7. 交叉维度分析
    cross_by_sub = analyze_reversal_by_dimension(
        data, "超购区间", get_sub_range_label, deviation_threshold=-10)
    cross_by_cat = analyze_reversal_by_dimension(
        data, "行业", lambda d: d.get("category", "其他"), deviation_threshold=-10)
    cross_by_cs = analyze_reversal_by_dimension(
        data, "基石", lambda d: "有基石" if d.get("has_cornerstone") else "无基石",
        deviation_threshold=-10)
    cross_by_market = analyze_reversal_by_dimension(
        data, "市场状态",
        lambda d: STATE_LABELS.get(d.get("_market_state", NEUTRAL), "⚖️ 震荡"),
        deviation_threshold=-10)
    cross_by_devtype = analyze_reversal_by_dimension(
        data, "偏差类型", get_deviation_type_label, deviation_threshold=-10)

    # 8. Top修正案例
    top_corrections = []
    for d in underperform:
        d10 = d.get("day10_return")
        d5 = d.get("day5_return")
        final = d10 if d10 is not None else d5
        if final is not None and final > 0:
            recovery = final - (d.get("dark_return") or 0)
            top_corrections.append({
                "stock": d,
                "dark_return": d.get("dark_return", 0),
                "deviation": d.get("deviation", 0),
                "expected_return": d.get("expected_return", 0),
                "final_return": final,
                "recovery": recovery,
                "deviation_type": classify_deviation_type(d),
                "path": extract_price_path(d),
            })
    top_corrections.sort(key=lambda x: -x["recovery"])

    return {
        "total": total,
        "underperform_count": len(underperform),
        "overperform_count": len(overperform),
        "dark_down_count": len(dark_down),
        "dark_up_count": len(dark_up),
        "deviation_types": {k: len(v) for k, v in dev_types.items()},
        "underperform_stats": calc_stats(underperform, "deviation"),
        "overperform_stats": calc_stats(overperform, "deviation"),
        "dark_down_stats": calc_stats(dark_down, "dark_return"),
        "threshold_results": threshold_results[:30],
        "best_threshold": best_threshold,
        "heatmap": heatmap,
        "model": model,
        "models_by_window": models_by_window,
        "patterns": patterns,
        "all_paths": all_paths,
        "potential_release": {"cases": pr_cases, "summary": pr_summary},
        "cross_by_sub": cross_by_sub,
        "cross_by_cat": cross_by_cat,
        "cross_by_cs": cross_by_cs,
        "cross_by_market": cross_by_market,
        "cross_by_devtype": cross_by_devtype,
        "top_corrections": top_corrections[:10],
        "data": data,
    }
