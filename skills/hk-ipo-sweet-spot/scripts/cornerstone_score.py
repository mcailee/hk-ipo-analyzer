#!/usr/bin/env python3
"""基石投资者评分模块 — "聪明钱"/"割韭菜"分类 + 评分
基于基石投资者历史参投IPO的暗盘/首日表现，给新股基石阵容打分。

集成方式：作为engine.py score_ipo的一个附加因子，与超购/行业/基石/募资并列。
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cornerstone_data import CORNERSTONE_MAP, get_stocks_by_investor, get_all_investors

# ============================================
# 基石类别分类
# ============================================

# 聪明钱：国际顶级长线基金 + 头部公私募
_SMART_MONEY = {
    "富达国际", "景林", "CPE源峰", "淡马锡", "高瓴", "博裕", "广发基金",
    "贝莱德", "富国基金", "华夏基金", "瑞银", "GIC", "3W", "Aspex", "平安资管",
}

# 基石类别标签
_INVESTOR_CATEGORIES = {
    # 国际主权/长线
    "GIC": "国际主权", "淡马锡": "国际主权", "科威特投资局": "国际主权",
    "贝莱德": "国际长线", "富达国际": "国际长线", "Baillie Gifford": "国际长线",
    "施罗德": "国际长线", "瑞银": "国际长线", "Eastspring": "国际长线",
    
    # 头部私募/PE
    "高瓴": "头部PE", "CPE源峰": "头部PE", "博裕": "头部PE", "景林": "头部PE",
    "3W": "头部PE", "Aspex": "头部PE", "春华资本": "头部PE", "云锋基金": "头部PE",
    "高毅资产": "头部PE", "Janchor": "头部PE",
    
    # 头部公募
    "广发基金": "头部公募", "富国基金": "头部公募", "华夏基金": "头部公募",
    "易方达": "头部公募", "嘉实基金": "头部公募", "南方基金": "头部公募",
    "汇添富": "头部公募", "鹏华基金": "头部公募", "兴证全球": "头部公募",
    "诺安基金": "头部公募", "银华基金": "头部公募", "中欧基金": "头部公募",
    "前海开源": "头部公募", "大成基金": "头部公募", "惠理": "头部公募",
    "太平基金": "头部公募",
    
    # 银行理财
    "工银理财": "银行理财", "中邮理财": "银行理财", "建信理财": "银行理财",
    "招银理财": "银行理财", "交银理财": "银行理财", "平安资管": "银行理财",
    "国寿资管": "银行理财",
    
    # 产业巨头（AI/科技）
    "阿里巴巴": "产业巨头", "中移资本": "产业巨头", "联想": "产业巨头",
    "中兴": "产业巨头", "小米": "产业巨头", "豪威集团": "产业巨头",
    "胜宏科技": "产业巨头",
    
    # 产业链上下游（⚠️ 关联方风险）
    "广汽集团": "产业链关联", "蔚来资本": "产业链关联", "吉利": "产业链关联",
    "博世": "产业链关联", "上汽": "产业链关联", "亨通光电": "产业链关联",
    "海天国际": "产业链关联", "禾赛科技": "产业链关联",
    "君实生物": "产业链关联", "桂林三金": "产业链关联", "药明生物": "产业链关联",
    "中信金属": "产业链关联",
    
    # 地方国资（⚠️ 割韭菜高发区）
    "盈科壹号": "地方国资", "北京高精尖": "地方国资", "宁波国资": "地方国资",
    "烟台国资": "地方国资", "佛山发展控股": "地方国资",
    
    # 对冲基金（短线思维）
    "Ghisallo": "对冲基金", "Athos": "对冲基金", "Hel Ved": "对冲基金",
    "Ocean Arete": "对冲基金", "Anatole": "对冲基金",
    
    # 券商自营
    "中金公司": "券商自营", "中信证券投资": "券商自营",
    
    # 保险
    "泰康人寿": "保险", "阳光人寿": "保险",
    
    # 其他/未分类
    "高盛资管": "国际长线", "法巴资管": "国际长线", "太盟投资": "头部PE",
    "Oaktree": "头部PE", "中国东方": "AMC", "新武塘": "其他",
    "国惠香港": "其他", "昌荣国际": "其他", "锦绣中和": "其他",
    "Voyager": "其他", "裕祥控股": "其他", "至源控股": "其他",
    "Dream'ee": "其他", "君宜资本": "其他", "未来香港": "其他",
}

# 类别风险等级
_CATEGORY_RISK = {
    "国际主权": 1,      # 最安全
    "国际长线": 1,
    "头部PE": 2,
    "头部公募": 2,
    "银行理财": 3,
    "产业巨头": 2,
    "保险": 3,
    "券商自营": 3,
    "产业链关联": 4,    # ⚠️ 有关联方风险
    "地方国资": 5,      # 🚨 割韭菜高发区
    "对冲基金": 4,      # ⚠️ 短线思维
    "AMC": 4,
    "其他": 5,          # 未知=高风险
}


def classify_investor(name):
    """给基石投资者分类"""
    return _INVESTOR_CATEGORIES.get(name, "其他")


def classify_lineup(investor_names):
    """分析基石阵容的类别构成"""
    categories = {}
    for inv in investor_names:
        cat = classify_investor(inv)
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(inv)
    
    # 计算风险加权分
    total_risk = 0
    for cat, members in categories.items():
        risk = _CATEGORY_RISK.get(cat, 5)
        total_risk += risk * len(members)
    avg_risk = total_risk / len(investor_names) if investor_names else 5
    
    return {
        "categories": categories,
        "avg_risk": round(avg_risk, 1),
        "n_smart": sum(1 for inv in investor_names if inv in _SMART_MONEY),
        "n_local_gov": len(categories.get("地方国资", [])),
        "n_related": len(categories.get("产业链关联", [])),
        "n_hedge": len(categories.get("对冲基金", [])),
    }


def build_investor_profiles(ipo_data):
    """构建每个基石投资者的历史表现画像。
    
    Returns:
        dict: {investor_name: {avg_day1, win_rate, n_stocks, label, score}}
        label: "smart_money" / "neutral" / "dumb_money"
    """
    ipo_by_code = {d["code"]: d for d in ipo_data}
    profiles = {}
    
    for inv in get_all_investors():
        codes = get_stocks_by_investor(inv)
        returns = []
        for code in codes:
            d = ipo_by_code.get(code)
            if d and d.get("day1_return") is not None:
                returns.append(d["day1_return"])
        
        if not returns:
            continue
        
        avg_d1 = sum(returns) / len(returns)
        win_rate = sum(1 for r in returns if r > 0) / len(returns) * 100
        n = len(returns)
        
        # 分类逻辑
        # 聪明钱：参与≥3只 & 首日均值>50% & 胜率>80%
        # 或：参与≥5只 & 首日均值>30% & 胜率>75%
        if (n >= 3 and avg_d1 > 50 and win_rate > 80) or \
           (n >= 5 and avg_d1 > 30 and win_rate > 75):
            label = "smart_money"
        # 割韭菜：参与≥3只 & 首日均值<0% 或 胜率<50%
        elif n >= 3 and (avg_d1 < 0 or win_rate < 50):
            label = "dumb_money"
        else:
            label = "neutral"
        
        # 评分：归一化到0-100
        # 基于均值+胜率的加权
        raw_score = avg_d1 * 0.6 + win_rate * 0.4
        score = max(0, min(100, raw_score))
        
        profiles[inv] = {
            "avg_day1": round(avg_d1, 1),
            "win_rate": round(win_rate, 1),
            "n_stocks": n,
            "label": label,
            "score": round(score, 1),
        }
    
    return profiles


def score_cornerstone_lineup(investor_names, profiles):
    """给一组基石投资者阵容打分。
    
    Args:
        investor_names: 基石投资者名称列表
        profiles: build_investor_profiles的输出
    
    Returns:
        dict: {
            "cornerstone_score": float (0-100),
            "smart_money_count": int,
            "dumb_money_count": int,
            "avg_investor_score": float,
            "top_investors": list,  # 最佳基石
            "warning_investors": list,  # 割韭菜基石
            "label": str,  # "强基石"/"中基石"/"弱基石"
        }
    """
    if not investor_names or not profiles:
        return _default_score()
    
    matched = []
    smart_count = 0
    dumb_count = 0
    top_investors = []
    warning_investors = []
    
    for inv in investor_names:
        p = profiles.get(inv)
        if p:
            matched.append(p)
            if p["label"] == "smart_money":
                smart_count += 1
                top_investors.append({"name": inv, "score": p["score"], 
                                      "avg_day1": p["avg_day1"], "n": p["n_stocks"]})
            elif p["label"] == "dumb_money":
                dumb_count += 1
                warning_investors.append({"name": inv, "score": p["score"],
                                          "avg_day1": p["avg_day1"], "n": p["n_stocks"]})
    
    if not matched:
        return _default_score()
    
    # 类别分析
    lineup_class = classify_lineup(investor_names)
    
    # 综合评分
    avg_score = sum(p["score"] for p in matched) / len(matched)
    
    # 聪明钱加分：每个聪明钱+5分（最多+25）
    smart_bonus = min(25, smart_count * 5)
    # 割韭菜减分：每个-8分
    dumb_penalty = dumb_count * 8
    
    # [NEW] 类别风险惩罚
    # 地方国资：每个-10分
    local_gov_penalty = lineup_class["n_local_gov"] * 10
    # 产业链关联（纯关联方）：如果>50%是关联方，-15分
    related_penalty = 0
    if len(investor_names) > 0 and lineup_class["n_related"] / len(investor_names) > 0.5:
        related_penalty = 15
    # 对冲基金为主：-8分
    hedge_penalty = 0
    if len(investor_names) > 0 and lineup_class["n_hedge"] / len(investor_names) > 0.5:
        hedge_penalty = 8
    
    final_score = avg_score + smart_bonus - dumb_penalty - local_gov_penalty - related_penalty - hedge_penalty
    final_score = max(0, min(100, final_score))
    
    # 标签
    if final_score >= 70 or smart_count >= 5:
        label = "强基石"
    elif final_score >= 40 or smart_count >= 2:
        label = "中基石"
    else:
        label = "弱基石"
    
    # 排序top investors
    top_investors.sort(key=lambda x: x["score"], reverse=True)
    
    return {
        "cornerstone_score": round(final_score, 1),
        "smart_money_count": smart_count,
        "dumb_money_count": dumb_count,
        "total_matched": len(matched),
        "total_given": len(investor_names),
        "avg_investor_score": round(avg_score, 1),
        "top_investors": top_investors[:5],
        "warning_investors": warning_investors,
        "label": label,
        "lineup_class": lineup_class,
    }


def _default_score():
    return {
        "cornerstone_score": 50.0,
        "smart_money_count": 0,
        "dumb_money_count": 0,
        "total_matched": 0,
        "total_given": 0,
        "avg_investor_score": 50.0,
        "top_investors": [],
        "warning_investors": [],
        "label": "未知",
    }


def format_cornerstone_summary(result):
    """格式化基石评分摘要"""
    lines = []
    label_emoji = {"强基石": "🏆", "中基石": "📊", "弱基石": "⚠️", "未知": "❓"}
    emoji = label_emoji.get(result["label"], "")
    
    lines.append(f"{emoji} 基石阵容评分: {result['cornerstone_score']:.0f}/100 ({result['label']})")
    lines.append(f"   匹配 {result['total_matched']}/{result['total_given']} 个基石 | "
                 f"聪明钱 {result['smart_money_count']} 个 | 割韭菜 {result['dumb_money_count']} 个")
    
    # 类别构成
    lc = result.get("lineup_class")
    if lc:
        cat_str = " | ".join(f"{cat}×{len(members)}" for cat, members in 
                             sorted(lc["categories"].items(), key=lambda x: len(x[1]), reverse=True))
        lines.append(f"   构成: {cat_str}")
        
        # 风险警告
        if lc["n_local_gov"] > 0:
            lines.append(f"   🚨 地方国资×{lc['n_local_gov']}（割韭菜高发区）")
        if lc["n_related"] > 0 and lc["n_related"] / max(result["total_given"], 1) > 0.3:
            lines.append(f"   ⚠️ 产业链关联×{lc['n_related']}（关联方占比高）")
        if lc["n_hedge"] > 0 and lc["n_hedge"] / max(result["total_given"], 1) > 0.3:
            lines.append(f"   ⚠️ 对冲基金×{lc['n_hedge']}（短线思维，上市后可能快速减持）")
    
    if result["top_investors"]:
        top_str = ", ".join(f"{t['name']}({t['avg_day1']:+.0f}%/{t['n']}只)" 
                           for t in result["top_investors"][:3])
        lines.append(f"   💰 聪明钱: {top_str}")
    
    if result["warning_investors"]:
        warn_str = ", ".join(f"{w['name']}({w['avg_day1']:+.0f}%/{w['n']}只)" 
                            for w in result["warning_investors"])
        lines.append(f"   🚨 割韭菜: {warn_str}")
    
    return "\n".join(lines)


# ============================================
# 聪明钱/割韭菜清单
# ============================================

def print_smart_dumb_list(profiles):
    """打印聪明钱和割韭菜清单"""
    smart = [(k, v) for k, v in profiles.items() if v["label"] == "smart_money"]
    smart.sort(key=lambda x: x[1]["score"], reverse=True)
    
    dumb = [(k, v) for k, v in profiles.items() if v["label"] == "dumb_money"]
    dumb.sort(key=lambda x: x[1]["score"])
    
    neutral = [(k, v) for k, v in profiles.items() if v["label"] == "neutral"]
    neutral.sort(key=lambda x: x[1]["score"], reverse=True)
    
    print("=" * 80)
    print("  💰 聪明钱 (Smart Money)")
    print("=" * 80)
    print(f"{'名称':<16} {'参与':>4} {'首日均值':>8} {'胜率':>6} {'评分':>6}")
    print("-" * 60)
    for inv, p in smart:
        print(f"  {inv:<14} {p['n_stocks']:>3}只 {p['avg_day1']:>+7.1f}% {p['win_rate']:>5.0f}% {p['score']:>5.0f}")
    
    print(f"\n{'='*80}")
    print("  📊 中性 (Neutral)")
    print(f"{'='*80}")
    for inv, p in neutral[:15]:
        print(f"  {inv:<14} {p['n_stocks']:>3}只 {p['avg_day1']:>+7.1f}% {p['win_rate']:>5.0f}% {p['score']:>5.0f}")
    if len(neutral) > 15:
        print(f"  ... 及其他 {len(neutral)-15} 个")
    
    if dumb:
        print(f"\n{'='*80}")
        print("  🚨 割韭菜 (Dumb Money)")
        print(f"{'='*80}")
        for inv, p in dumb:
            print(f"  {inv:<14} {p['n_stocks']:>3}只 {p['avg_day1']:>+7.1f}% {p['win_rate']:>5.0f}% {p['score']:>5.0f}")
    else:
        print(f"\n✅ 暂无「割韭菜」基石（当前样本中所有高频基石表现都不差）")
    
    print(f"\n📊 统计: 聪明钱 {len(smart)} 个 | 中性 {len(neutral)} 个 | 割韭菜 {len(dumb)} 个")


# ============================================
# 测试
# ============================================

if __name__ == "__main__":
    from data import ipo_data
    
    print("构建基石画像...\n")
    profiles = build_investor_profiles(ipo_data)
    print_smart_dumb_list(profiles)
    
    # 测试几个阵容
    test_cases = [
        ("商米科技(弱基石)", ["中国东方", "新武塘"]),
        ("曦智科技(超强)", ["阿里巴巴", "中移资本", "联想", "中兴", "GIC", "贝莱德", "富达国际",
                          "Baillie Gifford", "施罗德", "淡马锡", "瑞银", "高瓴", "景林", "CPE源峰"]),
        ("胜宏科技(38家)", ["CPE源峰", "Janchor", "云锋基金", "瑞银", "GIC", "贝莱德", "富达国际",
                          "高瓴", "景林", "博裕", "广发基金", "华夏基金", "易方达", "富国基金",
                          "惠理", "淡马锡", "Aspex"]),
        ("迈威生物(关联方)", ["君实生物", "桂林三金", "药明生物", "国惠香港", "昌荣国际", "锦绣中和"]),
        ("泽景股份(地方国资)", ["盈科壹号", "北京高精尖"]),
        ("小马智行(对冲基金)", ["Eastspring", "Ghisallo", "Athos", "Hel Ved", "Ocean Arete"]),
        ("黑芝麻智能(产业链)", ["蔚来资本", "吉利", "博世", "上汽"]),
        ("埃斯顿(混合)", ["嘉实基金", "亨通光电", "君宜资本", "至源控股", "海天国际", "裕祥控股", "Dream'ee"]),
    ]
    
    print(f"\n{'='*80}")
    print("  阵容评分测试")
    print(f"{'='*80}")
    for name, investors in test_cases:
        result = score_cornerstone_lineup(investors, profiles)
        print(f"\n{name}:")
        print(format_cornerstone_summary(result))
