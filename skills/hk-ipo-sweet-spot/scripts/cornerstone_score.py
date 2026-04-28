#!/usr/bin/env python3
"""基石投资者评分模块 — "聪明钱"/"割韭菜"分类 + 评分
基于基石投资者历史参投IPO的暗盘/首日表现，给新股基石阵容打分。

集成方式：作为engine.py score_ipo的一个附加因子，与超购/行业/基石/募资并列。
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cornerstone_data import CORNERSTONE_MAP, get_stocks_by_investor, get_all_investors


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
    
    # 综合评分
    avg_score = sum(p["score"] for p in matched) / len(matched)
    
    # 聪明钱加分：每个聪明钱+5分（最多+25）
    smart_bonus = min(25, smart_count * 5)
    # 割韭菜减分：每个-8分
    dumb_penalty = dumb_count * 8
    
    final_score = avg_score + smart_bonus - dumb_penalty
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
        ("假设纯聪明钱", ["高瓴", "CPE源峰", "景林", "博裕", "GIC", "淡马锡", "富达国际"]),
    ]
    
    print(f"\n{'='*80}")
    print("  阵容评分测试")
    print(f"{'='*80}")
    for name, investors in test_cases:
        result = score_cornerstone_lineup(investors, profiles)
        print(f"\n{name}:")
        print(format_cornerstone_summary(result))
