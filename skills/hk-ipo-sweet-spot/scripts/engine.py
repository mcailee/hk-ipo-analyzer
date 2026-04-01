#!/usr/bin/env python3
"""港股打新甜蜜区间分析器 - 分析引擎模块 V3.5 (Ensemble 混合版)
包含：基础统计、手写矩阵运算、Ridge回归、信息增益、多因子评分、卖出时点分析、
     季节性分析、相似度匹配(小样本保护)、Ensemble混合、暗盘联动修正

V3.5 改进：
  - 小样本降级保护：二值维度(基石/18C)动态权重缩放
  - 行业分层相似度：科技/医药/消费/工业/金融 5 大近亲组
  - 相似度+区间 Ensemble 混合：避免单一方法的极端失真
  - 18C 惩罚行业差异化：医药-10%/非医药-4%/有基石-2%
"""
import math

# ============================================
# 工具函数
# ============================================

def safe_values(data, key):
    """提取非None值"""
    return [d[key] for d in data if d.get(key) is not None]

def median(values):
    if not values: return 0
    s = sorted(values)
    n = len(s)
    return s[n//2] if n % 2 == 1 else (s[n//2-1] + s[n//2]) / 2

def calc_stats(group, return_key="day1_return"):
    """通用统计计算，null-safe"""
    returns = [d[return_key] for d in group if d.get(return_key) is not None]
    if not returns: return {"count": 0, "avg": 0, "median": 0, "win_rate": 0, "max": 0, "min": 0, "expected": 0}
    n = len(returns)
    winners = [r for r in returns if r > 0]
    losers = [r for r in returns if r < 0]
    avg_win = sum(winners)/len(winners) if winners else 0
    avg_loss = sum(losers)/len(losers) if losers else 0
    wr = len(winners)/n*100
    exp = (len(winners)/n)*avg_win + (len(losers)/n)*avg_loss if n > 0 else 0
    return {"count": n, "avg": sum(returns)/n, "median": median(returns),
            "win_rate": wr, "max": max(returns), "min": min(returns), "expected": exp,
            "avg_win": avg_win, "avg_loss": avg_loss}

# ============================================
# 基础分析模块 (V1升级版，null-safe)
# ============================================

RANGES = [
    ("< 20倍(冷门)", 0, 20), ("20-100倍(温和)", 20, 100),
    ("100-500倍(热门)", 100, 500), ("500-2000倍(火爆)", 500, 2000),
    ("2000-5000倍(疯狂)", 2000, 5000), ("> 5000倍(极端)", 5000, 999999),
]

def analyze_by_subscription_range(data):
    results = []
    for label, low, high in RANGES:
        group = [d for d in data if low <= d["subscription_mult"] < high]
        s = calc_stats(group)
        cs_count = sum(1 for d in group if d["has_cornerstone"])
        s["label"] = label
        s["cornerstone_rate"] = cs_count/len(group)*100 if group else 0
        s["avg_fundraising"] = sum(d["fundraising"] for d in group)/len(group) if group else 0
        s["stocks"] = group
        results.append(s)
    return results


def find_sweet_spot_range(range_results):
    """从区间分析结果中动态计算甜蜜区间
    规则：期望收益最高的区间（需样本>=5），返回其 label
    如有多个期望收益接近的（差距<5%），取胜率更高的
    """
    candidates = [r for r in range_results if r["count"] >= 5 and r.get("expected", 0) > 0]
    if not candidates:
        return range_results[0]["label"] if range_results else "N/A"
    # 按期望收益降序
    candidates.sort(key=lambda x: (-x["expected"], -x["win_rate"]))
    return candidates[0]["label"]


def analyze_by_cornerstone(data):
    def stats(g):
        s = calc_stats(g)
        return {"count": s["count"], "avg_return": s["avg"], "win_rate": s["win_rate"], "median_return": s["median"]}
    return {"with": stats([d for d in data if d["has_cornerstone"]]),
            "without": stats([d for d in data if not d["has_cornerstone"]])}

def analyze_by_category(data):
    cats = {}
    for d in data:
        cats.setdefault(d["category"], []).append(d)
    results = []
    for cat, group in sorted(cats.items(), key=lambda x: -len(x[1])):
        s = calc_stats(group)
        results.append({"category": cat, "count": s["count"], "avg_return": s["avg"], "win_rate": s["win_rate"], "median_return": s["median"]})
    return results

def analyze_fundraising_vs_return(data):
    ranges = [("< 5亿", 0, 5), ("5-20亿", 5, 20), ("20-50亿", 20, 50), ("50-100亿", 50, 100), ("> 100亿", 100, 99999)]
    results = []
    for label, low, high in ranges:
        group = [d for d in data if low <= d["fundraising"] < high]
        if not group: continue
        s = calc_stats(group)
        results.append({"label": label, "count": s["count"], "avg_return": s["avg"], "win_rate": s["win_rate"], "median_return": s["median"]})
    return results

# ============================================
# 手写矩阵运算（用于多元线性回归）
# ============================================

def mat_zeros(rows, cols):
    return [[0.0]*cols for _ in range(rows)]

def mat_multiply(A, B):
    ra, ca = len(A), len(A[0])
    rb, cb = len(B), len(B[0])
    assert ca == rb
    C = mat_zeros(ra, cb)
    for i in range(ra):
        for j in range(cb):
            for k in range(ca):
                C[i][j] += A[i][k] * B[k][j]
    return C

def mat_transpose(A):
    r, c = len(A), len(A[0])
    return [[A[i][j] for i in range(r)] for j in range(c)]

def mat_inverse(A):
    """高斯-约旦消元法求逆"""
    n = len(A)
    M = [row[:] + [1.0 if i == j else 0.0 for j in range(n)] for i, row in enumerate(A)]
    for col in range(n):
        max_row = col
        for row in range(col+1, n):
            if abs(M[row][col]) > abs(M[max_row][col]):
                max_row = row
        M[col], M[max_row] = M[max_row], M[col]
        if abs(M[col][col]) < 1e-12:
            return None  # 奇异矩阵
        pivot = M[col][col]
        for j in range(2*n):
            M[col][j] /= pivot
        for row in range(n):
            if row != col:
                factor = M[row][col]
                for j in range(2*n):
                    M[row][j] -= factor * M[col][j]
    return [row[n:] for row in M]

def ols_regression(X, y, sample_weights=None):
    """正规方程: beta = (X'X)^-1 X'y
    支持加权回归：当 sample_weights 不为 None 时，使用 WLS
    """
    n = len(y)
    if sample_weights:
        # 加权最小二乘 (WLS): 对 X 和 y 乘以 sqrt(w)
        sw = [w ** 0.5 for w in sample_weights]
        Xw = [[X[i][j] * sw[i] for j in range(len(X[0]))] for i in range(n)]
        yw = [y[i] * sw[i] for i in range(n)]
    else:
        Xw, yw = X, y

    Xt = mat_transpose(Xw)
    XtX = mat_multiply(Xt, Xw)
    XtX_inv = mat_inverse(XtX)
    if XtX_inv is None:
        return None, 0
    Xty = mat_multiply(Xt, [[yi] for yi in yw])
    beta = mat_multiply(XtX_inv, Xty)
    beta = [b[0] for b in beta]
    # R^2 (基于原始 X, y 计算，非加权)
    y_mean = sum(y)/len(y)
    y_pred = [sum(X[i][j]*beta[j] for j in range(len(beta))) for i in range(n)]
    ss_res = sum((y[i]-y_pred[i])**2 for i in range(n))
    ss_tot = sum((yi-y_mean)**2 for yi in y)
    r2 = 1 - ss_res/ss_tot if ss_tot > 0 else 0
    return beta, r2


def ridge_regression(X, y, lam=1.0, sample_weights=None):
    """Ridge 回归 (L2 正则化): beta = (X'WX + λI)^-1 X'Wy
    λ 控制正则化强度。截距项不做正则化。
    """
    n = len(y)
    p = len(X[0])

    if sample_weights:
        sw = [w ** 0.5 for w in sample_weights]
        Xw = [[X[i][j] * sw[i] for j in range(p)] for i in range(n)]
        yw = [y[i] * sw[i] for i in range(n)]
    else:
        Xw, yw = X, y

    Xt = mat_transpose(Xw)
    XtX = mat_multiply(Xt, Xw)

    # 加 λI（截距项 index=0 不正则化）
    for j in range(p):
        if j > 0:
            XtX[j][j] += lam

    XtX_inv = mat_inverse(XtX)
    if XtX_inv is None:
        return None, 0
    Xty = mat_multiply(Xt, [[yi] for yi in yw])
    beta = mat_multiply(XtX_inv, Xty)
    beta = [b[0] for b in beta]

    # R^2 (基于原始 X, y)
    y_mean = sum(y) / len(y)
    y_pred = [sum(X[i][j] * beta[j] for j in range(p)) for i in range(n)]
    ss_res = sum((y[i] - y_pred[i]) ** 2 for i in range(n))
    ss_tot = sum((yi - y_mean) ** 2 for yi in y)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0
    return beta, r2

# ============================================
# 手写信息增益算法
# ============================================

def entropy(labels):
    n = len(labels)
    if n == 0: return 0
    counts = {}
    for l in labels:
        counts[l] = counts.get(l, 0) + 1
    h = 0
    for c in counts.values():
        p = c / n
        h -= p * math.log2(p) if p > 0 else 0
    return h

def info_gain_continuous(feature, labels):
    """连续变量的最优二分割信息增益"""
    if not feature: return 0
    paired = sorted(zip(feature, labels))
    base_ent = entropy(labels)
    best_ig = 0
    n = len(paired)
    for i in range(1, n):
        if paired[i][0] == paired[i-1][0]: continue
        left_labels = [p[1] for p in paired[:i]]
        right_labels = [p[1] for p in paired[i:]]
        ig = base_ent - (len(left_labels)/n)*entropy(left_labels) - (len(right_labels)/n)*entropy(right_labels)
        if ig > best_ig:
            best_ig = ig
    return best_ig

def info_gain_categorical(feature, labels):
    """分类变量的信息增益"""
    if not feature: return 0
    base_ent = entropy(labels)
    groups = {}
    for f, l in zip(feature, labels):
        groups.setdefault(f, []).append(l)
    n = len(labels)
    cond_ent = sum((len(g)/n)*entropy(g) for g in groups.values())
    return base_ent - cond_ent

# ============================================
# 多因子评分引擎
# ============================================

def _leave_one_out_encoding(valid):
    """Leave-one-out 目标编码：避免数据泄露
    每只股票的行业编码 = 排除自身后该行业的 day1_return 均值
    返回: (cat_encoding_global, loo_values)
      - cat_encoding_global: 全局编码（用于预测新股）
      - loo_values: 每条记录对应的 LOO 编码值列表
    """
    cat_groups = {}
    for d in valid:
        cat_groups.setdefault(d["category"], []).append(d["day1_return"])
    # 全局编码（供预测时使用，不存在泄露问题）
    cat_encoding_global = {cat: sum(rs)/len(rs) for cat, rs in cat_groups.items()}
    # LOO 编码（训练时使用）
    cat_sums = {cat: sum(rs) for cat, rs in cat_groups.items()}
    cat_counts = {cat: len(rs) for cat, rs in cat_groups.items()}
    loo_values = []
    for d in valid:
        cat = d["category"]
        n = cat_counts[cat]
        if n > 1:
            loo_val = (cat_sums[cat] - d["day1_return"]) / (n - 1)
        else:
            loo_val = 0.0  # 该行业仅此一只，无法LOO，用0
        loo_values.append(loo_val)
    return cat_encoding_global, loo_values


def _winsorize(values, lower_pct=5, upper_pct=95):
    """Winsorize 缩尾处理：将超出指定百分位的值截断到边界
    减少极端值（如 +364%、-92%）对 OLS 回归的过度影响
    """
    if not values:
        return values
    s = sorted(values)
    n = len(s)
    lo_idx = max(0, int(n * lower_pct / 100))
    hi_idx = min(n - 1, int(n * upper_pct / 100))
    lo_val = s[lo_idx]
    hi_val = s[hi_idx]
    return [max(lo_val, min(hi_val, v)) for v in values]


def _time_decay_weights(dates, half_life_months=12):
    """计算时间衰减权重：越近的样本权重越大
    使用指数衰减：w = exp(-λ * months_ago)
    half_life_months: 半衰期（月），默认12个月
    """
    if not dates:
        return []
    # 解析日期为 (year, month) 元组
    parsed = []
    for d in dates:
        parts = d.split("-")
        parsed.append((int(parts[0]), int(parts[1])))
    # 找最新日期
    max_ym = max(parsed, key=lambda x: x[0] * 12 + x[1])
    max_months = max_ym[0] * 12 + max_ym[1]
    # 计算各样本距今月数和衰减权重
    lam = math.log(2) / half_life_months
    weights = []
    for y, m in parsed:
        months_ago = max_months - (y * 12 + m)
        w = math.exp(-lam * months_ago)
        weights.append(w)
    # 归一化（使均值=1，不改变 OLS 的尺度）
    mean_w = sum(weights) / len(weights)
    weights = [w / mean_w for w in weights]
    return weights


def _zscore_standardize(features):
    """对特征列表做 z-score 标准化，返回 (standardized, mean, std)"""
    n = len(features)
    if n == 0:
        return [], 0, 1
    mean = sum(features) / n
    var = sum((x - mean) ** 2 for x in features) / n
    std = var ** 0.5 if var > 0 else 1.0
    standardized = [(x - mean) / std for x in features]
    return standardized, mean, std


def compute_factor_weights(data):
    """双轨法：Ridge回归 + 信息增益 (V3.2)
    改进点：
      1. OLS 前对特征做 z-score 标准化，使回归系数可直接比较
      2. 行业目标编码使用 leave-one-out 避免数据泄露
      3. Winsorize 缩尾处理 y（5%-95%），减少极端值影响
      4. Ridge 回归 (L2 正则化) 替代 OLS，提高小样本稳定性
      5. 增加 log_sub² 二次项，捕捉超购与收益的非线性关系
      6. 时间衰减权重：近期样本权重更大（半衰期 12 个月）
    """
    valid = [d for d in data if d.get("day1_return") is not None]
    if len(valid) < 10:
        return {"subscription": 0.3, "cornerstone": 0.2, "industry": 0.25, "fundraising": 0.25}, {}

    # 行业目标编码 (leave-one-out)
    cat_encoding, loo_cat_values = _leave_one_out_encoding(valid)

    # 提取原始特征（未标准化）
    y_raw = [d["day1_return"] for d in valid]
    raw_x1 = [math.log(max(d["subscription_mult"], 1)) for d in valid]  # 超购(对数)
    raw_x2 = [1.0 if d["has_cornerstone"] else 0.0 for d in valid]     # 基石
    raw_x3 = loo_cat_values                                              # 行业(LOO编码)
    raw_x4 = [math.log(max(d["fundraising"], 0.1)) for d in valid]     # 募资(对数)

    # [V3.2] Winsorize: 缩尾处理 y，减少诺比侃(+364%)等极端值对回归的影响
    y = _winsorize(y_raw, lower_pct=5, upper_pct=95)

    # [V3.2] 非线性项：超购二次项，捕捉倒U型关系（甜蜜区间效应）
    raw_x1_sq = [x * x for x in raw_x1]

    # z-score 标准化（用于回归，使系数可直接比较重要性）
    z_x1, mu1, sd1 = _zscore_standardize(raw_x1)
    z_x1_sq, mu1sq, sd1sq = _zscore_standardize(raw_x1_sq)
    z_x2, mu2, sd2 = _zscore_standardize(raw_x2)
    z_x3, mu3, sd3 = _zscore_standardize(raw_x3)
    z_x4, mu4, sd4 = _zscore_standardize(raw_x4)

    # 特征矩阵: [截距, 超购, 超购², 基石, 行业, 募资]
    X_std = [[1.0, z_x1[i], z_x1_sq[i], z_x2[i], z_x3[i], z_x4[i]] for i in range(len(valid))]

    # [V3.2] 时间衰减权重
    dates = [d["date"] for d in valid]
    time_weights = _time_decay_weights(dates, half_life_months=12)

    # 1) Ridge 回归权重（L2正则化 + 时间衰减加权）
    # 自动选择 λ：数据量小时用较大 λ（更强正则化）
    n_samples = len(valid)
    lam = max(0.5, 5.0 - n_samples / 30.0)  # 30样本→λ=4, 60→λ=3, 128→λ=0.7
    beta_std, r2_ridge = ridge_regression(X_std, y, lam=lam,
                                          sample_weights=time_weights if time_weights else None)

    # 同时跑 OLS 做对比
    beta_ols, r2_ols = ols_regression(X_std, y,
                                       sample_weights=time_weights if time_weights else None)

    if beta_std is None:
        reg_weights_5 = [0.2, 0.2, 0.2, 0.2, 0.2]
    else:
        # 标准化系数（排除截距），5个因子: sub, sub², cs, ind, fund
        raw_w = [abs(b) for b in beta_std[1:]]
        total = sum(raw_w)
        reg_weights_5 = [w/total for w in raw_w] if total > 0 else [0.2]*5

    # 将 sub 和 sub² 的权重合并为一个"超购"总权重
    reg_sub_combined = reg_weights_5[0] + reg_weights_5[1]
    reg_weights = [reg_sub_combined, reg_weights_5[2], reg_weights_5[3], reg_weights_5[4]]
    rw_total = sum(reg_weights)
    reg_weights = [w/rw_total for w in reg_weights] if rw_total > 0 else [0.25]*4

    # 2) 信息增益权重（使用原始特征，不需要标准化）
    labels = [1 if r > 0 else 0 for r in y_raw]  # IG 用原始 y 的二分类
    ig_sub = info_gain_continuous(raw_x1, labels)
    ig_cs = info_gain_categorical([d["has_cornerstone"] for d in valid], labels)
    ig_ind = info_gain_categorical([d["category"] for d in valid], labels)
    ig_fund = info_gain_continuous(raw_x4, labels)
    ig_raw = [ig_sub, ig_cs, ig_ind, ig_fund]
    ig_total = sum(ig_raw)
    ig_weights = [w/ig_total for w in ig_raw] if ig_total > 0 else [0.25]*4

    # 最终权重 = 50%回归 + 50%信息增益
    final = [(reg_weights[i]*0.5 + ig_weights[i]*0.5) for i in range(4)]
    f_total = sum(final)
    final = [w/f_total for w in final] if f_total > 0 else [0.25]*4

    names = ["subscription", "cornerstone", "industry", "fundraising"]
    weights = {names[i]: final[i] for i in range(4)}

    # 保存归一化统计量，供 score_ipo 动态归一化使用
    norm_stats = {
        "sub": {"min": min(raw_x1), "max": max(raw_x1)},
        "ind": {"min": min(loo_cat_values), "max": max(loo_cat_values)},
        "fund": {"min": min(raw_x4), "max": max(raw_x4)},
    }

    # 非线性评分参数：保存 sub² 的系数符号，用于 score_ipo 判断倒U型
    sub_sq_effect = beta_std[2] if beta_std and len(beta_std) > 2 else 0

    extra = {"r2": r2_ridge, "r2_ols": r2_ols,
             "reg_weights": dict(zip(names, reg_weights)),
             "ig_weights": dict(zip(names, ig_weights)), "cat_encoding": cat_encoding,
             "beta_std": beta_std, "norm_stats": norm_stats,
             "lambda": lam, "sub_sq_effect": sub_sq_effect,
             "winsorize_bounds": {"lo": sorted(y_raw)[max(0, int(len(y_raw)*0.05))],
                                  "hi": sorted(y_raw)[min(len(y_raw)-1, int(len(y_raw)*0.95))]},
             "time_decay_half_life": 12}
    return weights, extra

def score_ipo(ipo, weights, cat_encoding, norm_stats=None, extra=None):
    """计算单只新股综合评分(0-100)
    改进点：
      - 归一化范围从训练集数据动态计算
      - 超购二次项效应：若回归发现倒U型关系，对极端超购施加惩罚
      - [V3.4] 18C 风险惩罚：无基石18C股额外扣分
    """
    # 动态归一化参数（来自训练集的 min/max）
    if norm_stats:
        sub_min = norm_stats["sub"]["min"]
        sub_max = norm_stats["sub"]["max"]
        ind_min = norm_stats["ind"]["min"]
        ind_max = norm_stats["ind"]["max"]
        fund_min = norm_stats["fund"]["min"]
        fund_max = norm_stats["fund"]["max"]
    else:
        # 降级：无统计量时用经验值（向后兼容）
        sub_min, sub_max = 0, 10.0
        ind_min, ind_max = -50, 150
        fund_min, fund_max = -2.3, 6.0

    sub_log = math.log(max(ipo["subscription_mult"], 1))
    sub_span = sub_max - sub_min if sub_max > sub_min else 1
    sub_norm = min(max((sub_log - sub_min) / sub_span, 0), 1)

    cs_norm = 1.0 if ipo["has_cornerstone"] else 0.0

    ind_raw = cat_encoding.get(ipo["category"], 0)
    ind_span = ind_max - ind_min if ind_max > ind_min else 1
    ind_norm = min(max((ind_raw - ind_min) / ind_span, 0), 1)

    fund_log = math.log(max(ipo["fundraising"], 0.1))
    fund_span = fund_max - fund_min if fund_max > fund_min else 1
    # 小盘股评分更高（募资额小=好），所以反向归一化
    fund_norm = min(max(1.0 - (fund_log - fund_min) / fund_span, 0), 1)

    score = (sub_norm * weights.get("subscription", 0.25) +
             cs_norm * weights.get("cornerstone", 0.25) +
             ind_norm * weights.get("industry", 0.25) +
             fund_norm * weights.get("fundraising", 0.25))

    # [V3.2] 非线性调整：若回归检测到超购二次项为负（倒U型），
    # 对极端超购区间（>95%分位）施加轻微惩罚
    if extra and extra.get("sub_sq_effect", 0) < -1.0:
        # 超购越偏离中心（甜蜜区间），惩罚越大
        # sub_norm > 0.9 意味着极端超购，最多惩罚 5%
        if sub_norm > 0.9:
            penalty = (sub_norm - 0.9) * 0.5  # 0-5%
            score = score * (1 - penalty)

    # [V3.5] 18C 风险惩罚（行业差异化）
    # V3.4一刀切(-8%无基石/-3%有基石)对非医药18C过度惩罚
    # 事实：医药18C无基石3只全崩(翰思艾泰+2%→-46%/华芢-25%/拔康-32%)
    #       但科技18C表现差异大(MiniMax+109%/傅里叶+111.5%暗盘)
    # V3.5: 按行业差异化惩罚力度
    is_18c = ipo.get("is_18c", False)
    if is_18c:
        category = ipo.get("category", "其他")
        is_med_group = _get_industry_group(category) == "医药"
        if not ipo.get("has_cornerstone", False):
            if is_med_group:
                # 医药18C无基石：强惩罚 10%（三只全崩）
                score = score * 0.90
            else:
                # 非医药18C无基石：轻惩罚 4%（样本少但不全是负面）
                score = score * 0.96
        else:
            # 有基石18C：统一轻惩罚 2%（有基石保护，风险可控）
            score = score * 0.98

    return min(max(score * 100, 0), 100)

def get_tier(score):
    if score >= 80: return "S"
    if score >= 60: return "A"
    if score >= 40: return "B"
    if score >= 20: return "C"
    return "D"

TIER_COLORS = {"S": "#ff4444", "A": "#ff8c00", "B": "#ffaa00", "C": "#888", "D": "#00b050"}

def analyze_by_score_tier(data, weights, cat_encoding, norm_stats=None, extra=None):
    """按评分档位分组统计"""
    tiers = {"S": [], "A": [], "B": [], "C": [], "D": []}
    for d in data:
        s = score_ipo(d, weights, cat_encoding, norm_stats, extra)
        d["_score"] = s
        d["_tier"] = get_tier(s)
        tiers[d["_tier"]].append(d)
    results = []
    for tier in ["S", "A", "B", "C", "D"]:
        group = tiers[tier]
        s = calc_stats(group)
        s["tier"] = tier
        s["stocks"] = group
        s["avg_score"] = sum(d["_score"] for d in group)/len(group) if group else 0
        results.append(s)
    return results

# ============================================
# 卖出时点分析
# ============================================

TIMEPOINTS = [
    ("暗盘", "dark_return"), ("首日", "day1_return"),
    ("第3天", "day3_return"), ("第5天", "day5_return"),
]

def analyze_selling_timepoints(data):
    """全链条卖出时点对比"""
    results = []
    for label, key in TIMEPOINTS:
        s = calc_stats(data, key)
        s["label"] = label
        s["key"] = key
        results.append(s)
    return results

def analyze_timepoint_by_dimension(data, dim_name, dim_fn, dim_labels=None):
    """交叉维度：各卖出时点 x 指定维度"""
    groups = {}
    for d in data:
        key = dim_fn(d)
        if key is None: continue
        groups.setdefault(key, []).append(d)

    results = []
    order = dim_labels if dim_labels else sorted(groups.keys(), key=str)
    for g_key in order:
        if g_key not in groups: continue
        group = groups[g_key]
        row = {"dim_label": str(g_key), "count": len(group), "timepoints": []}
        for tp_label, tp_key in TIMEPOINTS:
            s = calc_stats(group, tp_key)
            s["label"] = tp_label
            row["timepoints"].append(s)
        # 找最优卖出时点
        valid_tps = [tp for tp in row["timepoints"] if tp["count"] > 0]
        if valid_tps:
            best = max(valid_tps, key=lambda x: x["expected"])
            row["best_timepoint"] = best["label"]
            row["best_expected"] = best["expected"]
        else:
            row["best_timepoint"] = "N/A"
            row["best_expected"] = 0
        results.append(row)
    return results

def get_sub_range_label(d):
    mult = d["subscription_mult"]
    if mult < 20: return "< 20倍"
    if mult < 100: return "20-100倍"
    if mult < 500: return "100-500倍"
    if mult < 2000: return "500-2000倍"
    if mult < 5000: return "2000-5000倍"
    return "> 5000倍"

def get_fundraising_label(d):
    f = d["fundraising"]
    if f < 5: return "< 5亿"
    if f < 20: return "5-20亿"
    if f < 50: return "20-50亿"
    if f < 100: return "50-100亿"
    return "> 100亿"

# ============================================
# 季节性分析
# ============================================

def analyze_by_quarter(data):
    """按季度分组统计"""
    quarters = {}
    for d in data:
        parts = d["date"].split("-")
        y, m = int(parts[0]), int(parts[1])
        q = (m - 1) // 3 + 1
        key = f"{y}Q{q}"
        quarters.setdefault(key, []).append(d)
    results = []
    for q_key in sorted(quarters.keys()):
        group = quarters[q_key]
        s = calc_stats(group)
        s["quarter"] = q_key
        results.append(s)
    return results

def analyze_by_month(data):
    """按月份分组统计"""
    months = {}
    for d in data:
        m = int(d["date"].split("-")[1])
        months.setdefault(m, []).append(d)
    results = []
    for m in range(1, 13):
        if m not in months: continue
        s = calc_stats(months[m])
        s["month"] = m
        s["month_label"] = f"{m}月"
        results.append(s)
    return results

# ============================================
# 单股分析（模式2：已上市股票回测）
# ============================================

def analyze_single_stock(target, data, weights, cat_encoding, norm_stats=None, extra=None):
    """单只股票的回测定位分析"""
    score = score_ipo(target, weights, cat_encoding, norm_stats, extra)
    tier = get_tier(score)

    # 找同区间股票
    sub_range = get_sub_range_label(target)
    same_range = [d for d in data if get_sub_range_label(d) == sub_range and d["code"] != target["code"]]

    # 找同行业股票
    same_cat = [d for d in data if d["category"] == target["category"] and d["code"] != target["code"]]

    # 找同档位股票
    same_tier = [d for d in data if d.get("_tier") == tier and d["code"] != target["code"]]

    # 计算排名（修复：处理重复涨幅的排名问题）
    all_returns = sorted([d["day1_return"] for d in data], reverse=True)
    target_ret = target["day1_return"]
    # 找比该股涨幅严格更高的数量 + 1 = 排名
    rank = sum(1 for r in all_returns if r > target_ret) + 1

    return {
        "target": target, "score": score, "tier": tier, "rank": rank, "total": len(data),
        "sub_range": sub_range,
        "same_range_stats": calc_stats(same_range) if same_range else None,
        "same_cat_stats": calc_stats(same_cat) if same_cat else None,
        "same_tier_stats": calc_stats(same_tier) if same_tier else None,
        "same_range": same_range[:5], "same_cat": same_cat[:5], "same_tier": same_tier[:5],
    }

# ============================================
# 未上市新股策略（模式3）
# ============================================

def predict_selling_strategy(params, data, weights, cat_encoding, market_state=None, model_source=None, norm_stats=None, extra=None):
    """基于历史同类群数据输出卖出策略
    [V3.5] 增强点:
      1. 相似度+区间混合集成(Ensemble)：避免小样本相似度匹配失真
      2. 小样本降级保护：二值维度权重自动缩放
      3. 行业差异化18C分析
      4. 暗盘联动修正（输入暗盘涨幅后修正首日/Day3/Day5预期）
    """
    score = score_ipo(params, weights, cat_encoding, norm_stats, extra)
    tier = get_tier(score)
    is_18c = params.get("is_18c", False)

    # ======== [V3.5] Ensemble: 相似度匹配 + 区间匹配混合 ========
    # 1. 相似度匹配（V3.4/V3.5增强版，含小样本保护）
    sim_peers = compute_similarity_peers(params, data, top_n=12)
    sim_stocks = [sp["stock"] for sp in sim_peers[:8]] if sim_peers else []

    # 2. 区间匹配（V3.1-V3.3的稳健方法）
    sub_range = get_sub_range_label(params)
    range_stocks = [d for d in data if get_sub_range_label(d) == sub_range]

    # 3. 计算 Ensemble 混合权重
    # 原则：相似度匹配同类群越"集中于小特征组"，区间匹配权重越高
    ensemble_info = _compute_ensemble_weights(params, sim_peers[:8], range_stocks, data)
    alpha_sim = ensemble_info["alpha_sim"]   # 相似度匹配权重
    alpha_range = ensemble_info["alpha_range"]  # 区间匹配权重

    # 4. 构造 Ensemble 同类群
    # 去重合并两组同类群，按加权贡献排序
    ensemble_peers = _build_ensemble_peers(sim_stocks, range_stocks, alpha_sim, alpha_range)

    # 最终使用的同类群
    tier_peers = ensemble_peers

    # 各时点统计
    tp_stats = analyze_selling_timepoints(tier_peers)

    # 找最优卖出时点
    valid_tps = [tp for tp in tp_stats if tp["count"] > 0]
    best_tp = max(valid_tps, key=lambda x: x["expected"]) if valid_tps else None

    # 暗盘策略判断
    dark_data = [d for d in tier_peers if d.get("dark_return") is not None]
    dark_stats = calc_stats(dark_data, "dark_return") if dark_data else None

    # [V3.4] 18C 独立分析
    is_18c_analysis = None
    if is_18c:
        all_18c = [d for d in data if d.get("is_18c", False)]
        is_18c_with_cs = [d for d in all_18c if d.get("has_cornerstone", False)]
        is_18c_no_cs = [d for d in all_18c if not d.get("has_cornerstone", False)]
        is_18c_analysis = {
            "total": len(all_18c),
            "stats": calc_stats(all_18c) if all_18c else None,
            "with_cs": {"count": len(is_18c_with_cs), "stats": calc_stats(is_18c_with_cs) if is_18c_with_cs else None},
            "no_cs": {"count": len(is_18c_no_cs), "stats": calc_stats(is_18c_no_cs) if is_18c_no_cs else None},
            "dark_stats": calc_stats(all_18c, "dark_return") if all_18c else None,
        }

    # [V3.4/V3.5] 暗盘联动修正（使用Ensemble同类群）
    dark_feedback = None
    if params.get("dark_return") is not None:
        dark_feedback = compute_dark_feedback(params, tier_peers, data)

    return {
        "params": params, "score": score, "tier": tier,
        "peer_count": len(tier_peers), "sub_range": sub_range,
        "tp_stats": tp_stats, "best_tp": best_tp, "dark_stats": dark_stats,
        "peers": tier_peers[:8],
        "sim_peers": sim_peers[:8] if sim_peers else [],
        "market_state": market_state,
        "model_source": model_source,
        "is_18c": is_18c,
        "is_18c_analysis": is_18c_analysis,
        "dark_feedback": dark_feedback,
        "ensemble_info": ensemble_info,  # V3.5: Ensemble混合信息
    }


# ============================================
# [V3.5] Ensemble: 相似度+区间混合引擎
# ============================================

def _compute_ensemble_weights(target, sim_peers_top, range_stocks, all_data):
    """计算相似度匹配与区间匹配的 Ensemble 混合权重

    原则:
      - 基础权重 α_sim=0.5, α_range=0.5（平等起步）
      - 当相似度Top8集中于小特征组(如18C无基石<5只)时，降低α_sim
      - 当区间样本充足(>10只)且方差低时，提高α_range
      - 当相似度Top3来自同一极端小组时，触发降级保护

    Returns:
        dict: {"alpha_sim": 0.4, "alpha_range": 0.6, "reason": "...", ...}
    """
    n_range = len(range_stocks)
    n_sim = len(sim_peers_top)

    # 检测相似度Top3是否来自同一"极端小组"
    # 定义：二值维度(cs, 18c)完全一致的特征组 < 5只
    if n_sim >= 3:
        top3_stocks = [sp["stock"] for sp in sim_peers_top[:3]]
        # 检查top3是否共享相同的 cs + 18c 组合
        t_cs_val = target.get("has_cornerstone", False)
        t_18c_val = target.get("is_18c", False)
        same_combo = all(
            d.get("has_cornerstone", False) == t_cs_val and d.get("is_18c", False) == t_18c_val
            for d in top3_stocks
        )
        combo_count = sum(1 for d in all_data
                         if d.get("has_cornerstone", False) == t_cs_val
                         and d.get("is_18c", False) == t_18c_val)
        small_group_trap = same_combo and combo_count < 5
    else:
        small_group_trap = False
        combo_count = 0

    # 计算权重
    if small_group_trap:
        # 小样本陷阱检测触发: 大幅偏向区间匹配
        alpha_sim = 0.20
        alpha_range = 0.80
        reason = f"⚠️ 小样本降级保护: 相似度Top3均来自仅{combo_count}只的特征组，以区间匹配为主"
    elif n_range >= 10 and n_sim >= 5:
        # 两种方法都有充足数据: 均衡混合
        alpha_sim = 0.50
        alpha_range = 0.50
        reason = f"均衡混合: 相似度{n_sim}只 + 区间{n_range}只"
    elif n_range >= 10 and n_sim < 5:
        # 区间充足、相似度不足
        alpha_sim = 0.30
        alpha_range = 0.70
        reason = f"区间优先: 相似度仅{n_sim}只，区间{n_range}只"
    elif n_range < 5:
        # 区间也不够（冷门区间）
        alpha_sim = 0.70
        alpha_range = 0.30
        reason = f"相似度优先: 区间仅{n_range}只"
    else:
        alpha_sim = 0.45
        alpha_range = 0.55
        reason = f"默认: 相似度{n_sim}只 + 区间{n_range}只"

    return {
        "alpha_sim": alpha_sim,
        "alpha_range": alpha_range,
        "reason": reason,
        "small_group_trap": small_group_trap,
        "combo_count": combo_count,
        "n_sim": n_sim,
        "n_range": n_range,
    }


def _build_ensemble_peers(sim_stocks, range_stocks, alpha_sim, alpha_range):
    """构造 Ensemble 混合同类群

    策略:
      1. 两组按权重分配名额: sim取 round(8*α_sim), range取 round(8*α_range)
      2. 去重（同一只股票只保留一次）
      3. 最终取 top 8-12只
    """
    n_total = 10  # Ensemble总名额
    n_sim = max(2, min(8, round(n_total * alpha_sim)))
    n_range = n_total - n_sim

    # 从相似度组取前n_sim只
    selected_codes = set()
    ensemble = []

    for d in sim_stocks[:n_sim]:
        code = d.get("code", "")
        if code not in selected_codes:
            selected_codes.add(code)
            ensemble.append(d)

    # 从区间组取前n_range只(去重)
    for d in range_stocks[:n_range + 4]:  # 多取几只以防去重后不够
        code = d.get("code", "")
        if code not in selected_codes:
            selected_codes.add(code)
            ensemble.append(d)
            if len(ensemble) >= n_total:
                break

    return ensemble


# ============================================
# [V3.4] 多维相似度匹配引擎
# ============================================

def compute_similarity_peers(target, data, top_n=12):
    """[V3.5] 多维相似度匹配引擎（带小样本降级保护）

    改进点 (V3.5):
      1. 二值维度动态权重缩放：当特征组样本<5只时自动降低权重
      2. 行业相似度分层：科技/半导体/AI归为近亲组(0.7)，医药/生物归为近亲组(0.7)
      3. 超购维度权重提升，避免被二值维度淹没

    维度基础权重：
      - 超购倍数(log): 40% — 最核心的分档因子（V3.4: 35%→V3.5: 40%）
      - 基石投资者:     15% — 动态缩放（V3.4: 20%→V3.5: 15%基础）
      - 行业:          20% — 分层相似度（V3.4: 15%→V3.5: 20%）
      - 募资规模(log):  15% — 影响流动性和市场容量
      - 18C机制:       10% — 动态缩放（V3.4: 15%→V3.5: 10%基础）

    Returns:
        list[dict]: [{"stock": d, "similarity": 0.95, "breakdown": {...}, "weights_used": {...}}, ...]
    """
    results = []
    t_sub = math.log(max(target.get("subscription_mult", 1), 1))
    t_cs = 1.0 if target.get("has_cornerstone", False) else 0.0
    t_cat = target.get("category", "其他")
    t_fund = math.log(max(target.get("fundraising", 1), 0.1))
    t_18c = 1.0 if target.get("is_18c", False) else 0.0

    # 从数据集计算 sub 和 fund 的范围（用于归一化距离）
    all_subs = [math.log(max(d["subscription_mult"], 1)) for d in data]
    all_funds = [math.log(max(d["fundraising"], 0.1)) for d in data]
    sub_range_val = max(all_subs) - min(all_subs) if all_subs else 1
    fund_range_val = max(all_funds) - min(all_funds) if all_funds else 1

    # ========== [V3.5] 小样本降级保护 ==========
    # 统计二值维度的特征组大小
    n_same_cs = sum(1 for d in data if (d.get("has_cornerstone", False) == target.get("has_cornerstone", False)))
    n_same_18c = sum(1 for d in data if (d.get("is_18c", False) == target.get("is_18c", False)))
    # 交叉组: 同时满足 cs + 18c
    n_cross = sum(1 for d in data
                  if (d.get("has_cornerstone", False) == target.get("has_cornerstone", False))
                  and (d.get("is_18c", False) == target.get("is_18c", False)))

    # 动态权重缩放: eff_weight = base × min(1.0, n_group / 5)
    # 当组内样本<5只时，线性衰减权重，避免小样本陷阱
    MIN_GROUP_FOR_FULL_WEIGHT = 5
    cs_scale = min(1.0, n_same_cs / MIN_GROUP_FOR_FULL_WEIGHT)
    c18_scale = min(1.0, n_same_18c / MIN_GROUP_FOR_FULL_WEIGHT)
    # 交叉组更严格: 如果 cs+18c 组合很少，进一步缩放
    cross_scale = min(1.0, n_cross / MIN_GROUP_FOR_FULL_WEIGHT)
    joint_scale = min(cs_scale, c18_scale, cross_scale)

    # 基础权重
    w_sub_base = 0.40
    w_cs_base = 0.15
    w_cat_base = 0.20
    w_fund_base = 0.15
    w_18c_base = 0.10

    # 应用缩放
    w_cs = w_cs_base * joint_scale
    w_18c = w_18c_base * joint_scale
    # 释放的权重回流到超购和行业（最稳健的连续维度）
    released = (w_cs_base - w_cs) + (w_18c_base - w_18c)
    w_sub = w_sub_base + released * 0.6   # 60%回流超购
    w_cat = w_cat_base + released * 0.25   # 25%回流行业
    w_fund = w_fund_base + released * 0.15 # 15%回流募资

    # 归一化确保总和=1
    w_total = w_sub + w_cs + w_cat + w_fund + w_18c
    w_sub /= w_total
    w_cs /= w_total
    w_cat /= w_total
    w_fund /= w_total
    w_18c /= w_total

    weights_used = {"sub": w_sub, "cs": w_cs, "cat": w_cat, "fund": w_fund, "is_18c": w_18c,
                    "cs_scale": cs_scale, "c18_scale": c18_scale, "cross_scale": cross_scale}

    for d in data:
        if d.get("code") == target.get("code"):
            continue

        d_sub = math.log(max(d["subscription_mult"], 1))
        d_cs = 1.0 if d.get("has_cornerstone", False) else 0.0
        d_cat = d.get("category", "其他")
        d_fund = math.log(max(d["fundraising"], 0.1))
        d_18c = 1.0 if d.get("is_18c", False) else 0.0

        # 各维度相似度 (0-1, 1=完全相同)
        sim_sub = 1.0 - abs(t_sub - d_sub) / sub_range_val if sub_range_val > 0 else 1.0
        sim_cs = 1.0 if t_cs == d_cs else 0.3  # [V3.5] 不同基石状态给0.3(V3.4是0.0)
        # [V3.5] 行业分层相似度
        sim_cat = _industry_similarity(t_cat, d_cat)
        sim_fund = 1.0 - abs(t_fund - d_fund) / fund_range_val if fund_range_val > 0 else 1.0
        sim_18c = 1.0 if t_18c == d_18c else 0.3  # [V3.5] 不同18C状态给0.3(V3.4是0.2)

        # 加权综合相似度
        total_sim = (
            sim_sub * w_sub +
            sim_cs * w_cs +
            sim_cat * w_cat +
            sim_fund * w_fund +
            sim_18c * w_18c
        )

        results.append({
            "stock": d,
            "similarity": total_sim,
            "breakdown": {
                "sub": sim_sub, "cs": sim_cs, "cat": sim_cat,
                "fund": sim_fund, "is_18c": sim_18c,
            },
            "weights_used": weights_used,
        })

    results.sort(key=lambda x: -x["similarity"])
    return results[:top_n]


# ============================================
# [V3.5] 行业分层相似度
# ============================================

# 行业近亲组：组内相似度 0.7，组外 0.3
_INDUSTRY_GROUPS = {
    "科技": ["半导体", "AI", "科技", "SaaS", "软件", "芯片", "互联网", "云计算", "数据"],
    "医药": ["医药", "生物科技", "创新药", "医疗器械", "CXO", "生物"],
    "消费": ["消费", "餐饮", "零售", "电商", "食品", "服装"],
    "工业": ["机器人", "新能源", "汽车", "制造", "工业", "材料"],
    "金融": ["金融", "银行", "保险", "券商", "支付"],
}

def _get_industry_group(category):
    """获取行业所属的近亲组"""
    for group_name, keywords in _INDUSTRY_GROUPS.items():
        for kw in keywords:
            if kw in category:
                return group_name
    return None  # 未匹配到任何组

def _industry_similarity(cat_a, cat_b):
    """[V3.5] 行业分层相似度：同行业=1.0, 同组近亲=0.7, 其他=0.3"""
    if cat_a == cat_b:
        return 1.0
    group_a = _get_industry_group(cat_a)
    group_b = _get_industry_group(cat_b)
    if group_a and group_b and group_a == group_b:
        return 0.7  # 同组近亲（如半导体↔AI, 医药↔生物科技）
    return 0.3  # 跨组


# ============================================
# [V3.4] 暗盘联动修正引擎
# ============================================

def compute_dark_feedback(params, peers, all_data):
    """暗盘实际值 → 修正首日/Day3/Day5 预期

    原理：暗盘涨幅偏离同类群均值的幅度，可用于修正后续预期。
    - 暗盘高于预期 → 首日可能更高（但也可能暗盘透支）
    - 暗盘低于预期 → 首日可能补涨（修正效应）或继续下跌

    方法：
    1. 计算同类群的暗盘→首日转换率分布
    2. 基于暗盘实际值，用转换率推算首日/Day3/Day5的修正预期
    3. 识别「暗盘透支」vs「暗盘蓄力」模式

    Returns:
        dict: {
            "dark_actual": 暗盘实际涨幅,
            "dark_expected": 同类群暗盘均值,
            "dark_deviation": 偏差,
            "corrected_day1": 修正后首日预期,
            "corrected_day3": 修正后Day3预期,
            "corrected_day5": 修正后Day5预期,
            "pattern": "暗盘透支" / "暗盘蓄力" / "符合预期",
            "confidence": 置信度说明,
            "similar_dark_peers": 暗盘走势相似的历史案例,
        }
    """
    dark_actual = params.get("dark_return")
    if dark_actual is None:
        return None

    # 同类群暗盘统计
    dark_peers = [d for d in peers if d.get("dark_return") is not None and d.get("day1_return") is not None]
    if len(dark_peers) < 3:
        # 样本不足，扩大到全量数据
        dark_peers = [d for d in all_data if d.get("dark_return") is not None and d.get("day1_return") is not None]
        if len(dark_peers) < 5:
            return None

    # 计算同类群暗盘均值
    dark_expected = sum(d["dark_return"] for d in dark_peers) / len(dark_peers)
    dark_deviation = dark_actual - dark_expected

    # 计算暗盘→首日的转换率 (day1 / dark)
    d2d1_ratios = []
    d2d3_ratios = []
    d2d5_ratios = []
    for d in dark_peers:
        dk = d["dark_return"]
        d1 = d.get("day1_return", 0)
        d3 = d.get("day3_return")
        d5 = d.get("day5_return")
        if dk != 0:
            d2d1_ratios.append(d1 / dk)
        else:
            d2d1_ratios.append(d1 / 1.0 if d1 else 0)  # 暗盘0%时用绝对值
        if d3 is not None and dk != 0:
            d2d3_ratios.append(d3 / dk)
        if d5 is not None and dk != 0:
            d2d5_ratios.append(d5 / dk)

    # 中位转换率（比均值更稳健）
    def _median(lst):
        if not lst: return 1.0
        s = sorted(lst)
        n = len(s)
        return s[n//2] if n % 2 == 1 else (s[n//2-1] + s[n//2]) / 2

    med_d2d1 = _median(d2d1_ratios)
    med_d2d3 = _median(d2d3_ratios) if d2d3_ratios else None
    med_d2d5 = _median(d2d5_ratios) if d2d5_ratios else None

    # 修正后预期
    corrected_day1 = dark_actual * med_d2d1 if dark_actual != 0 else dark_expected * med_d2d1
    corrected_day3 = dark_actual * med_d2d3 if med_d2d3 is not None and dark_actual != 0 else None
    corrected_day5 = dark_actual * med_d2d5 if med_d2d5 is not None and dark_actual != 0 else None

    # 找暗盘走势相似的历史案例（暗盘涨幅最接近的5只）
    similar_dark = sorted(dark_peers, key=lambda d: abs(d["dark_return"] - dark_actual))[:5]

    # 用这些最相似暗盘案例的实际后续走势做另一个预测
    sim_d1 = sum(d["day1_return"] for d in similar_dark) / len(similar_dark) if similar_dark else corrected_day1
    sim_d3_list = [d["day3_return"] for d in similar_dark if d.get("day3_return") is not None]
    sim_d5_list = [d["day5_return"] for d in similar_dark if d.get("day5_return") is not None]
    sim_d3 = sum(sim_d3_list) / len(sim_d3_list) if sim_d3_list else corrected_day3
    sim_d5 = sum(sim_d5_list) / len(sim_d5_list) if sim_d5_list else corrected_day5

    # 综合两种方法取均值
    final_d1 = (corrected_day1 + sim_d1) / 2
    final_d3 = ((corrected_day3 or 0) + (sim_d3 or 0)) / 2 if corrected_day3 is not None or sim_d3 is not None else None
    final_d5 = ((corrected_day5 or 0) + (sim_d5 or 0)) / 2 if corrected_day5 is not None or sim_d5 is not None else None

    # 模式识别
    if dark_actual > dark_expected + 20:
        pattern = "暗盘透支"
        pattern_desc = "暗盘涨幅显著高于预期，首日可能回落。建议暗盘果断卖出。"
    elif dark_actual < dark_expected - 20:
        pattern = "暗盘不及预期"
        pattern_desc = "暗盘涨幅显著低于预期，可能存在修正空间（也可能继续下跌）。需结合基本面判断。"
    elif dark_actual < 0 and dark_expected > 10:
        pattern = "暗盘破发（预期外）"
        pattern_desc = "暗盘破发但同类群预期为正，风险极高。建议立即止损。"
    elif dark_actual > 0 and dark_actual < dark_expected * 0.5 and dark_expected > 20:
        pattern = "暗盘蓄力"
        pattern_desc = "暗盘涨幅不到预期一半，可能首日有补涨空间。但需谨慎。"
    else:
        pattern = "符合预期"
        pattern_desc = "暗盘表现在预期范围内，按原策略执行。"

    return {
        "dark_actual": dark_actual,
        "dark_expected": dark_expected,
        "dark_deviation": dark_deviation,
        "corrected_day1": final_d1,
        "corrected_day3": final_d3,
        "corrected_day5": final_d5,
        "pattern": pattern,
        "pattern_desc": pattern_desc,
        "similar_dark_peers": similar_dark,
        "conversion_rates": {"d2d1": med_d2d1, "d2d3": med_d2d3, "d2d5": med_d2d5},
        "sample_size": len(dark_peers),
    }


# ============================================
# [V3.4] 18C 效应分析
# ============================================

def analyze_18c_effect(data):
    """分析 18C/B 类股票的整体表现差异
    Returns:
        dict: 18C vs 非18C 的对比统计
    """
    is_18c = [d for d in data if d.get("is_18c", False)]
    non_18c = [d for d in data if not d.get("is_18c", False)]

    result = {
        "is_18c_count": len(is_18c),
        "non_18c_count": len(non_18c),
        "is_18c_stats": calc_stats(is_18c) if is_18c else None,
        "non_18c_stats": calc_stats(non_18c) if non_18c else None,
    }

    # 18C 有基石 vs 无基石
    is_18c_cs = [d for d in is_18c if d.get("has_cornerstone", False)]
    is_18c_no_cs = [d for d in is_18c if not d.get("has_cornerstone", False)]
    result["is_18c_with_cs"] = {
        "count": len(is_18c_cs),
        "stats": calc_stats(is_18c_cs) if is_18c_cs else None,
    }
    result["is_18c_no_cs"] = {
        "count": len(is_18c_no_cs),
        "stats": calc_stats(is_18c_no_cs) if is_18c_no_cs else None,
    }

    # 暗盘统计
    result["is_18c_dark"] = calc_stats(is_18c, "dark_return") if is_18c else None
    result["non_18c_dark"] = calc_stats(non_18c, "dark_return") if non_18c else None

    return result


# ============================================
# 市场状态分类系统
# ============================================

# 市场状态常量
BULL = "BULL"
BEAR = "BEAR"
NEUTRAL = "NEUTRAL"

STATE_LABELS = {BULL: "🐂 牛市", BEAR: "🐻 熊市", NEUTRAL: "⚖️ 震荡"}
STATE_COLORS = {BULL: "#ff4444", BEAR: "#00b050", NEUTRAL: "#ffaa00"}

def classify_market_state(date_str, hsi_monthly):
    """根据上市日期前3个月恒指累计涨跌幅判定市场状态
    
    Args:
        date_str: 上市日期 "YYYY-MM-DD" 或 "未上市"
        hsi_monthly: 恒指月度涨跌幅字典 {"2024-01": -1.16, ...}
    
    Returns:
        str: BULL / BEAR / NEUTRAL
    """
    if date_str == "未上市" or not hsi_monthly:
        return None
    
    try:
        parts = date_str.split("-")
        y, m = int(parts[0]), int(parts[1])
    except (ValueError, IndexError):
        return None
    
    # 取上市月份前3个月的恒指累计涨跌幅
    cumulative = 0.0
    months_found = 0
    for offset in range(1, 4):  # 前1、2、3个月
        target_m = m - offset
        target_y = y
        while target_m <= 0:
            target_m += 12
            target_y -= 1
        key = f"{target_y}-{target_m:02d}"
        if key in hsi_monthly:
            cumulative += hsi_monthly[key]
            months_found += 1
    
    if months_found == 0:
        return NEUTRAL  # 无数据时默认震荡
    
    # 阈值：±8%
    if cumulative > 8.0:
        return BULL
    elif cumulative < -8.0:
        return BEAR
    else:
        return NEUTRAL


def get_current_market_state(hsi_monthly):
    """获取当前（最新月份）的市场状态"""
    if not hsi_monthly:
        return NEUTRAL
    # 找最近的月份
    sorted_keys = sorted(hsi_monthly.keys(), reverse=True)
    if len(sorted_keys) < 3:
        return NEUTRAL
    # 取最近3个月累计
    cumulative = sum(hsi_monthly[k] for k in sorted_keys[:3])
    if cumulative > 8.0:
        return BULL
    elif cumulative < -8.0:
        return BEAR
    else:
        return NEUTRAL


def label_data_market_state(data, hsi_monthly):
    """为数据集中每条记录打上市场状态标签"""
    for d in data:
        d["_market_state"] = classify_market_state(d.get("date", ""), hsi_monthly)


# ============================================
# 条件子模型引擎
# ============================================

MIN_SAMPLES_FULL = 10    # 完全使用子模型的最低样本数
MIN_SAMPLES_WARN = 5     # 带警告使用子模型的最低样本数

def compute_conditional_models(data, hsi_monthly):
    """条件子模型：按市场状态分组训练独立模型
    
    Args:
        data: ipo_data列表（已打好_market_state标签）
        hsi_monthly: 恒指月度涨跌幅字典
    
    Returns:
        dict: {
            "models": {state: {"weights": {...}, "extra": {...}, "cat_encoding": {...}, "sample_count": N, "warning": str|None}},
            "global": {"weights": {...}, "extra": {...}, "cat_encoding": {...}},
            "state_distribution": {state: count},
            "degraded_states": [state, ...],
        }
    """
    # 1. 确保所有数据都有市场状态标签
    label_data_market_state(data, hsi_monthly)
    
    # 2. 先训练全局模型（作为降级后备）
    global_weights, global_extra = compute_factor_weights(data)
    global_cat_encoding = global_extra.get("cat_encoding", {})
    global_norm_stats = global_extra.get("norm_stats", {})
    
    # 3. 按市场状态分组
    state_groups = {}
    for d in data:
        state = d.get("_market_state", NEUTRAL) or NEUTRAL
        state_groups.setdefault(state, []).append(d)
    
    state_distribution = {s: len(g) for s, g in state_groups.items()}
    
    # 4. 各组独立训练子模型
    models = {}
    degraded_states = []
    
    for state in [BULL, BEAR, NEUTRAL]:
        group = state_groups.get(state, [])
        n = len(group)
        
        if n >= MIN_SAMPLES_FULL:
            # 样本充足，正常训练
            w, ex = compute_factor_weights(group)
            models[state] = {
                "weights": w,
                "extra": ex,
                "cat_encoding": ex.get("cat_encoding", {}),
                "norm_stats": ex.get("norm_stats", {}),
                "sample_count": n,
                "warning": None,
            }
        elif n >= MIN_SAMPLES_WARN:
            # 样本较少，训练但带警告
            w, ex = compute_factor_weights(group)
            models[state] = {
                "weights": w,
                "extra": ex,
                "cat_encoding": ex.get("cat_encoding", {}),
                "norm_stats": ex.get("norm_stats", {}),
                "sample_count": n,
                "warning": f"⚠️ 小样本警告: 仅{n}只，结果需谨慎参考",
            }
        else:
            # 样本不足，降级为全局模型
            degraded_states.append(state)
            models[state] = {
                "weights": global_weights,
                "extra": global_extra,
                "cat_encoding": global_cat_encoding,
                "norm_stats": global_norm_stats,
                "sample_count": n,
                "warning": f"⚠️ 降级至全局模型: {state}仅{n}只样本，不足以独立训练",
            }
    
    return {
        "models": models,
        "global": {
            "weights": global_weights,
            "extra": global_extra,
            "cat_encoding": global_cat_encoding,
            "norm_stats": global_norm_stats,
        },
        "state_distribution": state_distribution,
        "degraded_states": degraded_states,
    }


def get_model_for_state(conditional_result, state):
    """根据市场状态获取对应的模型权重、编码、归一化参数和额外信息"""
    models = conditional_result["models"]
    if state in models:
        m = models[state]
        return m["weights"], m["cat_encoding"], m.get("norm_stats", {}), m.get("extra", {}), m["warning"]
    # fallback to global
    g = conditional_result["global"]
    return g["weights"], g["cat_encoding"], g.get("norm_stats", {}), g.get("extra", {}), f"⚠️ 未知状态 {state}，使用全局模型"


def bootstrap_confidence(data, key="day1_return", n_bootstrap=1000, ci=90):
    """Bootstrap 置信区间：对均值和胜率给出不确定性范围
    
    Args:
        data: 数据列表
        key: 收益率字段名
        n_bootstrap: 重采样次数（1000次足够稳定）
        ci: 置信水平（默认90%）
    
    Returns:
        dict: {
            "mean": 样本均值,
            "mean_ci_lo": 均值下界, "mean_ci_hi": 均值上界,
            "win_rate": 样本胜率,
            "wr_ci_lo": 胜率下界, "wr_ci_hi": 胜率上界,
            "expected": 期望收益,
            "exp_ci_lo": 期望下界, "exp_ci_hi": 期望上界,
        }
    """
    import random
    values = [d[key] for d in data if d.get(key) is not None]
    n = len(values)
    if n < 3:
        m = sum(values) / n if n > 0 else 0
        wr = sum(1 for v in values if v > 0) / n * 100 if n > 0 else 0
        return {"mean": m, "mean_ci_lo": m, "mean_ci_hi": m,
                "win_rate": wr, "wr_ci_lo": wr, "wr_ci_hi": wr,
                "expected": m, "exp_ci_lo": m, "exp_ci_hi": m, "n": n}
    
    # 简单 LCG 伪随机数生成器（纯标准库，可复现）
    seed = 42
    boot_means = []
    boot_wrs = []
    boot_exps = []
    
    for _ in range(n_bootstrap):
        # 有放回重采样
        seed = (seed * 1103515245 + 12345) & 0x7fffffff
        random.seed(seed)
        sample = random.choices(values, k=n)
        
        s_mean = sum(sample) / n
        winners = [v for v in sample if v > 0]
        losers = [v for v in sample if v < 0]
        s_wr = len(winners) / n * 100
        avg_win = sum(winners) / len(winners) if winners else 0
        avg_loss = sum(losers) / len(losers) if losers else 0
        s_exp = (len(winners) / n) * avg_win + (len(losers) / n) * avg_loss
        
        boot_means.append(s_mean)
        boot_wrs.append(s_wr)
        boot_exps.append(s_exp)
    
    # 百分位置信区间
    alpha = (100 - ci) / 2
    lo_idx = max(0, int(n_bootstrap * alpha / 100))
    hi_idx = min(n_bootstrap - 1, int(n_bootstrap * (100 - alpha) / 100))
    
    boot_means.sort()
    boot_wrs.sort()
    boot_exps.sort()
    
    actual_mean = sum(values) / n
    actual_wr = sum(1 for v in values if v > 0) / n * 100
    winners = [v for v in values if v > 0]
    losers = [v for v in values if v < 0]
    avg_win = sum(winners) / len(winners) if winners else 0
    avg_loss = sum(losers) / len(losers) if losers else 0
    actual_exp = (len(winners) / n) * avg_win + (len(losers) / n) * avg_loss
    
    return {
        "mean": actual_mean,
        "mean_ci_lo": boot_means[lo_idx], "mean_ci_hi": boot_means[hi_idx],
        "win_rate": actual_wr,
        "wr_ci_lo": boot_wrs[lo_idx], "wr_ci_hi": boot_wrs[hi_idx],
        "expected": actual_exp,
        "exp_ci_lo": boot_exps[lo_idx], "exp_ci_hi": boot_exps[hi_idx],
        "n": n,
    }


def time_series_cv(data, n_folds=4):
    """时序交叉验证：按时间排序后滑动窗口验证模型稳定性
    
    与随机 K-fold 不同，这里严格保证训练集在测试集之前（无前视偏差）。
    
    Args:
        data: ipo_data 列表（需包含 date 字段）
        n_folds: 折数（默认4，即4次验证）
    
    Returns:
        list[dict]: 每折结果 [{
            "fold": 1,
            "train_n": 训练集大小,
            "test_n": 测试集大小,
            "train_r2": 训练集 R²,
            "test_r2": 测试集 R² (OOS),
            "test_mae": 测试集 MAE,
            "test_corr": 测试集 预测-实际相关系数,
            "train_period": "2024.06-2024.12",
            "test_period": "2025.01-2025.03",
            "tier_accuracy": 档位准确率（预测档=实际档的比例）,
        }]
    """
    valid = [d for d in data if d.get("day1_return") is not None]
    valid.sort(key=lambda d: d["date"])
    n = len(valid)
    
    if n < 20:
        return []  # 样本太少无法交叉验证
    
    results = []
    # 扩展窗口法：前 k 折做训练，第 k+1 折做测试
    fold_size = n // (n_folds + 1)
    
    for fold in range(1, n_folds + 1):
        train_end = fold_size * (fold + 1)  # 逐步扩大训练集
        test_start = train_end
        test_end = min(test_start + fold_size, n)
        
        if test_end <= test_start:
            break
        
        train_data = valid[:train_end]
        test_data = valid[test_start:test_end]
        
        if len(train_data) < 10 or len(test_data) < 3:
            continue
        
        # 在训练集上训练模型
        weights, extra = compute_factor_weights(train_data)
        cat_encoding = extra.get("cat_encoding", {})
        norm_stats = extra.get("norm_stats", {})
        train_r2 = extra.get("r2", 0)
        
        # 在测试集上评估
        test_actual = [d["day1_return"] for d in test_data]
        test_scores = [score_ipo(d, weights, cat_encoding, norm_stats, extra) for d in test_data]
        
        # 测试集 MAE（评分与实际涨幅排序一致性比 R² 更有意义）
        test_mae = sum(abs(test_actual[i] - test_scores[i]) for i in range(len(test_data))) / len(test_data)
        
        # 简单 R²：用评分预测涨幅（仅作参考，评分 0-100 与涨幅 % 尺度不同）
        # 改用：Spearman 秩相关系数（排序一致性）
        def _rank(vals):
            """简单排名"""
            indexed = sorted(enumerate(vals), key=lambda x: x[1])
            ranks = [0] * len(vals)
            for rank, (idx, _) in enumerate(indexed):
                ranks[idx] = rank
            return ranks
        
        rank_actual = _rank(test_actual)
        rank_scores = _rank(test_scores)
        n_test = len(test_data)
        mean_ra = sum(rank_actual) / n_test
        mean_rs = sum(rank_scores) / n_test
        cov = sum((rank_actual[i] - mean_ra) * (rank_scores[i] - mean_rs) for i in range(n_test))
        std_a = (sum((r - mean_ra)**2 for r in rank_actual)) ** 0.5
        std_s = (sum((r - mean_rs)**2 for r in rank_scores)) ** 0.5
        spearman = cov / (std_a * std_s) if std_a > 0 and std_s > 0 else 0
        
        # 档位准确率
        test_tiers_pred = [get_tier(s) for s in test_scores]
        test_tiers_actual = [get_tier(d.get("_score", score_ipo(d, weights, cat_encoding, norm_stats, extra))) for d in test_data]
        tier_match = sum(1 for i in range(n_test) if test_tiers_pred[i] == test_tiers_actual[i])
        tier_accuracy = tier_match / n_test * 100 if n_test > 0 else 0
        
        # OOS R²（用训练集的 beta 直接预测测试集收益）
        # 为此需要重建特征矩阵
        test_y = [d["day1_return"] for d in test_data]
        y_mean_train = sum(d["day1_return"] for d in train_data) / len(train_data)
        ss_tot_test = sum((y - y_mean_train)**2 for y in test_y)
        
        # 用 beta 预测（如果有的话）
        beta = extra.get("beta_std")
        if beta and norm_stats:
            # 重建测试集特征（使用训练集的编码和标准化参数）
            test_preds = []
            for d in test_data:
                s = score_ipo(d, weights, cat_encoding, norm_stats, extra)
                # 评分到收益的线性映射（用训练集统计）
                test_preds.append(s)  # 作为 proxy
            ss_res_test = sum((test_y[i] - test_preds[i])**2 for i in range(n_test))
            oos_r2 = 1 - ss_res_test / ss_tot_test if ss_tot_test > 0 else 0
        else:
            oos_r2 = 0
        
        train_period = f"{train_data[0]['date'][:7].replace('-','.')}~{train_data[-1]['date'][:7].replace('-','.')}"
        test_period = f"{test_data[0]['date'][:7].replace('-','.')}~{test_data[-1]['date'][:7].replace('-','.')}"
        
        results.append({
            "fold": fold,
            "train_n": len(train_data),
            "test_n": len(test_data),
            "train_r2": train_r2,
            "spearman": spearman,
            "test_mae": test_mae,
            "tier_accuracy": tier_accuracy,
            "train_period": train_period,
            "test_period": test_period,
        })
    
    return results


def analyze_tier_selling_strategy(data, weights, cat_encoding, norm_stats=None, extra=None):
    """分档位卖出策略：每个评分档给出最优卖出时点和策略建议
    
    Returns:
        list[dict]: [{
            "tier": "S",
            "count": N,
            "tp_stats": [各时点统计],
            "best_tp": "首日",
            "best_expected": +X.X%,
            "strategy": "文字策略建议",
            "bootstrap": {置信区间},
        }]
    """
    tiers_data = {"S": [], "A": [], "B": [], "C": [], "D": []}
    for d in data:
        if d.get("day1_return") is None:
            continue
        s = d.get("_score") or score_ipo(d, weights, cat_encoding, norm_stats, extra)
        tier = get_tier(s)
        tiers_data[tier].append(d)
    
    results = []
    for tier in ["S", "A", "B", "C", "D"]:
        group = tiers_data[tier]
        if not group:
            results.append({"tier": tier, "count": 0, "tp_stats": [], "best_tp": "N/A",
                            "best_expected": 0, "strategy": "无数据", "bootstrap": None,
                            "hold_premium": {}})
            continue
        
        # 各时点统计
        tp_stats = analyze_selling_timepoints(group)
        
        # 找最优卖出时点
        valid_tps = [tp for tp in tp_stats if tp["count"] > 0]
        if valid_tps:
            best = max(valid_tps, key=lambda x: x["expected"])
            best_tp = best["label"]
            best_expected = best["expected"]
        else:
            best_tp = "N/A"
            best_expected = 0
        
        # 持有溢价：首日→Day3、首日→Day5 的增量收益
        tp_map = {tp["label"]: tp for tp in tp_stats}
        d1_exp = tp_map.get("首日", {}).get("expected", 0)
        d3_exp = tp_map.get("第3天", {}).get("expected", 0)
        d5_exp = tp_map.get("第5天", {}).get("expected", 0)
        dark_exp = tp_map.get("暗盘", {}).get("expected", 0)
        
        hold_premium = {
            "dark_to_d1": d1_exp - dark_exp if dark_exp != 0 else None,
            "d1_to_d3": d3_exp - d1_exp,
            "d1_to_d5": d5_exp - d1_exp,
            "d3_to_d5": d5_exp - d3_exp,
        }
        
        # Bootstrap 置信区间（对最优时点）
        best_key = {"暗盘": "dark_return", "首日": "day1_return",
                     "第3天": "day3_return", "第5天": "day5_return"}.get(best_tp, "day1_return")
        bs = bootstrap_confidence(group, key=best_key) if len(group) >= 5 else None
        
        # 生成策略文字
        strategy = _generate_tier_strategy(tier, best_tp, best_expected, tp_stats, hold_premium, len(group))
        
        results.append({
            "tier": tier,
            "count": len(group),
            "tp_stats": tp_stats,
            "best_tp": best_tp,
            "best_expected": best_expected,
            "strategy": strategy,
            "bootstrap": bs,
            "hold_premium": hold_premium,
        })
    
    return results


def _generate_tier_strategy(tier, best_tp, best_exp, tp_stats, hold_premium, count):
    """根据档位和数据自动生成策略文字"""
    tp_map = {tp["label"]: tp for tp in tp_stats}
    d1_wr = tp_map.get("首日", {}).get("win_rate", 0)
    dark_wr = tp_map.get("暗盘", {}).get("win_rate", 0)
    
    if tier == "S":
        if best_tp in ["第3天", "第5天"]:
            return f"🔥 S档高确定性标的：建议持有到{best_tp}（期望{best_exp:+.1f}%），首日胜率{d1_wr:.0f}%极高，可大胆持有。"
        else:
            return f"🔥 S档优质标的：建议{best_tp}卖出锁定收益（期望{best_exp:+.1f}%），若暗盘涨幅>30%可考虑暗盘即卖。"
    elif tier == "A":
        d1_to_d3 = hold_premium.get("d1_to_d3", 0) or 0
        if d1_to_d3 > 5:
            return f"⭐ A档较优标的：首日卖出期望良好，但持有到第3天有额外{d1_to_d3:+.1f}%溢价，视暗盘情况决定。"
        else:
            return f"⭐ A档较优标的：建议{best_tp}卖出（期望{best_exp:+.1f}%），不建议过度持有。"
    elif tier == "B":
        if dark_wr > 60:
            return f"⚡ B档中等标的：暗盘胜率{dark_wr:.0f}%尚可，建议暗盘或首日择机卖出，不宜恋战。"
        else:
            return f"⚡ B档中等标的：胜率一般，建议{best_tp}果断卖出（期望{best_exp:+.1f}%），不宜持有过久。"
    elif tier == "C":
        return f"⚠️ C档高风险标的：胜率低，若中签建议暗盘或首日第一时间卖出止损，切忌持有。"
    else:  # D
        return f"🚫 D档极高风险：强烈建议不申购。若已中签，暗盘/首日无条件卖出。"


def analyze_by_market_state(data, hsi_monthly, conditional_result):
    """按市场状态维度分析各指标"""
    label_data_market_state(data, hsi_monthly)
    
    results = []
    for state in [BULL, BEAR, NEUTRAL]:
        group = [d for d in data if d.get("_market_state") == state]
        if not group:
            continue
        s = calc_stats(group)
        s["state"] = state
        s["label"] = STATE_LABELS.get(state, state)
        s["color"] = STATE_COLORS.get(state, "#888")
        
        # 各时点分析
        s["tp_stats"] = analyze_selling_timepoints(group)
        
        # 最优时点
        valid_tps = [tp for tp in s["tp_stats"] if tp["count"] > 0]
        s["best_tp"] = max(valid_tps, key=lambda x: x["expected"])["label"] if valid_tps else "N/A"
        s["best_expected"] = max(valid_tps, key=lambda x: x["expected"])["expected"] if valid_tps else 0
        
        # 子模型信息
        model = conditional_result["models"].get(state, {})
        s["model_r2"] = model.get("extra", {}).get("r2", 0)
        s["model_warning"] = model.get("warning")
        s["is_degraded"] = state in conditional_result.get("degraded_states", [])
        
        results.append(s)
    
    return results
