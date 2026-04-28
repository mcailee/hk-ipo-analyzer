#!/usr/bin/env python3
"""基石投资者 → 股票表现分析
分析每个基石投资者参与的IPO的暗盘/首日表现，找出"黄金基石"。
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data import ipo_data
from cornerstone_data import CORNERSTONE_MAP, get_all_investors, get_stocks_by_investor


def analyze_cornerstone_performance():
    """分析每个基石投资者的IPO表现"""
    # 建立code→ipo_data的索引
    ipo_by_code = {d["code"]: d for d in ipo_data}
    
    # 统计每个基石的表现
    investor_stats = {}
    all_investors = get_all_investors()
    
    for inv in all_investors:
        codes = get_stocks_by_investor(inv)
        stocks = []
        for code in codes:
            d = ipo_by_code.get(code)
            if d and d.get("day1_return") is not None:
                stocks.append({
                    "name": d["name"],
                    "code": code,
                    "dark_return": d.get("dark_return"),
                    "day1_return": d["day1_return"],
                    "category": d.get("category", ""),
                    "subscription_mult": d.get("subscription_mult", 0),
                    "fundraising": d.get("fundraising", 0),
                })
        
        if not stocks:
            continue
        
        dark_returns = [s["dark_return"] for s in stocks if s["dark_return"] is not None]
        day1_returns = [s["day1_return"] for s in stocks]
        
        win_rate_d1 = sum(1 for r in day1_returns if r > 0) / len(day1_returns) * 100
        win_rate_dark = sum(1 for r in dark_returns if r > 0) / len(dark_returns) * 100 if dark_returns else 0
        
        investor_stats[inv] = {
            "n_stocks": len(stocks),
            "stocks": stocks,
            "avg_dark": sum(dark_returns) / len(dark_returns) if dark_returns else 0,
            "avg_day1": sum(day1_returns) / len(day1_returns),
            "median_day1": sorted(day1_returns)[len(day1_returns)//2],
            "win_rate_d1": win_rate_d1,
            "win_rate_dark": win_rate_dark,
            "best": max(stocks, key=lambda s: s["day1_return"]),
            "worst": min(stocks, key=lambda s: s["day1_return"]),
        }
    
    return investor_stats


def print_report(stats):
    """打印基石表现报告"""
    # 按参与数量 * 平均首日收益排序（综合评分）
    ranked = sorted(stats.items(), 
                    key=lambda x: x[1]["avg_day1"] * min(x[1]["n_stocks"], 10),
                    reverse=True)
    
    print("=" * 100)
    print("  基石投资者表现排行榜 — 按参与IPO的暗盘/首日表现")
    print("=" * 100)
    
    # 只显示参与>=3只的
    print(f"\n{'排名':>4} {'基石投资者':<16} {'参与':>4} {'暗盘均值':>8} {'首日均值':>8} {'首日中位':>8} {'胜率':>6} {'最佳':>20}")
    print("-" * 100)
    
    rank = 0
    for inv, s in ranked:
        if s["n_stocks"] < 3:
            continue
        rank += 1
        best_name = s["best"]["name"]
        best_d1 = s["best"]["day1_return"]
        print(f"{rank:>4}. {inv:<16} {s['n_stocks']:>3}只 "
              f"{s['avg_dark']:>+7.1f}% {s['avg_day1']:>+7.1f}% {s['median_day1']:>+7.1f}% "
              f"{s['win_rate_d1']:>5.0f}% {best_name}({best_d1:+.0f}%)")
    
    # 参与<3只的小型基石
    print(f"\n--- 参与<3只的基石 ---")
    small = [(inv, s) for inv, s in ranked if s["n_stocks"] < 3 and s["n_stocks"] >= 1]
    for inv, s in small[:20]:
        stocks_str = ", ".join(f"{st['name']}({st['day1_return']:+.0f}%)" for st in s["stocks"])
        print(f"  {inv}: {stocks_str}")
    
    # 关键发现
    print(f"\n{'='*100}")
    print("💡 关键发现")
    print(f"{'='*100}")
    
    # Top5黄金基石（参与≥5只且首日均值最高）
    top5 = [(inv, s) for inv, s in ranked if s["n_stocks"] >= 5][:5]
    print("\n🏆 黄金基石 Top5（参与≥5只，首日均值最高）：")
    for inv, s in top5:
        stocks_names = [st["name"] for st in sorted(s["stocks"], key=lambda x: x["day1_return"], reverse=True)]
        print(f"  {inv}: {s['n_stocks']}只 | 暗盘均{s['avg_dark']:+.1f}% 首日均{s['avg_day1']:+.1f}% | 胜率{s['win_rate_d1']:.0f}%")
        print(f"    参投: {', '.join(stocks_names[:8])}{'...' if len(stocks_names) > 8 else ''}")
    
    # 常出现在高收益IPO中的基石
    print("\n🎯 高收益IPO(首日>100%)中最常出现的基石：")
    high_perf_counts = {}
    for inv, s in stats.items():
        high_count = sum(1 for st in s["stocks"] if st["day1_return"] > 100)
        if high_count > 0:
            high_perf_counts[inv] = high_count
    
    for inv, count in sorted(high_perf_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
        s = stats[inv]
        high_stocks = [st["name"] for st in s["stocks"] if st["day1_return"] > 100]
        print(f"  {inv}: {count}只翻倍 / {s['n_stocks']}只总计 ({count/s['n_stocks']*100:.0f}%) → {', '.join(high_stocks)}")
    
    # 反面教材：参与多但表现差的
    print("\n⚠️ 参与多但首日均值<30%的基石：")
    low_perf = [(inv, s) for inv, s in stats.items() if s["n_stocks"] >= 5 and s["avg_day1"] < 30]
    for inv, s in sorted(low_perf, key=lambda x: x[1]["avg_day1"]):
        print(f"  {inv}: {s['n_stocks']}只 | 首日均{s['avg_day1']:+.1f}% | 胜率{s['win_rate_d1']:.0f}%")


def generate_html_report(stats, output_path):
    """生成HTML报告"""
    ranked = sorted(stats.items(),
                    key=lambda x: x[1]["avg_day1"] * min(x[1]["n_stocks"], 10),
                    reverse=True)
    
    html = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<title>基石投资者表现分析</title>
<style>
:root { --bg:#0d1117; --card:#161b22; --border:#30363d; --text:#e6edf3; --text2:#8b949e;
  --red:#f85149; --green:#3fb950; --blue:#58a6ff; --yellow:#d29922; --purple:#bc8cff; }
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:-apple-system,sans-serif; background:var(--bg); color:var(--text); padding:20px; max-width:1400px; margin:0 auto; }
h1 { font-size:1.5em; margin-bottom:8px; }
h2 { font-size:1.2em; margin:20px 0 10px; color:var(--blue); }
.subtitle { color:var(--text2); font-size:0.9em; margin-bottom:16px; }
.card { background:var(--card); border:1px solid var(--border); border-radius:8px; padding:16px; margin-bottom:16px; }
table { width:100%; border-collapse:collapse; font-size:0.85em; }
th { background:#21262d; color:var(--text2); padding:8px 6px; text-align:right; font-weight:600; border-bottom:2px solid var(--border); }
th:first-child,th:nth-child(2) { text-align:left; }
td { padding:7px 6px; text-align:right; border-bottom:1px solid var(--border); }
td:first-child,td:nth-child(2) { text-align:left; }
.pos { color:var(--red); } .neg { color:var(--green); }
.tag { display:inline-block; padding:2px 6px; border-radius:4px; font-size:0.75em; }
.gold { background:#2a2000; color:var(--yellow); }
.bar { height:4px; border-radius:2px; background:var(--border); margin-top:4px; }
.bar-fill { height:100%; border-radius:2px; }
.stocks-list { font-size:0.78em; color:var(--text2); }
</style></head><body>
<h1>🏛️ 基石投资者表现分析</h1>
<p class="subtitle">覆盖""" + str(len(CORNERSTONE_MAP)) + """只新股 · 基于暗盘/首日涨跌幅 · 数据集142只</p>

<h2>📊 基石表现排行（参与≥3只）</h2>
<div class="card"><table>
<tr><th>#</th><th>基石投资者</th><th>参与数</th><th>暗盘均值</th><th>首日均值</th><th>首日中位</th><th>胜率</th><th>翻倍数</th><th>参投标的</th></tr>
"""
    rank = 0
    for inv, s in ranked:
        if s["n_stocks"] < 3:
            continue
        rank += 1
        d1_cls = "pos" if s["avg_day1"] > 0 else "neg"
        dk_cls = "pos" if s["avg_dark"] > 0 else "neg"
        
        high_count = sum(1 for st in s["stocks"] if st["day1_return"] > 100)
        stocks_str = ", ".join(f"{st['name']}({st['day1_return']:+.0f}%)" 
                              for st in sorted(s["stocks"], key=lambda x: x["day1_return"], reverse=True)[:6])
        if len(s["stocks"]) > 6:
            stocks_str += "..."
        
        gold = ' <span class="tag gold">🏆</span>' if rank <= 5 else ""
        html += f"""<tr>
<td>{rank}</td><td>{inv}{gold}</td><td>{s['n_stocks']}</td>
<td class="{dk_cls}">{s['avg_dark']:+.1f}%</td>
<td class="{d1_cls}">{s['avg_day1']:+.1f}%</td>
<td class="{d1_cls}">{s['median_day1']:+.1f}%</td>
<td>{s['win_rate_d1']:.0f}%</td>
<td>{high_count}</td>
<td class="stocks-list">{stocks_str}</td>
</tr>\n"""
    
    html += "</table></div>"
    
    # 参与<3只
    html += '<h2>📋 低频基石（参与1-2只）</h2><div class="card"><table>'
    html += '<tr><th>基石投资者</th><th>参投标的</th></tr>'
    small = [(inv, s) for inv, s in ranked if 1 <= s["n_stocks"] < 3]
    for inv, s in small:
        stocks_str = ", ".join(f"{st['name']}({st['day1_return']:+.0f}%)" for st in s["stocks"])
        html += f'<tr><td>{inv}</td><td class="stocks-list">{stocks_str}</td></tr>\n'
    html += "</table></div>"
    
    html += "</body></html>"
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ HTML报告已生成: {output_path}")


if __name__ == "__main__":
    stats = analyze_cornerstone_performance()
    print_report(stats)
    
    # 生成HTML
    script_dir = os.path.dirname(os.path.abspath(__file__))
    html_path = os.path.join(script_dir, "cornerstone_analysis.html")
    generate_html_report(stats, html_path)
