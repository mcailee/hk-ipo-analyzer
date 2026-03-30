#!/usr/bin/env python3
"""港股新股暗盘反转猎手 V2 - HTML报告生成器 (期望偏差版)
暗色主题，内嵌SVG图表，三种模式：全量/单股/预测
核心升级：从"暗盘下跌/反转"泛化为"偏差/修正"
"""
from utils import mean, median, std_dev, STATE_LABELS, STATE_COLORS
from reversal_engine import (
    PATH_TIMEPOINTS, PATTERN_LABELS, PATTERN_COLORS, PATTERN_EMOJIS,
    RECOVERY_WINDOWS, DEVIATION_CATEGORIES, classify_deviation_type,
)

# ============================================
# 通用CSS样式
# ============================================

CSS = """
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { background: #0d1117; color: #c9d1d9; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; line-height: 1.6; padding: 20px; }
.container { max-width: 1200px; margin: 0 auto; }
h1 { color: #58a6ff; font-size: 28px; margin-bottom: 8px; }
h2 { color: #58a6ff; font-size: 22px; margin: 30px 0 15px; border-bottom: 1px solid #21262d; padding-bottom: 8px; }
h3 { color: #8b949e; font-size: 16px; margin: 20px 0 10px; }
.subtitle { color: #8b949e; font-size: 14px; margin-bottom: 20px; }
.card { background: #161b22; border: 1px solid #21262d; border-radius: 8px; padding: 20px; margin-bottom: 16px; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 16px; }
.grid-5 { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; }
.stat-box { background: #0d1117; border: 1px solid #21262d; border-radius: 6px; padding: 16px; text-align: center; }
.stat-value { font-size: 32px; font-weight: bold; }
.stat-label { color: #8b949e; font-size: 13px; margin-top: 4px; }
.positive { color: #ff4444; }
.negative { color: #3fb950; }
.neutral { color: #8b949e; }
table { width: 100%; border-collapse: collapse; margin: 10px 0; }
th { background: #21262d; color: #8b949e; padding: 10px 12px; text-align: left; font-size: 13px; font-weight: 600; }
td { padding: 10px 12px; border-bottom: 1px solid #21262d; font-size: 13px; }
tr:hover { background: #1c2128; }
.badge { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 12px; font-weight: 600; }
.badge-success { background: rgba(63,185,80,0.15); color: #3fb950; }
.badge-danger { background: rgba(255,68,68,0.15); color: #ff4444; }
.badge-warning { background: rgba(255,170,0,0.15); color: #ffaa00; }
.badge-info { background: rgba(88,166,255,0.15); color: #58a6ff; }
.badge-purple { background: rgba(163,113,247,0.15); color: #a371f7; }
.progress-bar { background: #21262d; border-radius: 4px; height: 24px; overflow: hidden; position: relative; }
.progress-fill { height: 100%; border-radius: 4px; transition: width 0.3s; }
.progress-text { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); font-size: 12px; font-weight: bold; }
.heatmap { display: grid; gap: 2px; }
.heatmap-cell { padding: 8px; text-align: center; border-radius: 4px; font-size: 12px; font-weight: bold; }
.path-chart { margin: 15px 0; }
svg text { font-family: -apple-system, sans-serif; }
.factor-item { display: flex; align-items: center; padding: 10px; border-bottom: 1px solid #21262d; }
.factor-emoji { font-size: 20px; margin-right: 12px; }
.factor-info { flex: 1; }
.factor-name { font-weight: 600; color: #c9d1d9; }
.factor-detail { color: #8b949e; font-size: 12px; }
.factor-score { font-weight: bold; font-size: 16px; }
.disclaimer { color: #484f58; font-size: 12px; margin-top: 30px; padding: 15px; border: 1px solid #21262d; border-radius: 6px; }
.similar-case { display: flex; align-items: center; padding: 8px; border-bottom: 1px solid #21262d; }
.similar-bar { width: 60px; height: 8px; background: #21262d; border-radius: 4px; margin-right: 10px; overflow: hidden; }
.similar-fill { height: 100%; background: #58a6ff; border-radius: 4px; }
.dev-type-tag { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600; margin-right: 4px; }
.dev-dark-down { background: rgba(255,68,68,0.15); color: #ff4444; }
.dev-below-exp { background: rgba(255,170,0,0.15); color: #ffaa00; }
.dev-potential { background: rgba(163,113,247,0.15); color: #a371f7; }
.dev-normal { background: rgba(139,148,158,0.15); color: #8b949e; }
</style>
"""


# ============================================
# SVG 图表工具
# ============================================

def svg_path_chart(paths_data, width=800, height=300, title=""):
    """绘制多条价格路径的SVG折线图"""
    if not paths_data:
        return ""

    n_points = len(paths_data[0]["path"])
    labels = [l for l, _ in PATH_TIMEPOINTS[:n_points]]

    all_vals = [v for pd in paths_data for v in pd["path"] if v is not None]
    if not all_vals:
        return ""
    y_min = min(all_vals) - 5
    y_max = max(all_vals) + 5
    if y_max - y_min < 10:
        y_max = y_min + 10

    margin = {"top": 30, "right": 20, "bottom": 40, "left": 60}
    chart_w = width - margin["left"] - margin["right"]
    chart_h = height - margin["top"] - margin["bottom"]

    def x_pos(i):
        return margin["left"] + i * chart_w / (n_points - 1) if n_points > 1 else margin["left"]
    def y_pos(v):
        return margin["top"] + (1 - (v - y_min) / (y_max - y_min)) * chart_h

    svg = f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:{width}px;">\n'
    svg += f'<rect width="{width}" height="{height}" fill="#0d1117" rx="6"/>\n'

    n_grid = 5
    for i in range(n_grid + 1):
        y_val = y_min + (y_max - y_min) * i / n_grid
        y = y_pos(y_val)
        svg += f'<line x1="{margin["left"]}" y1="{y:.0f}" x2="{width-margin["right"]}" y2="{y:.0f}" stroke="#21262d" stroke-width="1"/>\n'
        svg += f'<text x="{margin["left"]-8}" y="{y:.0f}" text-anchor="end" fill="#484f58" font-size="11" dy="4">{y_val:+.0f}%</text>\n'

    if y_min <= 0 <= y_max:
        y0 = y_pos(0)
        svg += f'<line x1="{margin["left"]}" y1="{y0:.0f}" x2="{width-margin["right"]}" y2="{y0:.0f}" stroke="#30363d" stroke-width="2" stroke-dasharray="5,5"/>\n'

    for i, label in enumerate(labels):
        x = x_pos(i)
        svg += f'<text x="{x:.0f}" y="{height-10}" text-anchor="middle" fill="#8b949e" font-size="11">{label}</text>\n'

    for pd in paths_data:
        path = pd["path"]
        color = pd.get("color", "#58a6ff")
        opacity = pd.get("opacity", 1.0)
        stroke_w = pd.get("stroke_width", 2)
        points = []
        for i, v in enumerate(path):
            if v is not None:
                points.append(f"{x_pos(i):.1f},{y_pos(v):.1f}")
        if points:
            svg += f'<polyline points="{" ".join(points)}" fill="none" stroke="{color}" stroke-width="{stroke_w}" opacity="{opacity}" stroke-linecap="round" stroke-linejoin="round"/>\n'
            if len(path) > 0 and path[-1] is not None:
                ex = x_pos(len(path)-1)
                ey = y_pos(path[-1])
                svg += f'<circle cx="{ex:.1f}" cy="{ey:.1f}" r="4" fill="{color}" opacity="{opacity}"/>\n'

    if title:
        svg += f'<text x="{width/2}" y="18" text-anchor="middle" fill="#c9d1d9" font-size="13" font-weight="600">{title}</text>\n'

    svg += '</svg>'
    return svg


def svg_bar_chart(data_points, width=600, height=200, title=""):
    """简单水平条形图"""
    if not data_points:
        return ""

    max_val = max(abs(d["value"]) for d in data_points) or 1
    bar_h = min(30, (height - 40) / len(data_points))
    total_h = bar_h * len(data_points) + 40

    svg = f'<svg viewBox="0 0 {width} {total_h}" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:{width}px;">\n'
    svg += f'<rect width="{width}" height="{total_h}" fill="#0d1117" rx="6"/>\n'

    if title:
        svg += f'<text x="{width/2}" y="18" text-anchor="middle" fill="#c9d1d9" font-size="13" font-weight="600">{title}</text>\n'

    y_start = 35
    label_w = 120
    bar_area = width - label_w - 80

    for i, d in enumerate(data_points):
        y = y_start + i * bar_h
        val = d["value"]
        color = d.get("color", "#58a6ff")
        bar_w = abs(val) / max_val * bar_area * 0.8

        svg += f'<text x="{label_w-8}" y="{y+bar_h/2+4}" text-anchor="end" fill="#8b949e" font-size="11">{d["label"]}</text>\n'
        svg += f'<rect x="{label_w}" y="{y+2}" width="{bar_w:.0f}" height="{bar_h-4}" fill="{color}" rx="3" opacity="0.8"/>\n'
        svg += f'<text x="{label_w+bar_w+8}" y="{y+bar_h/2+4}" fill="#c9d1d9" font-size="11">{val:.1f}%</text>\n'

    svg += '</svg>'
    return svg


def svg_heatmap(heatmap_data, width=700, height=350):
    """偏差阈值×窗口 修正率热力图"""
    if not heatmap_data:
        return '<div class="card">数据不足，无法生成热力图</div>'

    thresholds = sorted(heatmap_data.keys())
    windows = ["day1", "day3", "day5", "day7", "day10"]
    win_labels = ["Day1", "Day3", "Day5", "Day7", "Day10"]

    cell_w = (width - 100) / len(windows)
    cell_h = (height - 60) / len(thresholds)

    svg = f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:{width}px;">\n'
    svg += f'<rect width="{width}" height="{height}" fill="#0d1117" rx="6"/>\n'
    svg += f'<text x="{width/2}" y="18" text-anchor="middle" fill="#c9d1d9" font-size="13" font-weight="600">修正率热力图 (期望偏差阈值 × 回正窗口)</text>\n'

    for j, wl in enumerate(win_labels):
        x = 100 + j * cell_w + cell_w / 2
        svg += f'<text x="{x:.0f}" y="40" text-anchor="middle" fill="#8b949e" font-size="11">{wl}</text>\n'

    for i, t in enumerate(thresholds):
        y = 50 + i * cell_h
        svg += f'<text x="90" y="{y+cell_h/2+4:.0f}" text-anchor="end" fill="#8b949e" font-size="11">≤{t}%</text>\n'

        for j, w in enumerate(windows):
            x = 100 + j * cell_w
            cell = heatmap_data.get(t, {}).get(w, {})
            rate = cell.get("rate", 0)
            count = cell.get("count", 0)

            if count == 0:
                fill = "#161b22"
                text_color = "#484f58"
            elif rate >= 50:
                intensity = min((rate - 50) / 50, 1)
                r = int(255 * intensity)
                fill = f"rgba({r},68,68,0.4)"
                text_color = "#ff6666"
            elif rate >= 25:
                fill = "rgba(255,170,0,0.2)"
                text_color = "#ffaa00"
            else:
                fill = "rgba(63,185,80,0.15)"
                text_color = "#3fb950"

            svg += f'<rect x="{x+2:.0f}" y="{y+2:.0f}" width="{cell_w-4:.0f}" height="{cell_h-4:.0f}" fill="{fill}" rx="4"/>\n'
            if count > 0:
                svg += f'<text x="{x+cell_w/2:.0f}" y="{y+cell_h/2:.0f}" text-anchor="middle" fill="{text_color}" font-size="13" font-weight="bold" dy="2">{rate:.0f}%</text>\n'
                svg += f'<text x="{x+cell_w/2:.0f}" y="{y+cell_h/2+14:.0f}" text-anchor="middle" fill="#484f58" font-size="9">n={count}</text>\n'
            else:
                svg += f'<text x="{x+cell_w/2:.0f}" y="{y+cell_h/2+4:.0f}" text-anchor="middle" fill="#484f58" font-size="10">-</text>\n'

    svg += '</svg>'
    return svg


def color_for_return(val):
    if val is None: return "#484f58"
    return "#ff4444" if val > 0 else "#3fb950" if val < 0 else "#8b949e"

def format_return(val):
    if val is None: return "-"
    return f"{val:+.1f}%"

def format_pct(val):
    if val is None: return "-"
    return f"{val:.1f}%"

def dev_type_badge(dev_type):
    """生成偏差类型标签"""
    cls_map = {"dark_down": "dev-dark-down", "below_expectation": "dev-below-exp",
               "potential_release": "dev-potential", "normal": "dev-normal"}
    label = DEVIATION_CATEGORIES.get(dev_type, "其他")
    cls = cls_map.get(dev_type, "dev-normal")
    return f'<span class="dev-type-tag {cls}">{label}</span>'


# ============================================
# 模式1: 全量偏差修正统计报告
# ============================================

def generate_full_report(result):
    """生成全量偏差修正统计HTML报告"""
    dev_types = result.get("deviation_types", {})

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>港股新股反转猎手 V2 — 全量统计报告</title>
{CSS}
</head>
<body>
<div class="container">

<h1>🔄 港股新股反转猎手 V2</h1>
<p class="subtitle">期望偏差分析 | 数据集: {result['total']}只新股 (2024.06-2026.03)</p>

<!-- 1. 概览仪表板 -->
<h2>📊 偏差概览</h2>
<div class="grid-5">
    <div class="stat-box">
        <div class="stat-value">{result['total']}</div>
        <div class="stat-label">总样本</div>
    </div>
    <div class="stat-box">
        <div class="stat-value" style="color:#ff4444">{dev_types.get('dark_down', 0)}</div>
        <div class="stat-label">暗盘下跌</div>
    </div>
    <div class="stat-box">
        <div class="stat-value" style="color:#ffaa00">{dev_types.get('below_expectation', 0)}</div>
        <div class="stat-label">涨幅不及预期</div>
    </div>
    <div class="stat-box">
        <div class="stat-value" style="color:#a371f7">{dev_types.get('potential_release', 0)}</div>
        <div class="stat-label">潜力释放</div>
    </div>
    <div class="stat-box">
        <div class="stat-value" style="color:#3fb950">{dev_types.get('normal', 0)}</div>
        <div class="stat-label">表现正常</div>
    </div>
</div>

<div class="card" style="margin-top:16px;">
    <h3>💡 偏差模型说明</h3>
    <p style="color:#8b949e;margin-top:8px;">
        <strong>期望偏差 = 暗盘涨幅 - 预期涨幅</strong><br>
        预期涨幅基于超购倍数、基石投资者、行业和募资规模的历史分档统计推算。<br>
        当偏差为负时，说明暗盘表现不及预期——无论暗盘绝对涨跌幅是正是负。
    </p>
    <p style="margin-top:8px;">
        <span class="dev-type-tag dev-dark-down">暗盘下跌</span> 暗盘跌幅为负
        <span class="dev-type-tag dev-below-exp" style="margin-left:8px">涨幅不及预期</span> 暗盘涨了但远低于预期
        <span class="dev-type-tag dev-potential" style="margin-left:8px">潜力释放</span> 暗盘小涨→后续大涨
    </p>
</div>
"""

    # 偏差分布统计
    html += f"""
<div class="grid" style="margin-top:16px;">
    <div class="stat-box">
        <div class="stat-value" style="color:#ff6666">{result['underperform_count']}</div>
        <div class="stat-label">偏差为负(不及预期)</div>
    </div>
    <div class="stat-box">
        <div class="stat-value" style="color:#3fb950">{result['overperform_count']}</div>
        <div class="stat-label">偏差为正(超预期)</div>
    </div>
</div>
"""

    # 最优阈值
    best = result.get("best_threshold")
    if best:
        html += f"""
<div class="card" style="margin-top:16px;">
    <h3>🎯 最优修正定义 (自动寻优)</h3>
    <p style="margin-top:10px;">
        <span class="badge badge-info">偏差 ≤ {best['deviation_threshold']}%</span>
        <span class="badge badge-warning" style="margin-left:8px;">回正窗口: {best['window']}</span>
        <span class="badge badge-success" style="margin-left:8px;">标准: {best['criterion']}</span>
    </p>
    <p style="margin-top:8px;color:#8b949e;">
        样本: {best['total_underperform']}只
        (暗盘下跌{best.get('n_dark_down', 0)} + 涨幅不及预期{best.get('n_below_exp', 0)})
        | 修正成功: {best['corrected']}只 |
        修正率: <strong style="color:#ffaa00">{best['correction_rate']:.1f}%</strong> |
        修正组均收益: <span style="color:{color_for_return(best['avg_corrected_return'])}">{format_return(best['avg_corrected_return'])}</span>
    </p>
</div>
"""

    # 2. 热力图
    html += "<h2>🌡️ 偏差修正率热力图</h2>"
    html += '<div class="card">'
    html += svg_heatmap(result.get("heatmap", {}))
    html += "</div>"

    # 3. 因子重要性
    model = result.get("model")
    if model:
        html += "<h2>🧬 修正因子重要性</h2>"
        html += '<div class="card">'
        html += f'<p style="color:#8b949e;margin-bottom:10px;">Logistic回归 + 信息增益双轨法 | 训练样本: {model["n_samples"]}只 | 准确率: {model["accuracy"]:.1%} | AUC: {model["auc"]:.3f}</p>'

        importance = model.get("feature_importance", {})
        sorted_imp = sorted(importance.items(), key=lambda x: -x[1])
        bars = [{"label": name, "value": val * 100, "color": "#58a6ff"} for name, val in sorted_imp]
        html += svg_bar_chart(bars, title="因子综合重要性 (%)")
        html += "</div>"

    # 4. 价格路径聚类
    patterns = result.get("patterns", {})
    if patterns:
        html += "<h2>📈 价格路径模式</h2>"
        html += '<div class="grid">'
        for pid in sorted(patterns.keys()):
            p = patterns[pid]
            chars = p["characteristics"]
            html += f"""
<div class="card">
    <h3>{p['emoji']} {p['label']} (n={p['count']})</h3>
    <table>
        <tr><td>暗盘均涨幅</td><td style="color:{color_for_return(chars['avg_dark_return'])}">{format_return(chars['avg_dark_return'])}</td></tr>
        <tr><td>平均偏差</td><td style="color:{color_for_return(chars['avg_deviation'])}">{format_return(chars['avg_deviation'])}</td></tr>
        <tr><td>Day10均涨幅</td><td style="color:{color_for_return(chars['avg_day10_return'])}">{format_return(chars['avg_day10_return'])}</td></tr>
        <tr><td>修正率(路径回升)</td><td style="color:#ffaa00">{chars['correction_rate']:.0f}%</td></tr>
        <tr><td>暗盘下跌/涨幅不及预期</td><td>{chars['n_dark_down']} / {chars['n_below_exp']}</td></tr>
    </table>
</div>"""
        html += "</div>"

        html += '<div class="card">'
        chart_data = []
        for pid in sorted(patterns.keys()):
            p = patterns[pid]
            chart_data.append({
                "label": p["label"], "path": p["avg_path"],
                "color": p["color"], "stroke_width": 3, "opacity": 0.9,
            })
        html += svg_path_chart(chart_data, title="各模式平均路径对比")
        html += "</div>"

    # 5. 潜力释放分析 (新增)
    pr = result.get("potential_release", {})
    pr_cases = pr.get("cases", [])
    pr_summary = pr.get("summary", {})
    if pr_cases:
        html += "<h2>🚀 潜力释放分析</h2>"
        html += '<div class="card">'
        html += '<p style="color:#8b949e;margin-bottom:12px;">暗盘上涨但后续表现远超暗盘（Day5-Day10相对暗盘增幅>15pp）的股票</p>'

        if pr_summary:
            html += f"""<div class="grid" style="margin-bottom:16px;">
                <div class="stat-box"><div class="stat-value" style="color:#a371f7">{pr_summary['count']}</div><div class="stat-label">潜力释放案例</div></div>
                <div class="stat-box"><div class="stat-value positive">{format_return(pr_summary['avg_release_pp'])}</div><div class="stat-label">平均补涨幅度</div></div>
                <div class="stat-box"><div class="stat-value">{pr_summary.get('cornerstone_rate', 0):.0f}%</div><div class="stat-label">有基石比例</div></div>
            </div>"""

        html += '<table><tr><th>股票</th><th>暗盘</th><th>预期</th><th>偏差</th><th>Day5</th><th>Day10</th><th>补涨幅度</th><th>行业</th></tr>'
        for c in pr_cases[:10]:
            s = c["stock"]
            html += f"""<tr>
                <td><strong>{s['name']}</strong> ({s['code']})</td>
                <td style="color:{color_for_return(c['dark'])}">{format_return(c['dark'])}</td>
                <td>{format_return(c.get('expected_return'))}</td>
                <td style="color:{color_for_return(c.get('deviation'))}">{format_return(c.get('deviation'))}</td>
                <td style="color:{color_for_return(s.get('day5_return'))}">{format_return(s.get('day5_return'))}</td>
                <td style="color:{color_for_return(s.get('day10_return'))}">{format_return(s.get('day10_return'))}</td>
                <td style="color:#a371f7;font-weight:bold">{c['release_pp']:+.0f}pp</td>
                <td>{s.get('category','')}</td>
            </tr>"""
        html += "</table></div>"

        # 路径图
        html += '<div class="card">'
        chart_data = [{"label": c["stock"]["name"], "path": c["path"],
                       "color": "#a371f7", "opacity": 0.6, "stroke_width": 2}
                      for c in pr_cases[:5]]
        html += svg_path_chart(chart_data, title="Top 5 潜力释放案例路径")
        html += "</div>"

    # 6. 交叉维度
    html += "<h2>🔀 交叉维度修正分析</h2>"

    for section_title, cross_data in [
        ("偏差类型", result.get("cross_by_devtype", [])),
        ("超购区间", result.get("cross_by_sub", [])),
        ("基石投资者", result.get("cross_by_cs", [])),
        ("行业板块", result.get("cross_by_cat", [])),
        ("市场状态", result.get("cross_by_market", [])),
    ]:
        if not cross_data:
            continue
        html += f'<div class="card"><h3>{section_title} × 修正率</h3>'
        html += '<table><tr><th>维度</th><th>总数</th><th>不及预期</th><th>修正成功</th><th>修正率</th><th>平均偏差</th><th>修正均收益</th></tr>'
        for row in cross_data:
            rate_color = "#ff4444" if row["correction_rate"] >= 40 else "#ffaa00" if row["correction_rate"] >= 20 else "#3fb950"
            html += f"""<tr>
                <td><strong>{row['dim_label']}</strong></td>
                <td>{row['total']}</td>
                <td>{row['underperform']}</td>
                <td>{row['corrected']}</td>
                <td style="color:{rate_color};font-weight:bold">{row['correction_rate']:.0f}%</td>
                <td style="color:{color_for_return(row['avg_deviation'])}">{format_return(row['avg_deviation'])}</td>
                <td style="color:{color_for_return(row['avg_correction_return'])}">{format_return(row['avg_correction_return'])}</td>
            </tr>"""
        html += "</table></div>"

    # 7. Top修正案例
    top = result.get("top_corrections", [])
    if top:
        html += "<h2>🏆 Top 修正案例</h2>"
        html += '<div class="card">'
        html += '<table><tr><th>股票</th><th>类型</th><th>暗盘</th><th>预期</th><th>偏差</th><th>Day10</th><th>修正幅度</th><th>行业</th></tr>'
        for t in top:
            s = t["stock"]
            dt = t.get("deviation_type", "dark_down")
            html += f"""<tr>
                <td><strong>{s['name']}</strong> ({s['code']})</td>
                <td>{dev_type_badge(dt)}</td>
                <td style="color:{color_for_return(t['dark_return'])}">{format_return(t['dark_return'])}</td>
                <td>{format_return(t.get('expected_return'))}</td>
                <td style="color:{color_for_return(t.get('deviation'))}">{format_return(t.get('deviation'))}</td>
                <td style="color:{color_for_return(t['final_return'])}">{format_return(t['final_return'])}</td>
                <td style="color:#ff4444;font-weight:bold">{t['recovery']:+.1f}pp</td>
                <td>{s.get('category','')}</td>
            </tr>"""
        html += "</table></div>"

        html += '<div class="card">'
        chart_data = [{"label": t["stock"]["name"], "path": t["path"],
                       "color": "#ff4444", "opacity": 0.6, "stroke_width": 2}
                      for t in top[:5]]
        html += svg_path_chart(chart_data, title="Top 5 修正案例价格路径")
        html += "</div>"

    # 8. 阈值详情
    html += "<h2>📋 全部偏差阈值组合详情 (Top 20)</h2>"
    html += '<div class="card"><table>'
    html += '<tr><th>偏差阈值</th><th>窗口</th><th>标准</th><th>样本</th><th>暗盘跌/不及预期</th><th>修正</th><th>修正率</th><th>修正均收益</th><th>评分</th></tr>'
    for r in result.get("threshold_results", [])[:20]:
        html += f"""<tr>
            <td>≤{r['deviation_threshold']}%</td>
            <td>{r['window']}</td>
            <td>{r['criterion']}</td>
            <td>{r['total_underperform']}</td>
            <td>{r.get('n_dark_down',0)} / {r.get('n_below_exp',0)}</td>
            <td>{r['corrected']}</td>
            <td style="color:#ffaa00;font-weight:bold">{r['correction_rate']:.1f}%</td>
            <td style="color:{color_for_return(r['avg_corrected_return'])}">{format_return(r['avg_corrected_return'])}</td>
            <td>{r['score']:.2f}</td>
        </tr>"""
    html += "</table></div>"

    html += """
<div class="disclaimer">
⚠️ <strong>免责声明</strong>：本报告基于历史数据回测分析，不构成任何投资建议。港股新股交易风险极高，
暗盘交易更具不确定性。过往表现不代表未来收益。请在充分了解风险的情况下自行决策。
</div>

</div></body></html>"""

    return html


# ============================================
# 模式2: 单股修正回测报告
# ============================================

def generate_single_report(analysis):
    """生成单股修正分析报告"""
    target = analysis["target"]
    path = analysis["path"]
    dev = analysis.get("deviation")
    exp = analysis.get("expected_return")
    dev_type = analysis.get("deviation_type", "normal")

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>修正分析 — {target['name']} ({target['code']})</title>
{CSS}
</head>
<body>
<div class="container">

<h1>🔄 修正路径分析 — {target['name']}</h1>
<p class="subtitle">{target['code']} | 上市日期: {target['date']} | {target.get('category', '')} | {dev_type_badge(dev_type)}</p>

<div class="grid-5">
    <div class="stat-box">
        <div class="stat-value" style="color:{color_for_return(target.get('dark_return'))}">{format_return(target.get('dark_return'))}</div>
        <div class="stat-label">暗盘涨跌幅</div>
    </div>
    <div class="stat-box">
        <div class="stat-value" style="color:#8b949e">{format_return(exp)}</div>
        <div class="stat-label">预期涨幅</div>
    </div>
    <div class="stat-box">
        <div class="stat-value" style="color:{color_for_return(dev)}">{format_return(dev)}</div>
        <div class="stat-label">期望偏差</div>
    </div>
    <div class="stat-box">
        <div class="stat-value" style="color:{color_for_return(target.get('day1_return'))}">{format_return(target.get('day1_return'))}</div>
        <div class="stat-label">首日涨跌幅</div>
    </div>
    <div class="stat-box">
        <div class="stat-value" style="color:{color_for_return(target.get('day10_return'))}">{format_return(target.get('day10_return'))}</div>
        <div class="stat-label">Day10涨跌幅</div>
    </div>
</div>

<div class="card" style="margin-top:16px;">
    <span class="badge {'badge-success' if analysis['did_correct'] else 'badge-danger' if analysis['is_underperform'] else 'badge-info'}">
        {'✅ 修正成功' if analysis['did_correct'] else '❌ 未修正' if analysis['is_underperform'] else '➡️ 表现正常(偏差不大)'}
    </span>
    <span style="color:#8b949e;margin-left:12px;font-size:13px;">
        {analysis.get('deviation_type_label', '')}
    </span>
</div>
"""

    # 价格路径
    html += '<h2>📈 价格路径</h2><div class="card">'
    chart_data = [{"label": target["name"], "path": path, "color": "#58a6ff", "stroke_width": 3}]
    html += svg_path_chart(chart_data, title=f"{target['name']} 价格路径")
    html += "</div>"

    # 各时点数据
    html += '<h2>📊 各时点数据</h2><div class="card"><table>'
    html += '<tr><th>时点</th><th>涨跌幅</th><th>vs暗盘变化</th></tr>'
    dr = target.get("dark_return", 0) or 0
    for label, key in PATH_TIMEPOINTS:
        val = target.get(key)
        change = (val - dr) if val is not None and dr is not None else None
        html += f"""<tr>
            <td>{label}</td>
            <td style="color:{color_for_return(val)};font-weight:bold">{format_return(val)}</td>
            <td style="color:{color_for_return(change)}">{format_return(change) if change is not None else '-'}</td>
        </tr>"""
    html += "</table></div>"

    # 相似案例
    similar = analysis.get("similar_cases", [])
    if similar:
        html += "<h2>🔍 历史相似案例</h2><div class='card'>"
        html += '<table><tr><th>相似度</th><th>股票</th><th>暗盘</th><th>偏差</th><th>Day5</th><th>Day10</th><th>结局</th></tr>'
        for sim, d in similar[:8]:
            d5 = d.get("day5_return")
            d10 = d.get("day10_return")
            final = d10 if d10 is not None else d5
            did_corr = final is not None and final > 0
            html += f"""<tr>
                <td>{sim:.0%}</td>
                <td><strong>{d['name']}</strong> ({d['code']})</td>
                <td style="color:{color_for_return(d.get('dark_return'))}">{format_return(d.get('dark_return'))}</td>
                <td style="color:{color_for_return(d.get('deviation'))}">{format_return(d.get('deviation'))}</td>
                <td style="color:{color_for_return(d5)}">{format_return(d5)}</td>
                <td style="color:{color_for_return(d10)}">{format_return(d10)}</td>
                <td>{'<span class="badge badge-success">修正</span>' if did_corr else '<span class="badge badge-danger">未修正</span>'}</td>
            </tr>"""
        html += "</table></div>"

    html += """
<div class="disclaimer">
⚠️ 本报告基于历史数据回测，不构成投资建议。
</div>
</div></body></html>"""

    return html


# ============================================
# 模式3: 实时修正预测报告
# ============================================

def generate_predict_report(prediction):
    """生成修正预测HTML报告"""
    params = prediction.get("params", {})
    prob = prediction.get("probability")
    conf = prediction.get("confidence", 0)
    advice = prediction.get("advice", {})
    dev = params.get("deviation")
    exp = params.get("expected_return")
    dev_type = prediction.get("deviation_type", "normal")

    if prediction.get("not_applicable"):
        html = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8"><title>修正预测</title>{CSS}</head>
<body><div class="container">
<h1>🔄 修正预测 — {params.get('name', params.get('code', ''))}</h1>
<p class="subtitle">{params.get('code', '')} | 暗盘: {format_return(params.get('dark_return'))} | 预期: {format_return(exp)} | 偏差: {format_return(dev)}</p>
<div class="card">
    <h3>ℹ️ {prediction.get('reason', '表现符合预期')}</h3>
    <p style="color:#8b949e;margin-top:8px;">暗盘表现基本符合或超越预期，不属于偏差修正分析范畴。</p>
    <p style="margin-top:8px;">建议使用 <strong>hk-ipo-sweet-spot</strong> 分析最佳卖出时点。</p>
</div>
</div></body></html>"""
        return html

    prob_pct = prob * 100 if prob is not None else 0
    prob_color = "#ff4444" if prob_pct >= 60 else "#ffaa00" if prob_pct >= 40 else "#3fb950"
    risk_colors = {"低": "#3fb950", "中": "#ffaa00", "中高": "#ff8c00", "高": "#ff4444", "极高": "#ff0000"}

    # 区分标题
    is_dark_positive = params.get("dark_return", 0) >= 0
    title_verb = "修正" if is_dark_positive else "反转"

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>{title_verb}预测 — {params.get('name', params.get('code', ''))}</title>
{CSS}
</head>
<body>
<div class="container">

<h1>🎯 {title_verb}预测 — {params.get('name', params.get('code', ''))}</h1>
<p class="subtitle">
    {params.get('code', '')} |
    暗盘: {format_return(params.get('dark_return'))} |
    预期: {format_return(exp)} |
    偏差: {format_return(dev)} |
    {dev_type_badge(dev_type)} |
    超购: {params.get('subscription_mult', 0):.0f}倍
</p>

<!-- 核心预测卡片 -->
<div class="card" style="text-align:center;padding:30px;">
    <div style="font-size:48px;font-weight:bold;color:{prob_color}">{prob_pct:.0f}%</div>
    <div style="color:#8b949e;font-size:16px;margin:8px 0;">{title_verb}概率</div>
    <div class="progress-bar" style="max-width:400px;margin:12px auto;">
        <div class="progress-fill" style="width:{prob_pct:.0f}%;background:{prob_color};"></div>
    </div>
    <div style="font-size:24px;margin-top:12px;">{prediction.get('confidence_stars', '☆☆☆☆☆')}</div>
    <div style="color:#8b949e;font-size:13px;">信心等级</div>
</div>

<!-- 建议 -->
<div class="card" style="border-left:3px solid {risk_colors.get(advice.get('risk_level', '中'), '#ffaa00')};">
    <h3>💡 建议: {advice.get('action', '')}</h3>
    <p style="color:#8b949e;margin-top:8px;">{advice.get('reason', '')}</p>
    <div style="margin-top:12px;">
        <span class="badge" style="background:rgba(255,170,0,0.15);color:{risk_colors.get(advice.get('risk_level', '中'), '#ffaa00')}">
            风险等级: {advice.get('risk_level', '中')}
        </span>
    </div>
"""

    details = advice.get("detail", [])
    if isinstance(details, list) and details:
        html += '<ul style="margin-top:12px;color:#c9d1d9;padding-left:20px;">'
        for d in details:
            html += f"<li style='margin:4px 0'>{d}</li>"
        html += "</ul>"
    html += "</div>"

    # 因子诊断
    diagnostics = prediction.get("diagnostics", [])
    if diagnostics:
        html += "<h2>🧬 因子诊断</h2><div class='card'>"
        for diag in diagnostics:
            score = diag["score"]
            score_color = "#ff4444" if score > 0 else "#3fb950" if score < 0 else "#8b949e"
            html += f"""
<div class="factor-item">
    <div class="factor-emoji">{diag['emoji']}</div>
    <div class="factor-info">
        <div class="factor-name">{diag['factor']}: {diag['value']}</div>
        <div class="factor-detail">{diag['impact']}</div>
    </div>
    <div class="factor-score" style="color:{score_color}">{score:+d}</div>
</div>"""
        html += "</div>"

    # 预期收益
    expected = prediction.get("expected_returns", {})
    if expected:
        html += "<h2>📊 预期收益估算 (基于相似案例)</h2><div class='card'><table>"
        html += "<tr><th>时点</th><th>预期均值</th><th>95%置信区间</th></tr>"
        for tp, ci in expected.items():
            lo = ci.get("ci_lower", 0)
            hi = ci.get("ci_upper", 0)
            est = ci.get("estimate", 0)
            html += f"""<tr>
                <td>{tp}</td>
                <td style="color:{color_for_return(est)};font-weight:bold">{format_return(est)}</td>
                <td style="color:#8b949e">[{lo:+.1f}%, {hi:+.1f}%]</td>
            </tr>"""
        html += "</table></div>"

    # 相似案例
    similar = prediction.get("similar_cases", [])
    if similar:
        html += "<h2>🔍 历史相似案例</h2><div class='card'>"
        html += '<table><tr><th>相似度</th><th>股票</th><th>类型</th><th>暗盘</th><th>偏差</th><th>Day5</th><th>Day10</th><th>结局</th></tr>'
        for case in similar[:8]:
            s = case["stock"]
            corr = case.get("did_correct", False)
            html += f"""<tr>
                <td>{case['similarity']:.0%}</td>
                <td><strong>{s['name']}</strong></td>
                <td>{dev_type_badge(case.get('deviation_type', 'dark_down'))}</td>
                <td style="color:{color_for_return(s.get('dark_return'))}">{format_return(s.get('dark_return'))}</td>
                <td style="color:{color_for_return(s.get('deviation'))}">{format_return(s.get('deviation'))}</td>
                <td style="color:{color_for_return(s.get('day5_return'))}">{format_return(s.get('day5_return'))}</td>
                <td style="color:{color_for_return(s.get('day10_return'))}">{format_return(s.get('day10_return'))}</td>
                <td>{'<span class="badge badge-success">✅ 修正</span>' if corr else '<span class="badge badge-danger">❌ 未修正</span>'}</td>
            </tr>"""
        html += "</table></div>"

        html += '<div class="card">'
        chart_data = [{"label": c["stock"]["name"], "path": c["path"],
                       "color": "#3fb950" if c.get("did_correct") else "#ff4444",
                       "opacity": 0.5, "stroke_width": 1.5}
                      for c in similar[:6]]
        html += svg_path_chart(chart_data, title="相似案例价格路径")
        html += "</div>"

    # 模型信息
    mi = prediction.get("model_info")
    if mi:
        html += f"""<h2>🤖 模型信息</h2><div class="card">
        <table>
            <tr><td>训练样本</td><td>{mi.get('n_samples', 0)}只</td></tr>
            <tr><td>准确率</td><td>{mi.get('accuracy', 0):.1%}</td></tr>
            <tr><td>AUC</td><td>{mi.get('auc', 0.5):.3f}</td></tr>
        </table></div>"""

    html += """
<div class="disclaimer">
⚠️ <strong>免责声明</strong>：本预测基于历史数据统计模型，准确率有限，不构成任何投资建议。
港股暗盘交易风险极高，请在充分了解风险后自行决策。模型无法预测突发事件和市场极端情况。
</div>
</div></body></html>"""

    return html
