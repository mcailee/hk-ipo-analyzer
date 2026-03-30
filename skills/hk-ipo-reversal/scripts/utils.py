#!/usr/bin/env python3
"""港股新股暗盘反转猎手 - 数学工具库
手写实现：Logistic回归、Bootstrap、层次聚类、矩阵运算、统计函数
零外部依赖，纯Python 3标准库
"""
import math
import random

# ============================================
# 基础统计函数
# ============================================

def safe_values(data, key):
    """提取非None值"""
    return [d[key] for d in data if d.get(key) is not None]

def median(values):
    if not values: return 0
    s = sorted(values)
    n = len(s)
    return s[n//2] if n % 2 == 1 else (s[n//2-1] + s[n//2]) / 2

def mean(values):
    if not values: return 0
    return sum(values) / len(values)

def std_dev(values):
    if len(values) < 2: return 0
    m = mean(values)
    return math.sqrt(sum((v - m)**2 for v in values) / (len(values) - 1))

def percentile(values, p):
    """计算百分位数 (p: 0-100)"""
    if not values: return 0
    s = sorted(values)
    k = (len(s) - 1) * p / 100
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return s[int(k)]
    return s[f] * (c - k) + s[c] * (k - f)

def calc_stats(group, return_key="day1_return"):
    """通用统计计算，null-safe"""
    returns = [d[return_key] for d in group if d.get(return_key) is not None]
    if not returns:
        return {"count": 0, "avg": 0, "median": 0, "win_rate": 0,
                "max": 0, "min": 0, "expected": 0, "avg_win": 0, "avg_loss": 0, "std": 0}
    n = len(returns)
    winners = [r for r in returns if r > 0]
    losers = [r for r in returns if r < 0]
    avg_win = sum(winners)/len(winners) if winners else 0
    avg_loss = sum(losers)/len(losers) if losers else 0
    wr = len(winners)/n*100
    exp = (len(winners)/n)*avg_win + (len(losers)/n)*avg_loss if n > 0 else 0
    return {"count": n, "avg": sum(returns)/n, "median": median(returns),
            "win_rate": wr, "max": max(returns), "min": min(returns),
            "expected": exp, "avg_win": avg_win, "avg_loss": avg_loss,
            "std": std_dev(returns)}


# ============================================
# 矩阵运算（复用自 sweet-spot）
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
            return None
        pivot = M[col][col]
        for j in range(2*n):
            M[col][j] /= pivot
        for row in range(n):
            if row != col:
                factor = M[row][col]
                for j in range(2*n):
                    M[row][j] -= factor * M[col][j]
    return [row[n:] for row in M]


# ============================================
# 信息增益
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
# 手写 Logistic 回归（梯度下降）
# ============================================

def sigmoid(z):
    """Sigmoid函数，防止溢出"""
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    else:
        ez = math.exp(z)
        return ez / (1.0 + ez)

def logistic_predict_proba(X, weights, bias):
    """预测概率"""
    probs = []
    for x in X:
        z = bias + sum(w * xi for w, xi in zip(weights, x))
        probs.append(sigmoid(z))
    return probs

def logistic_regression(X, y, lr=0.01, epochs=1000, reg_lambda=0.01):
    """手写Logistic回归 - 带L2正则化的梯度下降

    Args:
        X: 特征矩阵 [[x1, x2, ...], ...]
        y: 标签 [0, 1, ...]
        lr: 学习率
        epochs: 迭代次数
        reg_lambda: L2正则化系数

    Returns:
        weights: 特征权重
        bias: 偏置
        history: 训练历史 {"losses": [...]}
    """
    n = len(X)
    if n == 0:
        return [], 0, {"losses": []}

    n_features = len(X[0])
    weights = [0.0] * n_features
    bias = 0.0
    losses = []

    for epoch in range(epochs):
        # Forward
        preds = logistic_predict_proba(X, weights, bias)

        # Loss (binary cross-entropy + L2)
        loss = 0
        for i in range(n):
            p = max(min(preds[i], 1 - 1e-15), 1e-15)
            loss -= y[i] * math.log(p) + (1 - y[i]) * math.log(1 - p)
        loss /= n
        loss += reg_lambda * sum(w**2 for w in weights) / (2 * n)

        if epoch % 100 == 0:
            losses.append(loss)

        # Gradients
        dw = [0.0] * n_features
        db = 0.0
        for i in range(n):
            error = preds[i] - y[i]
            for j in range(n_features):
                dw[j] += error * X[i][j]
            db += error

        for j in range(n_features):
            dw[j] = dw[j] / n + reg_lambda * weights[j] / n
        db /= n

        # Update
        for j in range(n_features):
            weights[j] -= lr * dw[j]
        bias -= lr * db

    return weights, bias, {"losses": losses}

def logistic_accuracy(X, y, weights, bias):
    """计算准确率"""
    preds = logistic_predict_proba(X, weights, bias)
    correct = sum(1 for p, yi in zip(preds, y) if (p >= 0.5) == (yi == 1))
    return correct / len(y) if y else 0

def logistic_auc_approx(X, y, weights, bias):
    """近似AUC（Mann-Whitney U统计量方法）"""
    preds = logistic_predict_proba(X, weights, bias)
    pos_scores = [p for p, yi in zip(preds, y) if yi == 1]
    neg_scores = [p for p, yi in zip(preds, y) if yi == 0]

    if not pos_scores or not neg_scores:
        return 0.5

    concordant = 0
    total = 0
    for ps in pos_scores:
        for ns in neg_scores:
            total += 1
            if ps > ns:
                concordant += 1
            elif ps == ns:
                concordant += 0.5

    return concordant / total if total > 0 else 0.5


# ============================================
# Bootstrap 置信区间
# ============================================

def bootstrap_ci(values, stat_fn=None, n_bootstrap=1000, ci=0.95, seed=42):
    """Bootstrap置信区间

    Args:
        values: 数据列表
        stat_fn: 统计函数 (默认均值)
        n_bootstrap: 重采样次数
        ci: 置信水平

    Returns:
        dict: {"estimate": float, "ci_lower": float, "ci_upper": float, "std_error": float}
    """
    if not values:
        return {"estimate": 0, "ci_lower": 0, "ci_upper": 0, "std_error": 0}

    if stat_fn is None:
        stat_fn = mean

    rng = random.Random(seed)
    n = len(values)
    boot_stats = []

    for _ in range(n_bootstrap):
        sample = [values[rng.randint(0, n-1)] for _ in range(n)]
        boot_stats.append(stat_fn(sample))

    boot_stats.sort()
    alpha = 1 - ci
    lo_idx = int(n_bootstrap * alpha / 2)
    hi_idx = int(n_bootstrap * (1 - alpha / 2))
    lo_idx = max(0, min(lo_idx, n_bootstrap - 1))
    hi_idx = max(0, min(hi_idx, n_bootstrap - 1))

    return {
        "estimate": stat_fn(values),
        "ci_lower": boot_stats[lo_idx],
        "ci_upper": boot_stats[hi_idx],
        "std_error": std_dev(boot_stats),
    }

def bootstrap_proportion_ci(successes, total, n_bootstrap=1000, ci=0.95, seed=42):
    """Bootstrap比率置信区间"""
    if total == 0:
        return {"estimate": 0, "ci_lower": 0, "ci_upper": 0, "std_error": 0}

    values = [1] * successes + [0] * (total - successes)
    return bootstrap_ci(values, mean, n_bootstrap, ci, seed)


# ============================================
# 层次聚类（Ward方法）
# ============================================

def euclidean_distance(a, b):
    """欧式距离"""
    return math.sqrt(sum((ai - bi)**2 for ai, bi in zip(a, b)))

def ward_distance(cluster_a, cluster_b):
    """Ward距离：合并后组内方差增量"""
    na, nb = len(cluster_a), len(cluster_b)
    if na == 0 or nb == 0:
        return float('inf')
    dim = len(cluster_a[0])
    # 各组中心
    ca = [sum(p[d] for p in cluster_a) / na for d in range(dim)]
    cb = [sum(p[d] for p in cluster_b) / nb for d in range(dim)]
    # Ward增量
    return (na * nb / (na + nb)) * sum((ca[d] - cb[d])**2 for d in range(dim))

def hierarchical_clustering(points, n_clusters=4):
    """层次聚类（自底向上，Ward方法）

    Args:
        points: [[x1, x2, ...], ...] 数据点
        n_clusters: 目标聚类数

    Returns:
        labels: [0, 1, 2, ...] 每个点的聚类标签
    """
    n = len(points)
    if n <= n_clusters:
        return list(range(n))

    # 初始：每个点一个簇
    clusters = {i: [points[i]] for i in range(n)}
    point_cluster = {i: i for i in range(n)}
    next_id = n

    while len(clusters) > n_clusters:
        # 找最小Ward距离的两个簇
        best_dist = float('inf')
        best_pair = None
        cluster_ids = list(clusters.keys())

        for i_idx in range(len(cluster_ids)):
            for j_idx in range(i_idx + 1, len(cluster_ids)):
                ci, cj = cluster_ids[i_idx], cluster_ids[j_idx]
                d = ward_distance(clusters[ci], clusters[cj])
                if d < best_dist:
                    best_dist = d
                    best_pair = (ci, cj)

        if best_pair is None:
            break

        ci, cj = best_pair
        # 合并
        merged = clusters[ci] + clusters[cj]
        clusters[next_id] = merged

        # 更新 point→cluster 映射
        for i in range(n):
            if point_cluster[i] == ci or point_cluster[i] == cj:
                point_cluster[i] = next_id

        del clusters[ci]
        del clusters[cj]
        next_id += 1

    # 转换为 0-based 标签
    cluster_ids = sorted(clusters.keys())
    id_to_label = {cid: idx for idx, cid in enumerate(cluster_ids)}
    labels = [id_to_label[point_cluster[i]] for i in range(n)]
    return labels


# ============================================
# 特征标准化
# ============================================

def standardize(values):
    """Z-score标准化"""
    if not values or len(values) < 2:
        return values[:], 0, 1
    m = mean(values)
    s = std_dev(values)
    if s < 1e-12:
        return [0.0] * len(values), m, 1
    return [(v - m) / s for v in values], m, s

def normalize_01(values):
    """Min-Max归一化到[0,1]"""
    if not values:
        return values[:], 0, 1
    lo, hi = min(values), max(values)
    if hi - lo < 1e-12:
        return [0.5] * len(values), lo, hi
    return [(v - lo) / (hi - lo) for v in values], lo, hi


# ============================================
# 相似度计算
# ============================================

def cosine_similarity(a, b):
    """余弦相似度"""
    dot = sum(ai * bi for ai, bi in zip(a, b))
    norm_a = math.sqrt(sum(ai**2 for ai in a))
    norm_b = math.sqrt(sum(bi**2 for bi in b))
    if norm_a < 1e-12 or norm_b < 1e-12:
        return 0
    return dot / (norm_a * norm_b)

def find_similar(target_features, all_features, all_data, top_n=5):
    """找最相似的案例

    Args:
        target_features: 目标特征向量
        all_features: 所有案例特征矩阵
        all_data: 所有案例原始数据
        top_n: 返回前N个

    Returns:
        [(similarity, data_record), ...]
    """
    scores = []
    for i, feat in enumerate(all_features):
        dist = euclidean_distance(target_features, feat)
        sim = 1.0 / (1.0 + dist)
        scores.append((sim, all_data[i]))

    scores.sort(key=lambda x: -x[0])
    return scores[:top_n]


# ============================================
# 市场状态分类（继承自 sweet-spot）
# ============================================

BULL = "BULL"
BEAR = "BEAR"
NEUTRAL = "NEUTRAL"

STATE_LABELS = {BULL: "🐂 牛市", BEAR: "🐻 熊市", NEUTRAL: "⚖️ 震荡"}
STATE_COLORS = {BULL: "#ff4444", BEAR: "#00b050", NEUTRAL: "#ffaa00"}

def classify_market_state(date_str, hsi_monthly):
    """根据上市日期前3个月恒指累计涨跌幅判定市场状态"""
    if date_str == "未上市" or not hsi_monthly:
        return None

    try:
        parts = date_str.split("-")
        y, m = int(parts[0]), int(parts[1])
    except (ValueError, IndexError):
        return None

    cumulative = 0.0
    months_found = 0
    for offset in range(1, 4):
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
        return NEUTRAL

    if cumulative > 8.0:
        return BULL
    elif cumulative < -8.0:
        return BEAR
    else:
        return NEUTRAL

def get_current_market_state(hsi_monthly):
    """获取当前市场状态"""
    if not hsi_monthly:
        return NEUTRAL
    sorted_keys = sorted(hsi_monthly.keys(), reverse=True)
    if len(sorted_keys) < 3:
        return NEUTRAL
    cumulative = sum(hsi_monthly[k] for k in sorted_keys[:3])
    if cumulative > 8.0:
        return BULL
    elif cumulative < -8.0:
        return BEAR
    else:
        return NEUTRAL

def label_data_market_state(data, hsi_monthly):
    """为数据集打市场状态标签"""
    for d in data:
        d["_market_state"] = classify_market_state(d.get("date", ""), hsi_monthly)
