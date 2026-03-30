#!/usr/bin/env python3
"""港股打新甜蜜区间分析器 - HTML报告生成模块"""
import math
from engine import TIER_COLORS, get_tier

def get_color(value):
    if value > 0: return "#ff4444" if value > 20 else "#ff6666"
    elif value < 0: return "#00b050" if value < -20 else "#22aa66"
    return "#888888"

def wr_color(wr):
    if wr > 70: return "#ff4444"
    if wr > 50: return "#ffaa00"
    return "#00b050"

CSS = '''
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Microsoft YaHei', sans-serif;
       background: linear-gradient(135deg, #0a0a1a 0%, #1a1a2e 50%, #0a0a1a 100%);
       color: #e0e0e0; min-height: 100vh; padding: 20px; }
.container { max-width: 1400px; margin: 0 auto; }
.header { text-align: center; padding: 40px 20px;
           background: linear-gradient(135deg, rgba(255,68,68,0.1) 0%, rgba(255,140,0,0.1) 100%);
           border-radius: 20px; border: 1px solid rgba(255,68,68,0.2); margin-bottom: 30px; }
.header h1 { font-size: 2.2em; background: linear-gradient(90deg, #ff4444, #ff8c00, #ffaa00);
              -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 10px; }
.header .subtitle { color: #aaa; font-size: 1.1em; }
.header .meta { color: #888; font-size: 0.9em; margin-top: 10px; }
.insight-box { background: linear-gradient(135deg, rgba(255,68,68,0.15) 0%, rgba(255,140,0,0.08) 100%);
               border: 2px solid rgba(255,68,68,0.4); border-radius: 16px; padding: 30px; margin-bottom: 30px; }
.insight-box h2 { color: #ff8c00; font-size: 1.5em; margin-bottom: 15px; }
.insight-box .key-finding { font-size: 1.3em; color: #ffcc00; margin-bottom: 10px; line-height: 1.6; }
.insight-box p { line-height: 1.8; color: #ccc; }
.highlight { color: #ff4444; font-weight: bold; font-size: 1.1em; }
.good { color: #ffcc00; font-weight: bold; }
.warn { color: #00b050; font-weight: bold; }
.section { background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.1);
           border-radius: 16px; padding: 30px; margin-bottom: 25px; }
.section h2 { font-size: 1.4em; color: #ff8c00; margin-bottom: 20px; }
.section h3 { font-size: 1.1em; color: #ffaa00; margin: 20px 0 12px 0; }
.card-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 15px; }
.stat-card { background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1);
             border-radius: 12px; padding: 20px; text-align: center; }
.stat-card .label { color: #888; font-size: 0.85em; margin-bottom: 8px; }
.stat-card .value { font-size: 1.8em; font-weight: bold; }
.stat-card .sub { color: #888; font-size: 0.8em; margin-top: 5px; }
table { width: 100%; border-collapse: collapse; font-size: 0.9em; }
th { background: rgba(255,140,0,0.15); color: #ffaa00; padding: 12px 10px;
     text-align: center; font-weight: 600; border-bottom: 2px solid rgba(255,140,0,0.3); }
td { padding: 10px; text-align: center; border-bottom: 1px solid rgba(255,255,255,0.05); }
tr:hover { background: rgba(255,255,255,0.03); }
.best-row { background: rgba(255,140,0,0.08) !important; border-left: 3px solid #ff8c00; }
.badge { display: inline-block; padding: 4px 12px; border-radius: 20px; font-size: 0.85em; font-weight: bold; }
.badge-S { background: rgba(255,68,68,0.2); color: #ff4444; }
.badge-A { background: rgba(255,140,0,0.2); color: #ff8c00; }
.badge-B { background: rgba(255,170,0,0.2); color: #ffaa00; }
.badge-C { background: rgba(136,136,136,0.2); color: #888; }
.badge-D { background: rgba(0,176,80,0.2); color: #00b050; }
.conclusion { background: linear-gradient(135deg, rgba(255,204,0,0.08), rgba(255,140,0,0.05));
              border: 2px solid rgba(255,204,0,0.3); border-radius: 16px; padding: 30px; }
.conclusion h2 { color: #ffcc00; }
.conclusion ul { list-style: none; padding: 0; }
.conclusion li { padding: 8px 0; padding-left: 25px; position: relative; line-height: 1.8; }
.conclusion li:before { content: "\\1F4A1"; position: absolute; left: 0; }
.disclaimer { text-align: center; color: #666; font-size: 0.8em; margin-top: 30px; padding: 15px; border-top: 1px solid rgba(255,255,255,0.05); }
.scatter-svg { width: 100%; max-width: 1100px; margin: 0 auto; display: block; }
.legend { display: flex; gap: 20px; justify-content: center; flex-wrap: wrap; margin: 15px 0; }
.legend-item { display: flex; align-items: center; gap: 6px; font-size: 0.85em; color: #aaa; }
.legend-dot { width: 12px; height: 12px; border-radius: 50%; }
'''

CAT_COLORS = {
    "医药": "#ff6b6b", "AI": "#4ecdc4", "消费": "#ffe66d", "科技": "#a29bfe",
    "新能源": "#74b9ff", "制造": "#dfe6e9", "半导体": "#fd79a8", "机器人": "#00cec9",
    "汽车": "#6c5ce7", "资源": "#e17055", "医疗": "#fab1a0", "其他": "#636e72",
    "自动驾驶": "#81ecec", "材料": "#b2bec3", "金融": "#fdcb6e", "物流": "#55a3f7",
    "文旅": "#d4a574", "化工": "#c8d6e5", "服务": "#a3cb38", "农业": "#2ecc71",
}

def svg_scatter(data, sweet_spot_label=None):
    """生成超购倍数 vs 首日涨幅散点图 SVG"""
    sw, sh = 1100, 500
    pl, pr, pt, pb = 80, 40, 30, 60
    cw, ch = sw-pl-pr, sh-pt-pb
    x_min, x_max = 0, 4.2
    # 动态 Y 轴范围（留 10% 余量）
    all_returns = [d["day1_return"] for d in data]
    y_min = min(min(all_returns), -60)
    y_max = max(all_returns) * 1.1 + 20

    # 解析甜蜜区间标签得到超购范围（用于标注）
    sweet_low, sweet_high = 500, 2000  # 默认值
    if sweet_spot_label:
        # 从标签如 "500-2000倍(火爆)" 解析
        import re
        m = re.match(r'[<>]?\s*(\d+)[-~](\d+)', sweet_spot_label.replace(",",""))
        if m:
            sweet_low, sweet_high = int(m.group(1)), int(m.group(2))
    def tx(v): return pl + (v-x_min)/(x_max-x_min)*cw
    def ty(v): return pt + ch - (v-y_min)/(y_max-y_min)*ch

    s = f'<svg class="scatter-svg" viewBox="0 0 {sw} {sh}" xmlns="http://www.w3.org/2000/svg">\n'
    # 甜蜜区间
    sx1, sx2 = tx(math.log10(max(sweet_low, 1))), tx(math.log10(max(sweet_high, 2)))
    s += f'<rect x="{sx1}" y="{pt}" width="{sx2-sx1}" height="{ch}" fill="rgba(255,140,0,0.08)" stroke="rgba(255,140,0,0.3)" stroke-dasharray="5,5"/>\n'
    s += f'<text x="{(sx1+sx2)/2}" y="{pt+15}" fill="#ff8c00" font-size="12" text-anchor="middle" font-weight="bold">Sweet Spot {sweet_low}-{sweet_high}x</text>\n'
    # 零线
    zy = ty(0)
    s += f'<line x1="{pl}" y1="{zy}" x2="{sw-pr}" y2="{zy}" stroke="rgba(255,255,255,0.3)" stroke-width="1"/>\n'
    # 网格
    for yv in [-40, -20, 0, 50, 100, 150, 200, 250, 300, 350]:
        yy = ty(yv)
        if pt <= yy <= pt+ch:
            s += f'<line x1="{pl}" y1="{yy}" x2="{sw-pr}" y2="{yy}" stroke="rgba(255,255,255,0.05)"/>\n'
            s += f'<text x="{pl-10}" y="{yy+4}" fill="#888" font-size="11" text-anchor="end">{yv}%</text>\n'
    for xv in [1, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000]:
        xx = tx(math.log10(xv))
        if pl <= xx <= sw-pr:
            s += f'<line x1="{xx}" y1="{pt}" x2="{xx}" y2="{pt+ch}" stroke="rgba(255,255,255,0.05)"/>\n'
            lbl = f'{xv}x' if xv < 1000 else f'{xv//1000}kx'
            s += f'<text x="{xx}" y="{pt+ch+20}" fill="#888" font-size="11" text-anchor="middle">{lbl}</text>\n'
    s += f'<text x="{sw/2}" y="{sh-5}" fill="#aaa" font-size="13" text-anchor="middle">公开认购倍数（对数尺度）</text>\n'
    s += f'<text x="15" y="{sh/2}" fill="#aaa" font-size="13" text-anchor="middle" transform="rotate(-90,15,{sh/2})">首日涨跌幅 (%)</text>\n'
    # 散点
    for d in data:
        x = tx(math.log10(max(d["subscription_mult"], 1)))
        yv = min(max(d["day1_return"], y_min), y_max)
        y = ty(yv)
        c = CAT_COLORS.get(d["category"], "#888")
        r = 5 + min(d["fundraising"]/20, 8)
        s += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="{c}" opacity="0.8" stroke="rgba(255,255,255,0.3)" stroke-width="0.5">'
        s += f'<title>{d["name"]} ({d["code"]})&#10;超购: {d["subscription_mult"]:.0f}x&#10;首日: {d["day1_return"]:+.1f}%&#10;募资: {d["fundraising"]}亿</title></circle>\n'
    s += '</svg>\n'
    return s

def svg_timepoint_line(tp_stats):
    """卖出时点折线图"""
    w, h = 600, 300
    pl, pr, pt, pb = 60, 30, 30, 50
    cw, ch = w-pl-pr, h-pt-pb
    vals = [tp["avg"] for tp in tp_stats]
    wrs = [tp["win_rate"] for tp in tp_stats]
    if not vals: return ""
    y_min = min(min(vals), 0) - 10
    y_max = max(vals) + 20
    if y_max <= y_min: y_max = y_min + 50
    n = len(vals)

    s = f'<svg viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:600px;display:block;margin:20px auto;">\n'
    # 零线
    zy = pt + ch - (0-y_min)/(y_max-y_min)*ch
    s += f'<line x1="{pl}" y1="{zy}" x2="{w-pr}" y2="{zy}" stroke="rgba(255,255,255,0.2)"/>\n'

    points_avg = []
    points_wr = []
    for i in range(n):
        x = pl + (i/(n-1))*cw if n > 1 else pl + cw/2
        y = pt + ch - (vals[i]-y_min)/(y_max-y_min)*ch
        points_avg.append((x, y))
        # 胜率映射到同一坐标
        wr_y = pt + ch - (wrs[i]/100*(y_max-y_min)+y_min-y_min)/(y_max-y_min)*ch
        points_wr.append((x, min(max(wr_y, pt), pt+ch)))

    # 平均涨幅折线
    path = " ".join(f"{'M' if i==0 else 'L'}{p[0]:.1f},{p[1]:.1f}" for i, p in enumerate(points_avg))
    s += f'<path d="{path}" fill="none" stroke="#ff8c00" stroke-width="3"/>\n'
    for i, (x, y) in enumerate(points_avg):
        s += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="6" fill="#ff8c00" stroke="#fff" stroke-width="2"/>\n'
        s += f'<text x="{x:.1f}" y="{y-12:.1f}" fill="#ff8c00" font-size="12" text-anchor="middle" font-weight="bold">{vals[i]:+.1f}%</text>\n'

    # X轴标签
    labels = [tp["label"] for tp in tp_stats]
    for i, (x, _) in enumerate(points_avg):
        s += f'<text x="{x:.1f}" y="{h-10}" fill="#aaa" font-size="13" text-anchor="middle">{labels[i]}</text>\n'

    # 图例
    s += f'<circle cx="{pl+10}" cy="{pt+5}" r="5" fill="#ff8c00"/>'
    s += f'<text x="{pl+20}" y="{pt+9}" fill="#aaa" font-size="11">平均涨幅</text>\n'
    s += '</svg>\n'
    return s

def svg_bar_chart(labels, values, title="", w=700, h=300, color="#ff8c00"):
    """通用柱状图"""
    pl, pr, pt, pb = 60, 20, 40, 60
    cw, ch = w-pl-pr, h-pt-pb
    if not values: return ""
    v_max = max(max(values), 0.1)
    v_min = min(min(values), 0)
    span = v_max - v_min if v_max != v_min else 1
    n = len(values)
    bw = min(cw/(n*1.5), 60)
    gap = (cw - bw*n) / (n+1)

    s = f'<svg viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:{w}px;display:block;margin:15px auto;">\n'
    if title:
        s += f'<text x="{w/2}" y="20" fill="#ddd" font-size="14" text-anchor="middle" font-weight="bold">{title}</text>\n'
    # 零线
    zy = pt + ch - (0-v_min)/span*ch
    s += f'<line x1="{pl}" y1="{zy:.1f}" x2="{w-pr}" y2="{zy:.1f}" stroke="rgba(255,255,255,0.2)"/>\n'

    for i in range(n):
        x = pl + gap + i*(bw+gap)
        val = values[i]
        bar_h = abs(val)/span*ch
        if val >= 0:
            y = zy - bar_h
            c = "#ff4444" if val > 50 else "#ff8c00" if val > 20 else "#ffaa00" if val > 0 else "#888"
        else:
            y = zy
            c = "#00b050"
        s += f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{bar_h:.1f}" fill="{c}" rx="4" opacity="0.85"/>\n'
        s += f'<text x="{x+bw/2:.1f}" y="{(y-5 if val>=0 else y+bar_h+15):.1f}" fill="{c}" font-size="11" text-anchor="middle" font-weight="bold">{val:+.1f}%</text>\n'
        # 标签（支持换行）
        lbl_parts = labels[i].split("\n")
        for j, part in enumerate(lbl_parts):
            s += f'<text x="{x+bw/2:.1f}" y="{h-30+j*14:.1f}" fill="#aaa" font-size="10" text-anchor="middle">{part}</text>\n'
    s += '</svg>\n'
    return s

def svg_weight_donut(weights, extra):
    """因子权重环形图"""
    w, h = 400, 400
    cx, cy, r1, r2 = 200, 190, 120, 70
    labels = {"subscription": "超购倍数", "cornerstone": "基石投资者", "industry": "行业板块", "fundraising": "募资规模"}
    colors = {"subscription": "#ff4444", "cornerstone": "#ff8c00", "industry": "#4ecdc4", "fundraising": "#a29bfe"}

    s = f'<svg viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:400px;display:block;margin:15px auto;">\n'
    s += f'<text x="{cx}" y="25" fill="#ddd" font-size="14" text-anchor="middle" font-weight="bold">因子权重分布</text>\n'

    angle = -90  # 从顶部开始
    items = sorted(weights.items(), key=lambda x: -x[1])
    for name, wt in items:
        sweep = wt * 360
        a1 = math.radians(angle)
        a2 = math.radians(angle + sweep)
        x1o, y1o = cx + r1*math.cos(a1), cy + r1*math.sin(a1)
        x2o, y2o = cx + r1*math.cos(a2), cy + r1*math.sin(a2)
        x1i, y1i = cx + r2*math.cos(a2), cy + r2*math.sin(a2)
        x2i, y2i = cx + r2*math.cos(a1), cy + r2*math.sin(a1)
        large = 1 if sweep > 180 else 0
        c = colors.get(name, "#888")
        path = f"M{x1o:.1f},{y1o:.1f} A{r1},{r1} 0 {large},1 {x2o:.1f},{y2o:.1f} L{x1i:.1f},{y1i:.1f} A{r2},{r2} 0 {large},0 {x2i:.1f},{y2i:.1f} Z"
        s += f'<path d="{path}" fill="{c}" opacity="0.85" stroke="#1a1a2e" stroke-width="2"/>\n'
        # 标签
        mid_a = math.radians(angle + sweep/2)
        lx = cx + (r1+30)*math.cos(mid_a)
        ly = cy + (r1+30)*math.sin(mid_a)
        lbl = labels.get(name, name)
        s += f'<text x="{lx:.1f}" y="{ly:.1f}" fill="{c}" font-size="12" text-anchor="middle" font-weight="bold">{lbl}</text>\n'
        s += f'<text x="{lx:.1f}" y="{ly+14:.1f}" fill="#aaa" font-size="11" text-anchor="middle">{wt*100:.1f}%</text>\n'
        angle += sweep

    # 中心文字
    r2_val = extra.get("r2", 0) if extra else 0
    s += f'<text x="{cx}" y="{cy-5}" fill="#fff" font-size="16" text-anchor="middle" font-weight="bold">Ridge+IG</text>\n'
    s += f'<text x="{cx}" y="{cy+15}" fill="#aaa" font-size="11" text-anchor="middle">R²={r2_val:.3f}</text>\n'
    s += '</svg>\n'
    return s


def _svg_bootstrap_bars(bootstrap_ranges):
    """Bootstrap 置信区间可视化：期望收益 + 误差棒"""
    valid = [br for br in bootstrap_ranges if br.get("bootstrap") and br["bootstrap"].get("n", 0) >= 5]
    if not valid:
        return ""
    
    w, h = 800, 350
    pl, pr, pt, pb = 100, 30, 40, 80
    cw, ch = w - pl - pr, h - pt - pb
    n = len(valid)
    bw = min(cw / (n * 1.8), 80)
    gap = (cw - bw * n) / (n + 1)
    
    # 找Y轴范围
    all_lo = [br["bootstrap"]["exp_ci_lo"] for br in valid]
    all_hi = [br["bootstrap"]["exp_ci_hi"] for br in valid]
    y_min = min(min(all_lo), 0) - 10
    y_max = max(all_hi) + 20
    span = y_max - y_min if y_max != y_min else 1
    
    def ty(v):
        return pt + ch - (v - y_min) / span * ch
    
    s = f'<svg viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:800px;display:block;margin:20px auto;">\n'
    s += f'<text x="{w/2}" y="20" fill="#ddd" font-size="14" text-anchor="middle" font-weight="bold">各超购区间期望收益 (含90% Bootstrap CI)</text>\n'
    
    # 零线
    zy = ty(0)
    s += f'<line x1="{pl}" y1="{zy:.1f}" x2="{w-pr}" y2="{zy:.1f}" stroke="rgba(255,255,255,0.2)"/>\n'
    
    # Y轴网格
    for yv in range(-40, 200, 20):
        yy = ty(yv)
        if pt <= yy <= pt + ch:
            s += f'<line x1="{pl}" y1="{yy:.1f}" x2="{w-pr}" y2="{yy:.1f}" stroke="rgba(255,255,255,0.05)"/>\n'
            s += f'<text x="{pl-8}" y="{yy+4:.1f}" fill="#888" font-size="10" text-anchor="end">{yv}%</text>\n'
    
    for i, br in enumerate(valid):
        bs = br["bootstrap"]
        x = pl + gap + i * (bw + gap)
        xc = x + bw / 2
        
        val = bs["expected"]
        bar_h = abs(val) / span * ch
        c = "#ff4444" if val > 50 else "#ff8c00" if val > 20 else "#ffaa00" if val > 0 else "#00b050"
        
        if val >= 0:
            y = zy - bar_h
        else:
            y = zy
        
        # 柱子
        s += f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{bar_h:.1f}" fill="{c}" rx="4" opacity="0.7"/>\n'
        
        # 误差棒 (CI)
        ci_lo_y = ty(bs["exp_ci_lo"])
        ci_hi_y = ty(bs["exp_ci_hi"])
        s += f'<line x1="{xc:.1f}" y1="{ci_lo_y:.1f}" x2="{xc:.1f}" y2="{ci_hi_y:.1f}" stroke="#fff" stroke-width="2" opacity="0.7"/>\n'
        s += f'<line x1="{xc-6:.1f}" y1="{ci_lo_y:.1f}" x2="{xc+6:.1f}" y2="{ci_lo_y:.1f}" stroke="#fff" stroke-width="2" opacity="0.7"/>\n'
        s += f'<line x1="{xc-6:.1f}" y1="{ci_hi_y:.1f}" x2="{xc+6:.1f}" y2="{ci_hi_y:.1f}" stroke="#fff" stroke-width="2" opacity="0.7"/>\n'
        
        # 数值标签
        label_y = y - 8 if val >= 0 else y + bar_h + 15
        s += f'<text x="{xc:.1f}" y="{label_y:.1f}" fill="{c}" font-size="11" text-anchor="middle" font-weight="bold">{val:+.1f}%</text>\n'
        
        # X轴标签（多行）
        label = br["label"].replace("倍", "\n倍").split("(")[0].strip()
        parts = label.split("\n") if "\n" in label else [label]
        for j, part in enumerate(parts):
            s += f'<text x="{xc:.1f}" y="{h-40+j*14:.1f}" fill="#aaa" font-size="10" text-anchor="middle">{part}</text>\n'
    
    s += '</svg>\n'
    return s


def _svg_cv_trend(cv_res):
    """时序交叉验证走势图：训练R² vs Spearman ρ"""
    if not cv_res:
        return ""
    
    w, h = 600, 280
    pl, pr, pt, pb = 60, 60, 40, 50
    cw, ch = w - pl - pr, h - pt - pb
    n = len(cv_res)
    if n < 2:
        return ""
    
    # 双Y轴：左=R²，右=Spearman
    r2_vals = [f["train_r2"] for f in cv_res]
    sp_vals = [f["spearman"] for f in cv_res]
    
    r2_min, r2_max = min(min(r2_vals), 0), max(r2_vals) * 1.2 + 0.05
    sp_min = min(min(sp_vals), -0.1)
    sp_max = max(sp_vals) * 1.2 + 0.1
    
    def ty_r2(v):
        return pt + ch - (v - r2_min) / (r2_max - r2_min) * ch if r2_max > r2_min else pt + ch / 2
    
    def ty_sp(v):
        return pt + ch - (v - sp_min) / (sp_max - sp_min) * ch if sp_max > sp_min else pt + ch / 2
    
    s = f'<svg viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:600px;display:block;margin:20px auto;">\n'
    s += f'<text x="{w/2}" y="20" fill="#ddd" font-size="14" text-anchor="middle" font-weight="bold">模型稳定性趋势 (扩展窗口)</text>\n'
    
    # R² 折线（橙色）
    pts_r2 = []
    pts_sp = []
    for i in range(n):
        x = pl + (i / (n - 1)) * cw
        pts_r2.append((x, ty_r2(r2_vals[i])))
        pts_sp.append((x, ty_sp(sp_vals[i])))
    
    path_r2 = " ".join(f"{'M' if i == 0 else 'L'}{p[0]:.1f},{p[1]:.1f}" for i, p in enumerate(pts_r2))
    s += f'<path d="{path_r2}" fill="none" stroke="#ff8c00" stroke-width="2.5"/>\n'
    for i, (x, y) in enumerate(pts_r2):
        s += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="#ff8c00" stroke="#fff" stroke-width="1.5"/>\n'
        s += f'<text x="{x:.1f}" y="{y-10:.1f}" fill="#ff8c00" font-size="10" text-anchor="middle">{r2_vals[i]:.3f}</text>\n'
    
    # Spearman 折线（紫色）
    path_sp = " ".join(f"{'M' if i == 0 else 'L'}{p[0]:.1f},{p[1]:.1f}" for i, p in enumerate(pts_sp))
    s += f'<path d="{path_sp}" fill="none" stroke="#a29bfe" stroke-width="2.5" stroke-dasharray="6,3"/>\n'
    for i, (x, y) in enumerate(pts_sp):
        s += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="#a29bfe" stroke="#fff" stroke-width="1.5"/>\n'
        s += f'<text x="{x:.1f}" y="{y+18:.1f}" fill="#a29bfe" font-size="10" text-anchor="middle">{sp_vals[i]:.3f}</text>\n'
    
    # X轴标签
    for i in range(n):
        x = pl + (i / (n - 1)) * cw
        s += f'<text x="{x:.1f}" y="{h-10}" fill="#aaa" font-size="11" text-anchor="middle">Fold {cv_res[i]["fold"]}</text>\n'
    
    # Y轴标签
    s += f'<text x="15" y="{(pt+pt+ch)/2}" fill="#ff8c00" font-size="11" text-anchor="middle" transform="rotate(-90,15,{(pt+pt+ch)/2})">训练 R²</text>\n'
    s += f'<text x="{w-15}" y="{(pt+pt+ch)/2}" fill="#a29bfe" font-size="11" text-anchor="middle" transform="rotate(90,{w-15},{(pt+pt+ch)/2})">Spearman ρ</text>\n'
    
    # 图例
    s += f'<line x1="{pl}" y1="{pt-5}" x2="{pl+20}" y2="{pt-5}" stroke="#ff8c00" stroke-width="2.5"/>\n'
    s += f'<text x="{pl+25}" y="{pt-1}" fill="#ff8c00" font-size="10">训练R²</text>\n'
    s += f'<line x1="{pl+80}" y1="{pt-5}" x2="{pl+100}" y2="{pt-5}" stroke="#a29bfe" stroke-width="2.5" stroke-dasharray="6,3"/>\n'
    s += f'<text x="{pl+105}" y="{pt-1}" fill="#a29bfe" font-size="10">OOS Spearman ρ</text>\n'
    
    s += '</svg>\n'
    return s

def generate_full_report(data, range_res, cs_res, cat_res, fund_res,
                         weights, extra, tier_res, tp_res,
                         tp_by_sub, tp_by_cat, tp_by_fund,
                         quarter_res, month_res,
                         cond_result=None, ms_res=None,
                         sweet_spot_label=None,
                         cv_res=None, tier_sell_res=None,
                         bootstrap_ranges=None,
                         effect_18c=None):
    """生成全量回测 HTML 报告"""
    n = len(data)
    all_returns = sorted([d["day1_return"] for d in data])
    med_ret = all_returns[n//2] if n % 2 == 1 else (all_returns[n//2-1]+all_returns[n//2])/2
    overall_wr = sum(1 for d in data if d["day1_return"] > 0) / n * 100

    # 找甜蜜区间（动态）
    if sweet_spot_label:
        sweet = next((r for r in range_res if sweet_spot_label.split("(")[0].strip() in r.get("label","")), {})
    else:
        sweet = max((r for r in range_res if r["count"] >= 5), key=lambda x: x.get("expected", 0), default={})
        sweet_spot_label = sweet.get("label", "N/A")

    # 动态日期范围
    dates = sorted(d["date"] for d in data)
    date_start = dates[0][:7].replace("-", ".") if dates else "N/A"
    date_end = dates[-1][:7].replace("-", ".") if dates else "N/A"

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>港股打新"甜蜜区间"回测分析 V3</title><style>{CSS}</style></head>
<body><div class="container">

<div class="header">
<h1>🎯 港股打新"甜蜜区间"回测分析</h1>
<div class="subtitle">多因子评分 · 条件子模型 · 卖出时点优化 · 季节性规律 · 数据驱动的打新策略</div>
<div class="meta">V3 条件子模型版 | 数据期间：{date_start} ~ {date_end} | 样本量：{n}只新股 | 含暗盘/3天/5天数据</div>
</div>

<!-- 核心发现 -->
<div class="insight-box">
<h2>🔑 核心发现</h2>
<div class="key-finding">超购倍数的"甜蜜区间"是 <span class="highlight">{sweet_spot_label.split("(")[0].strip()}</span>，综合期望收益率最高</div>
<p>
通过对{n}只港股新股的多维度回测分析：<br>
• 超购 <span class="warn">&lt;20倍</span> 的冷门股破发率高，胜率仅 <b>{next((r for r in range_res if "< 20" in r.get("label","")), {}).get("win_rate",0):.0f}%</b><br>
• <span class="good">500-2000倍</span> 火爆区间：胜率 <b>{sweet.get("win_rate",0):.0f}%</b>，期望收益 <b>{sweet.get("expected",0):+.1f}%</b><br>
• 有基石投资者胜率 <b>{cs_res["with"]["win_rate"]:.0f}%</b> vs 无基石 <b>{cs_res["without"]["win_rate"]:.0f}%</b><br>
• 多因子模型 Ridge R²={extra.get("r2",0):.3f}（OLS R²={extra.get("r2_ols",0):.3f}），λ={extra.get("lambda",0):.1f}，时间衰减半衰期={extra.get("time_decay_half_life",12)}月
</p></div>

<!-- 概览卡片 -->
<div class="section">
<h2>📊 整体概览</h2>
<div class="card-grid">
<div class="stat-card"><div class="label">样本新股数</div><div class="value" style="color:#ff8c00">{n}</div><div class="sub">{date_start} ~ {date_end}</div></div>
<div class="stat-card"><div class="label">整体胜率</div><div class="value" style="color:#ff4444">{overall_wr:.1f}%</div><div class="sub">首日收涨占比</div></div>
<div class="stat-card"><div class="label">平均首日涨幅</div><div class="value" style="color:#ff4444">{sum(d["day1_return"] for d in data)/n:.1f}%</div><div class="sub">含破发股</div></div>
<div class="stat-card"><div class="label">中位首日涨幅</div><div class="value" style="color:#ff8c00">{med_ret:.1f}%</div><div class="sub">更具代表性</div></div>
<div class="stat-card"><div class="label">最大涨幅</div><div class="value" style="color:#ff4444">{max(d["day1_return"] for d in data):.0f}%</div><div class="sub">{max(data, key=lambda x: x["day1_return"])["name"]}</div></div>
<div class="stat-card"><div class="label">最大跌幅</div><div class="value" style="color:#00b050">{min(d["day1_return"] for d in data):.0f}%</div><div class="sub">{min(data, key=lambda x: x["day1_return"])["name"]}</div></div>
</div></div>

<!-- 超购区间分析 -->
<div class="section">
<h2>📈 超购倍数区间 vs 首日表现</h2>
<div style="overflow-x:auto;"><table><thead><tr>
<th>超购区间</th><th>样本</th><th>胜率</th><th>平均涨幅</th><th>中位涨幅</th><th>期望收益</th><th>最大涨</th><th>最大跌</th><th>基石率</th><th>评级</th>
</tr></thead><tbody>'''

    for r in range_res:
        if r["count"] == 0: continue
        is_sweet = "500-2000" in r.get("label","")
        rc = "best-row" if is_sweet else ""
        if r.get("expected",0) > 40 and r.get("win_rate",0) > 75:
            badge = '<span class="badge badge-S">⭐ 甜蜜区间</span>'
        elif r.get("expected",0) > 20 and r.get("win_rate",0) > 60:
            badge = '<span class="badge badge-A">🔥 较优</span>'
        elif r.get("win_rate",0) > 50:
            badge = '<span class="badge badge-B">⚡ 高波动</span>'
        else:
            badge = '<span class="badge badge-D">⚠️ 谨慎</span>'
        html += f'<tr class="{rc}"><td><b>{r["label"]}</b></td><td>{r["count"]}</td>'
        html += f'<td style="color:{wr_color(r["win_rate"])}">{r["win_rate"]:.0f}%</td>'
        html += f'<td style="color:{get_color(r["avg"])}">{r["avg"]:+.1f}%</td>'
        html += f'<td style="color:{get_color(r["median"])}">{r["median"]:+.1f}%</td>'
        html += f'<td style="color:{get_color(r["expected"])};font-weight:bold">{r["expected"]:+.1f}%</td>'
        html += f'<td style="color:#ff4444">{r["max"]:+.1f}%</td>'
        html += f'<td style="color:#00b050">{r["min"]:+.1f}%</td>'
        html += f'<td>{r["cornerstone_rate"]:.0f}%</td><td>{badge}</td></tr>\n'

    html += '</tbody></table></div></div>\n'

    # 散点图
    html += f'<div class="section"><h2>🔬 散点图：超购倍数 vs 首日涨幅</h2>\n'
    html += '<p style="color:#888;margin-bottom:10px;">每个点代表一只新股，X轴对数尺度。注意"甜蜜区间"（橙色带）</p>\n'
    html += svg_scatter(data, sweet_spot_label=sweet_spot_label)
    html += '<div class="legend">'
    for cat in sorted(CAT_COLORS.keys(), key=lambda c: -len([d for d in data if d["category"]==c])):
        cnt = len([d for d in data if d["category"]==cat])
        if cnt > 0:
            html += f'<div class="legend-item"><div class="legend-dot" style="background:{CAT_COLORS[cat]}"></div>{cat}({cnt})</div>'
    html += '</div></div>\n'

    # ============ 多因子评分 ============
    html += '<div class="section"><h2>🧠 多因子智能评分模型</h2>\n'
    html += '<p style="color:#888;margin-bottom:15px;">基于线性回归 + 信息增益双轨法自动计算因子权重</p>\n'
    html += '<div style="display:flex;flex-wrap:wrap;gap:20px;align-items:start;justify-content:center;">\n'
    html += svg_weight_donut(weights, extra)

    # 因子重要性表
    html += '<div style="flex:1;min-width:300px;"><table><thead><tr><th>因子</th><th>回归权重</th><th>信息增益</th><th>最终权重</th></tr></thead><tbody>'
    labels_map = {"subscription": "超购倍数", "cornerstone": "基石投资者", "industry": "行业板块", "fundraising": "募资规模"}
    reg_w = extra.get("reg_weights", {})
    ig_w = extra.get("ig_weights", {})
    for name in ["subscription", "cornerstone", "industry", "fundraising"]:
        html += f'<tr><td><b>{labels_map[name]}</b></td>'
        html += f'<td>{reg_w.get(name,0)*100:.1f}%</td>'
        html += f'<td>{ig_w.get(name,0)*100:.1f}%</td>'
        html += f'<td style="color:#ff8c00;font-weight:bold">{weights.get(name,0)*100:.1f}%</td></tr>\n'
    html += '</tbody></table></div></div>\n'

    # 评分档位统计
    html += '<h3>评分档位 vs 实际表现</h3>'
    html += '<table><thead><tr><th>档位</th><th>评分范围</th><th>样本</th><th>平均涨幅</th><th>中位涨幅</th><th>胜率</th><th>期望收益</th></tr></thead><tbody>'
    tier_ranges = {"S": "80-100", "A": "60-80", "B": "40-60", "C": "20-40", "D": "0-20"}
    for t in tier_res:
        if t["count"] == 0: continue
        tc = TIER_COLORS.get(t["tier"], "#888")
        html += f'<tr><td><span class="badge badge-{t["tier"]}">{t["tier"]}档</span></td>'
        html += f'<td>{tier_ranges[t["tier"]]}</td><td>{t["count"]}</td>'
        html += f'<td style="color:{get_color(t["avg"])}">{t["avg"]:+.1f}%</td>'
        html += f'<td style="color:{get_color(t["median"])}">{t["median"]:+.1f}%</td>'
        html += f'<td style="color:{wr_color(t["win_rate"])}">{t["win_rate"]:.0f}%</td>'
        html += f'<td style="color:{get_color(t["expected"])};font-weight:bold">{t["expected"]:+.1f}%</td></tr>\n'
    html += '</tbody></table></div>\n'

    # ============ 基石 + 行业 + 募资 ============
    html += f'''<div class="section"><h2>🏛️ 基石投资者效应</h2>
<div class="card-grid" style="grid-template-columns:1fr 1fr;">
<div class="stat-card" style="border-color:rgba(255,140,0,0.3);">
<div class="label">✅ 有基石 ({cs_res["with"]["count"]}只)</div>
<div class="value" style="color:#ff4444">{cs_res["with"]["avg_return"]:.1f}%</div>
<div class="sub">胜率 {cs_res["with"]["win_rate"]:.0f}% | 中位 {cs_res["with"]["median_return"]:.1f}%</div></div>
<div class="stat-card" style="border-color:rgba(0,176,80,0.3);">
<div class="label">❌ 无基石 ({cs_res["without"]["count"]}只)</div>
<div class="value" style="color:{get_color(cs_res["without"]["avg_return"])}">{cs_res["without"]["avg_return"]:.1f}%</div>
<div class="sub">胜率 {cs_res["without"]["win_rate"]:.0f}% | 中位 {cs_res["without"]["median_return"]:.1f}%</div></div>
</div></div>\n'''

    # 行业表
    html += '<div class="section"><h2>🏭 行业板块表现</h2><table><thead><tr><th>行业</th><th>样本</th><th>平均涨幅</th><th>胜率</th></tr></thead><tbody>'
    for c in sorted(cat_res, key=lambda x: -x["avg_return"]):
        if c["count"] >= 2:
            html += f'<tr><td><b>{c["category"]}</b></td><td>{c["count"]}</td>'
            html += f'<td style="color:{get_color(c["avg_return"])}">{c["avg_return"]:+.1f}%</td>'
            html += f'<td style="color:{wr_color(c["win_rate"])}">{c["win_rate"]:.0f}%</td></tr>\n'
    html += '</tbody></table></div>\n'

    # 募资规模
    html += '<div class="section"><h2>💰 募资规模 vs 首日表现</h2><table><thead><tr><th>规模</th><th>样本</th><th>平均涨幅</th><th>胜率</th></tr></thead><tbody>'
    for f in fund_res:
        html += f'<tr><td><b>{f["label"]}</b></td><td>{f["count"]}</td>'
        html += f'<td style="color:{get_color(f["avg_return"])}">{f["avg_return"]:+.1f}%</td>'
        html += f'<td style="color:{wr_color(f["win_rate"])}">{f["win_rate"]:.0f}%</td></tr>\n'
    html += '</tbody></table></div>\n'

    # ============ 卖出时点分析 ============
    html += '<div class="section"><h2>⏱️ 全链条卖出时点分析</h2>\n'
    html += '<p style="color:#888;margin-bottom:15px;">对比暗盘、首日、第3天、第5天四个卖出时点的收益表现</p>\n'

    # 整体对比表
    html += '<table><thead><tr><th>卖出时点</th><th>有效样本</th><th>平均涨幅</th><th>中位涨幅</th><th>胜率</th><th>期望收益</th></tr></thead><tbody>'
    for tp in tp_res:
        html += f'<tr><td><b>{tp["label"]}</b></td><td>{tp["count"]}</td>'
        html += f'<td style="color:{get_color(tp["avg"])}">{tp["avg"]:+.1f}%</td>'
        html += f'<td style="color:{get_color(tp["median"])}">{tp["median"]:+.1f}%</td>'
        html += f'<td style="color:{wr_color(tp["win_rate"])}">{tp["win_rate"]:.0f}%</td>'
        html += f'<td style="color:{get_color(tp["expected"])};font-weight:bold">{tp["expected"]:+.1f}%</td></tr>\n'
    html += '</tbody></table>\n'
    html += svg_timepoint_line(tp_res)

    # 按超购区间交叉分析
    html += '<h3>按超购区间的最优卖出时点</h3>'
    html += '<table><thead><tr><th>超购区间</th><th>样本</th><th>暗盘期望</th><th>首日期望</th><th>3天期望</th><th>5天期望</th><th>最优时点</th></tr></thead><tbody>'
    for row in tp_by_sub:
        tps = {tp["label"]: tp for tp in row["timepoints"]}
        html += f'<tr><td><b>{row["dim_label"]}</b></td><td>{row["count"]}</td>'
        for lbl in ["暗盘", "首日", "第3天", "第5天"]:
            tp = tps.get(lbl, {})
            v = tp.get("expected", 0)
            is_best = lbl == row["best_timepoint"]
            style = f'color:{get_color(v)};{"font-weight:bold;text-decoration:underline;" if is_best else ""}'
            html += f'<td style="{style}">{v:+.1f}%</td>'
        html += f'<td style="color:#ffcc00;font-weight:bold">{row["best_timepoint"]}</td></tr>\n'
    html += '</tbody></table>\n'

    # 按行业交叉分析
    html += '<h3>按行业的最优卖出时点</h3>'
    html += '<table><thead><tr><th>行业</th><th>样本</th><th>暗盘</th><th>首日</th><th>3天</th><th>5天</th><th>建议</th></tr></thead><tbody>'
    for row in sorted(tp_by_cat, key=lambda x: -x["count"]):
        if row["count"] < 2: continue
        tps = {tp["label"]: tp for tp in row["timepoints"]}
        html += f'<tr><td><b>{row["dim_label"]}</b></td><td>{row["count"]}</td>'
        for lbl in ["暗盘", "首日", "第3天", "第5天"]:
            tp = tps.get(lbl, {})
            v = tp.get("expected", 0)
            is_best = lbl == row["best_timepoint"]
            style = f'color:{get_color(v)};{"font-weight:bold;" if is_best else ""}'
            html += f'<td style="{style}">{v:+.1f}%</td>'
        html += f'<td style="color:#ffcc00">{row["best_timepoint"]}</td></tr>\n'
    html += '</tbody></table></div>\n'

    # ============ 季节性分析 ============
    html += '<div class="section"><h2>📅 季节性分析</h2>\n'
    html += '<h3>按季度统计</h3>'
    q_labels = [q["quarter"] for q in quarter_res]
    q_avgs = [q["avg"] for q in quarter_res]
    html += svg_bar_chart(q_labels, q_avgs, "各季度平均首日涨幅")
    html += '<table><thead><tr><th>季度</th><th>样本</th><th>平均涨幅</th><th>中位涨幅</th><th>胜率</th></tr></thead><tbody>'
    for q in quarter_res:
        html += f'<tr><td><b>{q["quarter"]}</b></td><td>{q["count"]}</td>'
        html += f'<td style="color:{get_color(q["avg"])}">{q["avg"]:+.1f}%</td>'
        html += f'<td style="color:{get_color(q["median"])}">{q["median"]:+.1f}%</td>'
        html += f'<td style="color:{wr_color(q["win_rate"])}">{q["win_rate"]:.0f}%</td></tr>\n'
    html += '</tbody></table>\n'

    html += '<h3>按月份统计</h3>'
    m_labels = [m["month_label"] for m in month_res]
    m_avgs = [m["avg"] for m in month_res]
    html += svg_bar_chart(m_labels, m_avgs, "各月份平均首日涨幅", w=800)
    html += '</div>\n'

    # ============ V3.3 新增：Bootstrap 置信区间 ============
    if bootstrap_ranges:
        html += '<div class="section" style="border-color:rgba(78,205,196,0.3);">\n'
        html += '<h2>📊 Bootstrap 置信区间 (90%)</h2>\n'
        html += '<p style="color:#888;margin-bottom:15px;">通过1000次有放回重采样估计各区间期望收益的不确定性范围。区间越窄说明估计越可靠。</p>\n'
        
        html += '<table><thead><tr>'
        html += '<th>超购区间</th><th>样本</th><th>期望收益</th><th>90% CI 下界</th><th>90% CI 上界</th><th>CI 宽度</th><th>胜率</th><th>胜率 CI</th>'
        html += '</tr></thead><tbody>\n'
        
        for br in bootstrap_ranges:
            bs = br.get("bootstrap")
            if not bs or bs.get("n", 0) < 5:
                html += f'<tr><td><b>{br["label"]}</b></td><td colspan="7" style="color:#666;">样本不足</td></tr>\n'
                continue
            ci_width = bs["exp_ci_hi"] - bs["exp_ci_lo"]
            reliability = "🟢" if ci_width < 30 else "🟡" if ci_width < 60 else "🔴"
            html += f'<tr><td><b>{br["label"]}</b></td>'
            html += f'<td>{bs["n"]}</td>'
            html += f'<td style="color:{get_color(bs["expected"])};font-weight:bold">{bs["expected"]:+.1f}%</td>'
            html += f'<td style="color:{get_color(bs["exp_ci_lo"])}">{bs["exp_ci_lo"]:+.1f}%</td>'
            html += f'<td style="color:{get_color(bs["exp_ci_hi"])}">{bs["exp_ci_hi"]:+.1f}%</td>'
            html += f'<td>{reliability} {ci_width:.1f}pp</td>'
            html += f'<td style="color:{wr_color(bs["win_rate"])}">{bs["win_rate"]:.0f}%</td>'
            html += f'<td>{bs["wr_ci_lo"]:.0f}%~{bs["wr_ci_hi"]:.0f}%</td></tr>\n'
        
        html += '</tbody></table>\n'
        
        # Bootstrap 可视化：期望收益 + CI 柱状图
        html += _svg_bootstrap_bars(bootstrap_ranges)
        
        html += '</div>\n'

    # ============ V3.3 新增：时序交叉验证 ============
    if cv_res:
        html += '<div class="section" style="border-color:rgba(162,155,254,0.3);">\n'
        html += '<h2>📐 时序交叉验证 (Expanding Window)</h2>\n'
        html += '<p style="color:#888;margin-bottom:15px;">严格按时间顺序切分训练/测试集，验证模型在未来数据上的预测能力。Spearman 秩相关衡量评分排序与实际涨幅排序的一致性。</p>\n'
        
        html += '<table><thead><tr>'
        html += '<th>折</th><th>训练期</th><th>训练样本</th><th>测试期</th><th>测试样本</th>'
        html += '<th>训练 R²</th><th>Spearman ρ</th><th>档位准确率</th>'
        html += '</tr></thead><tbody>\n'
        
        for fold in cv_res:
            sp_color = "#ff4444" if fold["spearman"] > 0.3 else "#ffaa00" if fold["spearman"] > 0.1 else "#00b050"
            ta_color = "#ff4444" if fold["tier_accuracy"] > 50 else "#ffaa00" if fold["tier_accuracy"] > 30 else "#888"
            html += f'<tr>'
            html += f'<td><b>Fold {fold["fold"]}</b></td>'
            html += f'<td>{fold["train_period"]}</td><td>{fold["train_n"]}</td>'
            html += f'<td>{fold["test_period"]}</td><td>{fold["test_n"]}</td>'
            html += f'<td>{fold["train_r2"]:.3f}</td>'
            html += f'<td style="color:{sp_color};font-weight:bold">{fold["spearman"]:.3f}</td>'
            html += f'<td style="color:{ta_color}">{fold["tier_accuracy"]:.0f}%</td>'
            html += '</tr>\n'
        
        # 平均值
        avg_sp = sum(f["spearman"] for f in cv_res) / len(cv_res)
        avg_ta = sum(f["tier_accuracy"] for f in cv_res) / len(cv_res)
        avg_r2 = sum(f["train_r2"] for f in cv_res) / len(cv_res)
        html += f'<tr style="border-top:2px solid rgba(255,140,0,0.3);font-weight:bold;">'
        html += f'<td colspan="2">平均</td><td>-</td><td>-</td><td>-</td>'
        html += f'<td>{avg_r2:.3f}</td>'
        html += f'<td style="color:#ff8c00">{avg_sp:.3f}</td>'
        html += f'<td style="color:#ff8c00">{avg_ta:.0f}%</td></tr>\n'
        
        html += '</tbody></table>\n'
        
        # CV 走势图
        html += _svg_cv_trend(cv_res)
        
        # 解读
        html += '<div style="background:rgba(162,155,254,0.08);border:1px solid rgba(162,155,254,0.2);border-radius:12px;padding:15px;margin-top:15px;">\n'
        html += '<h3 style="color:#a29bfe;margin-top:0;">💡 交叉验证解读</h3>\n'
        if avg_sp > 0.3:
            html += f'<p>平均 Spearman ρ = {avg_sp:.3f}，<span style="color:#ff4444;font-weight:bold">模型排序预测能力较强</span>，评分高的股票确实倾向于涨幅更大。</p>\n'
        elif avg_sp > 0.1:
            html += f'<p>平均 Spearman ρ = {avg_sp:.3f}，<span style="color:#ffaa00;font-weight:bold">模型有一定预测能力</span>，但存在噪声。建议结合其他因素综合判断。</p>\n'
        else:
            html += f'<p>平均 Spearman ρ = {avg_sp:.3f}，<span style="color:#888;">模型排序预测能力有限</span>。市场随机性较大，评分仅供参考。</p>\n'
        html += '</div>\n'
        html += '</div>\n'

    # ============ V3.3 新增：分档位卖出策略 ============
    if tier_sell_res:
        html += '<div class="section" style="border-color:rgba(255,204,0,0.3);">\n'
        html += '<h2>🎯 分档位卖出策略矩阵</h2>\n'
        html += '<p style="color:#888;margin-bottom:15px;">每个评分档位的最优卖出时点、期望收益和策略建议。含 Bootstrap 90% 置信区间。</p>\n'
        
        # 策略卡片
        html += '<div class="card-grid" style="grid-template-columns:repeat(auto-fit, minmax(250px, 1fr));">\n'
        for ts in tier_sell_res:
            if ts["count"] == 0:
                continue
            tc = TIER_COLORS.get(ts["tier"], "#888")
            html += f'<div class="stat-card" style="border-color:{tc}40;text-align:left;">\n'
            html += f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">'
            html += f'<span class="badge badge-{ts["tier"]}" style="font-size:1.1em;">{ts["tier"]}档</span>'
            html += f'<span style="color:#888;">{ts["count"]}只</span></div>\n'
            html += f'<div style="font-size:1.3em;color:#ffcc00;font-weight:bold;margin-bottom:5px;">推荐：{ts["best_tp"]}</div>\n'
            html += f'<div style="font-size:1.1em;color:{get_color(ts["best_expected"])};">期望 {ts["best_expected"]:+.1f}%</div>\n'
            
            if ts.get("bootstrap"):
                bs = ts["bootstrap"]
                html += f'<div style="color:#888;font-size:0.85em;">90%CI: {bs["exp_ci_lo"]:+.1f}% ~ {bs["exp_ci_hi"]:+.1f}%</div>\n'
            
            html += f'<div style="margin-top:10px;font-size:0.85em;color:#ccc;line-height:1.6;">{ts["strategy"]}</div>\n'
            html += '</div>\n'
        html += '</div>\n'
        
        # 详细对比表
        html += '<h3>各档位各时点期望收益对比</h3>\n'
        html += '<table><thead><tr><th>档位</th><th>样本</th><th>暗盘</th><th>首日</th><th>第3天</th><th>第5天</th><th>最优</th><th>持有溢价(D1→D5)</th></tr></thead><tbody>\n'
        for ts in tier_sell_res:
            if ts["count"] == 0:
                continue
            tc = TIER_COLORS.get(ts["tier"], "#888")
            tp_map = {tp["label"]: tp for tp in ts["tp_stats"]}
            html += f'<tr><td><span class="badge badge-{ts["tier"]}">{ts["tier"]}档</span></td>'
            html += f'<td>{ts["count"]}</td>'
            for lbl in ["暗盘", "首日", "第3天", "第5天"]:
                tp = tp_map.get(lbl, {})
                v = tp.get("expected", 0)
                is_best = lbl == ts["best_tp"]
                style = f'color:{get_color(v)};{"font-weight:bold;text-decoration:underline;" if is_best else ""}'
                html += f'<td style="{style}">{v:+.1f}%</td>'
            html += f'<td style="color:#ffcc00;font-weight:bold">{ts["best_tp"]}</td>'
            hp = ts.get("hold_premium", {}).get("d1_to_d5")
            if hp is not None:
                html += f'<td style="color:{get_color(hp)}">{hp:+.1f}%</td>'
            else:
                html += '<td>-</td>'
            html += '</tr>\n'
        html += '</tbody></table>\n'
        html += '</div>\n'

    # ============ 市场状态条件子模型 ============
    if cond_result and ms_res:
        state_colors = {"BULL": "#ff4444", "BEAR": "#00b050", "NEUTRAL": "#ffaa00"}
        state_labels = {"BULL": "🐂 牛市", "BEAR": "🐻 熊市", "NEUTRAL": "⚖️ 震荡"}
        
        html += '<div class="section" style="border-color:rgba(255,204,0,0.3);">\n'
        html += '<h2>🧬 市场状态条件子模型</h2>\n'
        html += '<p style="color:#888;margin-bottom:15px;">基于恒指前3月滚动收益率自动划分牛/熊/震荡，按市场状态分别训练独立模型</p>\n'
        
        # 状态分布概览
        dist = cond_result.get("state_distribution", {})
        degraded = cond_result.get("degraded_states", [])
        html += '<div class="card-grid" style="grid-template-columns:repeat(3,1fr);">\n'
        for state in ["BULL", "BEAR", "NEUTRAL"]:
            cnt = dist.get(state, 0)
            model = cond_result["models"].get(state, {})
            r2 = model.get("extra", {}).get("r2", 0)
            warning = model.get("warning")
            c = state_colors.get(state, "#888")
            lbl = state_labels.get(state, state)
            deg_mark = " (降级)" if state in degraded else ""
            html += f'<div class="stat-card" style="border-color:{c}40;">'
            html += f'<div class="label">{lbl}{deg_mark}</div>'
            html += f'<div class="value" style="color:{c}">{cnt}</div>'
            html += f'<div class="sub">R²={r2:.3f}</div>'
            if warning:
                html += f'<div class="sub" style="color:#ffaa00;font-size:0.75em;">{warning}</div>'
            html += '</div>\n'
        html += '</div>\n'
        
        # 各状态表现对比表
        if ms_res:
            html += '<h3>各市场状态打新表现对比</h3>\n'
            html += '<table><thead><tr>'
            html += '<th>市场状态</th><th>样本</th><th>胜率</th><th>平均涨幅</th><th>中位涨幅</th><th>期望收益</th><th>最优卖出</th><th>模型状态</th>'
            html += '</tr></thead><tbody>\n'
            
            for ms in ms_res:
                c = ms.get("color", "#888")
                html += f'<tr><td style="color:{c};font-weight:bold">{ms["label"]}</td>'
                html += f'<td>{ms["count"]}</td>'
                html += f'<td style="color:{wr_color(ms["win_rate"])}">{ms["win_rate"]:.0f}%</td>'
                html += f'<td style="color:{get_color(ms["avg"])}">{ms["avg"]:+.1f}%</td>'
                html += f'<td style="color:{get_color(ms["median"])}">{ms["median"]:+.1f}%</td>'
                html += f'<td style="color:{get_color(ms["expected"])};font-weight:bold">{ms["expected"]:+.1f}%</td>'
                html += f'<td style="color:#ffcc00">{ms["best_tp"]}</td>'
                html += f'<td>{"✅ 独立模型" if not ms.get("is_degraded") else "⚠️ 降级"}</td></tr>\n'
            
            html += '</tbody></table>\n'
            
            # 各状态卖出时点对比
            html += '<h3>各市场状态最优卖出时点对比</h3>\n'
            html += '<table><thead><tr><th>市场状态</th><th>暗盘期望</th><th>首日期望</th><th>3天期望</th><th>5天期望</th><th>建议</th></tr></thead><tbody>\n'
            
            for ms in ms_res:
                c = ms.get("color", "#888")
                html += f'<tr><td style="color:{c};font-weight:bold">{ms["label"]}</td>'
                tps = {tp["label"]: tp for tp in ms.get("tp_stats", [])}
                for lbl in ["暗盘", "首日", "第3天", "第5天"]:
                    tp = tps.get(lbl, {})
                    v = tp.get("expected", 0)
                    is_best = lbl == ms.get("best_tp")
                    style = f'color:{get_color(v)};{"font-weight:bold;text-decoration:underline;" if is_best else ""}'
                    html += f'<td style="{style}">{v:+.1f}%</td>'
                html += f'<td style="color:#ffcc00;font-weight:bold">{ms.get("best_tp", "N/A")}</td></tr>\n'
            
            html += '</tbody></table>\n'
            
            # 条件子模型核心发现
            html += '<div style="background:rgba(255,204,0,0.08);border:1px solid rgba(255,204,0,0.2);border-radius:12px;padding:20px;margin-top:15px;">\n'
            html += '<h3 style="color:#ffcc00;margin-top:0;">💡 条件子模型核心发现</h3>\n'
            html += '<ul style="list-style:none;padding:0;">\n'
            
            # 自动生成洞察
            if len(ms_res) >= 2:
                best_state = max(ms_res, key=lambda x: x.get("expected", 0))
                worst_state = min(ms_res, key=lambda x: x.get("expected", 0))
                html += f'<li style="padding:6px 0;">• <b>最佳市场环境：</b><span style="color:{best_state["color"]}">{best_state["label"]}</span> — 期望收益 {best_state["expected"]:+.1f}%，胜率 {best_state["win_rate"]:.0f}%</li>\n'
                html += f'<li style="padding:6px 0;">• <b>最差市场环境：</b><span style="color:{worst_state["color"]}">{worst_state["label"]}</span> — 期望收益 {worst_state["expected"]:+.1f}%，胜率 {worst_state["win_rate"]:.0f}%</li>\n'
                
                # 对比卖出策略差异
                best_tps = {ms["label"]: ms.get("best_tp", "N/A") for ms in ms_res}
                tp_diff = len(set(best_tps.values())) > 1
                if tp_diff:
                    html += '<li style="padding:6px 0;">• <b>卖出策略因市场状态而异：</b>'
                    for label, tp in best_tps.items():
                        html += f'{label}→{tp}  '
                    html += '</li>\n'
                else:
                    html += f'<li style="padding:6px 0;">• <b>所有市场状态最优卖出时点一致：</b>{list(best_tps.values())[0]}</li>\n'
            
            html += '</ul></div>\n'
        
        html += '</div>\n'

    # ============ V3.4: 18C 效应分析 ============
    if effect_18c and effect_18c.get("is_18c_count", 0) > 0:
        e = effect_18c
        s18 = e["is_18c_stats"]
        sn = e["non_18c_stats"]
        html += f'''<div class="section">
<h2>🏷️ 18C / B类上市机制效应（{e["is_18c_count"]}只 vs {e["non_18c_count"]}只）</h2>
<div class="card-grid">
<div class="stat-card"><div class="label">18C 首日均值</div><div class="value" style="color:{get_color(s18["avg"])}">{s18["avg"]:+.1f}%</div><div class="sub">胜率 {s18["win_rate"]:.0f}%</div></div>
<div class="stat-card"><div class="label">非18C 首日均值</div><div class="value" style="color:{get_color(sn["avg"])}">{sn["avg"]:+.1f}%</div><div class="sub">胜率 {sn["win_rate"]:.0f}%</div></div>
<div class="stat-card"><div class="label">差异</div><div class="value" style="color:{"#ff4444" if s18["avg"] < sn["avg"] else "#00b050"}">{s18["avg"]-sn["avg"]:+.1f}%</div><div class="sub">首日均值差</div></div>
</div>'''
        # 18C 有无基石对比
        wcs = e.get("is_18c_with_cs", {})
        ncs = e.get("is_18c_no_cs", {})
        if wcs.get("count", 0) > 0 and ncs.get("count", 0) > 0:
            wcs_s = wcs["stats"]
            ncs_s = ncs["stats"]
            html += f'''<h3>18C 内部：有基石 vs 无基石</h3>
<table><thead><tr><th>分组</th><th>只数</th><th>首日均值</th><th>胜率</th><th>中位数</th></tr></thead><tbody>
<tr><td>有基石</td><td>{wcs["count"]}</td><td style="color:{get_color(wcs_s["avg"])}">{wcs_s["avg"]:+.1f}%</td><td>{wcs_s["win_rate"]:.0f}%</td><td>{wcs_s["median"]:+.1f}%</td></tr>
<tr><td>无基石</td><td>{ncs["count"]}</td><td style="color:{get_color(ncs_s["avg"])}">{ncs_s["avg"]:+.1f}%</td><td>{ncs_s["win_rate"]:.0f}%</td><td>{ncs_s["median"]:+.1f}%</td></tr>
</tbody></table>'''
        html += '</div>\n'

    # ============ 结论 ============
    html += f'''<div class="conclusion">
<h2>🎯 回测结论与策略建议</h2>
<ul>
<li><b>最佳甜蜜区间：超购 {sweet_spot_label.split("(")[0].strip()}</b> — 期望收益最高，胜率 {sweet.get("win_rate",0):.0f}%</li>
<li><b>优先选择有基石投资者的新股</b> — 胜率差距巨大（{cs_res["with"]["win_rate"]:.0f}% vs {cs_res["without"]["win_rate"]:.0f}%）</li>
<li><b>行业偏好：医药、AI、消费</b> — 近一年赚钱效应最好</li>
<li><b>小市值更易翻倍</b> — 募资&lt;5亿的小票涨幅远超大票</li>
<li><b>多因子评分 S/A 档胜率显著高于 C/D 档</b></li>'''
    if effect_18c and effect_18c.get("is_18c_count", 0) > 0:
        html += f'\n<li><b>18C/B类股票需额外谨慎</b> — 首日均值 {effect_18c["is_18c_stats"]["avg"]:+.1f}% vs 非18C {effect_18c["non_18c_stats"]["avg"]:+.1f}%</li>'
    html += '''
</ul></div>

<div class="disclaimer">
⚠️ 本分析基于历史数据回测，不构成投资建议。港股打新存在风险，过往表现不代表未来收益。<br>
数据来源：东方财富、华盛通、富途牛牛、财联社等公开信息 | hk-ipo-sweet-spot V3.4 精准匹配与暗盘联动版
</div></div></body></html>'''
    return html


# ============================================
# 单股报告 / 策略报告生成
# ============================================

def generate_single_report(analysis):
    """已上市股票回测分析报告"""
    t = analysis["target"]
    html = f'''<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{t["name"]}({t["code"]}) 回测分析</title><style>{CSS}</style></head>
<body><div class="container">
<div class="header">
<h1>📊 {t["name"]}（{t["code"]}）回测分析</h1>
<div class="subtitle">上市日期：{t["date"]} | 超购：{t["subscription_mult"]:.0f}倍 | 行业：{t["category"]}</div>
</div>

<div class="section">
<h2>核心数据</h2>
<div class="card-grid">
<div class="stat-card"><div class="label">首日涨幅</div><div class="value" style="color:{get_color(t["day1_return"])}">{t["day1_return"]:+.1f}%</div></div>
<div class="stat-card"><div class="label">综合评分</div><div class="value" style="color:{TIER_COLORS.get(analysis["tier"],"#888")}">{analysis["score"]:.0f}</div><div class="sub">{analysis["tier"]}档</div></div>
<div class="stat-card"><div class="label">排名</div><div class="value" style="color:#ff8c00">{analysis["rank"]}/{analysis["total"]}</div></div>
<div class="stat-card"><div class="label">超购区间</div><div class="value" style="color:#ffaa00;font-size:1.2em">{analysis["sub_range"]}</div></div>
<div class="stat-card"><div class="label">暗盘涨幅</div><div class="value" style="color:{get_color(t.get("dark_return",0) or 0)}">{t.get("dark_return","N/A") if t.get("dark_return") is not None else "N/A"}%</div></div>
<div class="stat-card"><div class="label">基石投资者</div><div class="value">{"✅ 有" if t["has_cornerstone"] else "❌ 无"}</div></div>
</div></div>'''

    # 同类对比
    for label, stats, peers in [
        (f"同区间（{analysis['sub_range']}）", analysis["same_range_stats"], analysis["same_range"]),
        (f"同行业（{t['category']}）", analysis["same_cat_stats"], analysis["same_cat"]),
    ]:
        if stats and stats["count"] > 0:
            html += f'<div class="section"><h2>{label}对比</h2>'
            html += f'<p>该区间共 {stats["count"]} 只 | 平均涨幅 {stats["avg"]:+.1f}% | 胜率 {stats["win_rate"]:.0f}%</p>'
            if peers:
                html += '<table><thead><tr><th>名称</th><th>代码</th><th>超购</th><th>首日</th><th>暗盘</th></tr></thead><tbody>'
                for p in peers:
                    html += f'<tr><td>{p["name"]}</td><td>{p["code"]}</td><td>{p["subscription_mult"]:.0f}x</td>'
                    html += f'<td style="color:{get_color(p["day1_return"])}">{p["day1_return"]:+.1f}%</td>'
                    dk = p.get("dark_return")
                    html += f'<td style="color:{get_color(dk or 0)}">{dk:+.1f}%</td></tr>\n' if dk is not None else '<td>-</td></tr>\n'
                html += '</tbody></table>'
            html += '</div>\n'

    html += '<div class="disclaimer">数据来源：东方财富、华盛通等公开信息 | hk-ipo-sweet-spot V3.4</div></div></body></html>'
    return html


def generate_strategy_report(result):
    """未上市新股卖出策略报告 [V3.4 增强版]"""
    import math as _math
    p = result["params"]
    ms = result.get("market_state")
    ms_labels = {"BULL": "🐂 牛市", "BEAR": "🐻 熊市", "NEUTRAL": "⚖️ 震荡"}
    ms_colors = {"BULL": "#ff4444", "BEAR": "#00b050", "NEUTRAL": "#ffaa00"}
    ms_label = ms_labels.get(ms, "未知") if ms else "自动"
    ms_color = ms_colors.get(ms, "#888") if ms else "#888"
    model_source = result.get("model_source", "全局模型")
    model_warning = result.get("model_warning")
    is_18c = result.get("is_18c", False)
    
    # 18C 标签
    tag_18c = ' <span style="background:rgba(255,68,68,0.25);color:#ff6666;padding:2px 10px;border-radius:10px;font-size:0.7em;vertical-align:middle;">18C</span>' if is_18c else ''
    
    html = f'''<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{p.get("name",p["code"])} 卖出策略建议</title><style>{CSS}
.radar-wrap {{ display: flex; align-items: center; justify-content: center; gap: 30px; flex-wrap: wrap; }}
.radar-legend {{ font-size: 0.9em; line-height: 2; }}
.radar-legend .dot {{ display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 6px; }}
.dark-card {{ background: linear-gradient(135deg, rgba(100,100,255,0.12), rgba(100,200,255,0.06)); border: 1px solid rgba(100,150,255,0.3); border-radius: 14px; padding: 24px; margin-top: 15px; }}
.dark-card h3 {{ color: #88aaff; margin-bottom: 12px; }}
.pattern-tag {{ display: inline-block; padding: 4px 14px; border-radius: 20px; font-weight: bold; font-size: 0.95em; }}
.sim-bar {{ background: rgba(255,140,0,0.15); height: 6px; border-radius: 3px; overflow: hidden; }}
.sim-bar-fill {{ height: 100%; border-radius: 3px; background: linear-gradient(90deg, #ff8c00, #ffcc00); }}
</style></head>
<body><div class="container">
<div class="header">
<h1>🎯 {p.get("name",p["code"])}（{p["code"]}）卖出策略{tag_18c}</h1>
<div class="subtitle">超购：{p["subscription_mult"]:.0f}倍 | {"有" if p["has_cornerstone"] else "无"}基石 | {p["category"]} | 募资{p["fundraising"]}亿</div>
<div class="meta" style="margin-top:8px;">市场状态：<span style="color:{ms_color};font-weight:bold">{ms_label}</span> | 使用模型：{model_source}</div>
</div>

<div class="insight-box">
<h2>策略建议</h2>
<div class="card-grid">
<div class="stat-card"><div class="label">综合评分</div><div class="value" style="color:{TIER_COLORS.get(result["tier"],"#888")}">{result["score"]:.0f}</div><div class="sub">{result["tier"]}档</div></div>
<div class="stat-card"><div class="label">同类群样本</div><div class="value" style="color:#ff8c00">{result["peer_count"]}</div><div class="sub">{result["sub_range"]}</div></div>'''

    if result["best_tp"]:
        bt = result["best_tp"]
        html += f'''<div class="stat-card" style="border-color:rgba(255,204,0,0.5)"><div class="label">推荐卖出时点</div><div class="value" style="color:#ffcc00">{bt["label"]}</div><div class="sub">期望收益 {bt["expected"]:+.1f}%</div></div>'''

    html += '</div>'
    
    # 模型降级警告
    if model_warning:
        html += f'<div style="margin-top:12px;padding:8px 15px;background:rgba(255,170,0,0.1);border:1px solid rgba(255,170,0,0.3);border-radius:8px;color:#ffaa00;font-size:0.9em;">⚠️ {model_warning}</div>'
    
    html += '</div>\n'

    # ============ V3.4: 暗盘联动修正卡 ============
    dark_fb = result.get("dark_feedback")
    if dark_fb:
        # 模式颜色
        pat_colors = {
            "暗盘透支": ("#ff4444", "rgba(255,68,68,0.2)"),
            "暗盘蓄力": ("#22cc88", "rgba(34,204,136,0.2)"),
            "暗盘不及预期": ("#ffaa00", "rgba(255,170,0,0.2)"),
            "暗盘破发（预期外）": ("#ff2222", "rgba(255,34,34,0.3)"),
            "符合预期": ("#88aaff", "rgba(136,170,255,0.2)"),
        }
        pc, pbg = pat_colors.get(dark_fb["pattern"], ("#888", "rgba(136,136,136,0.2)"))
        
        html += f'''<div class="section">
<h2>🔗 暗盘联动修正</h2>
<div class="dark-card">
<div style="display:flex;align-items:center;gap:15px;margin-bottom:15px;">
<span class="pattern-tag" style="color:{pc};background:{pbg}">{dark_fb["pattern"]}</span>
<span style="color:#aaa;font-size:0.9em;">{dark_fb.get("pattern_desc","")}</span>
</div>
<div class="card-grid">
<div class="stat-card"><div class="label">暗盘实际</div><div class="value" style="color:{get_color(dark_fb["dark_actual"])}">{dark_fb["dark_actual"]:+.1f}%</div></div>
<div class="stat-card"><div class="label">同类群预期</div><div class="value" style="color:{get_color(dark_fb["dark_expected"])}">{dark_fb["dark_expected"]:+.1f}%</div></div>
<div class="stat-card"><div class="label">偏差</div><div class="value" style="color:{get_color(dark_fb["dark_deviation"])}">{dark_fb["dark_deviation"]:+.1f}%</div></div>
</div>
<h3 style="margin-top:18px;">修正后预期 vs 原始预期</h3>
<table><thead><tr><th>时点</th><th>原始预期</th><th>修正后预期</th><th>变化</th></tr></thead><tbody>'''
        # 从 tp_stats 获取原始预期
        orig = {}
        for tp in result.get("tp_stats", []):
            orig[tp["label"]] = tp["expected"]
        for label, corrected in [("首日", dark_fb.get("corrected_day1")), ("Day3", dark_fb.get("corrected_day3")), ("Day5", dark_fb.get("corrected_day5"))]:
            if corrected is not None:
                o = orig.get(label, 0)
                delta = corrected - o
                html += f'<tr><td><b>{label}</b></td><td style="color:{get_color(o)}">{o:+.1f}%</td>'
                html += f'<td style="color:{get_color(corrected)};font-weight:bold">{corrected:+.1f}%</td>'
                html += f'<td style="color:{get_color(delta)}">{delta:+.1f}%</td></tr>\n'
        html += '</tbody></table>'
        
        # 暗盘相似案例
        sim_dk = dark_fb.get("similar_dark_peers", [])
        if sim_dk:
            html += f'<h3 style="margin-top:18px;">暗盘走势最相似的历史案例（{len(sim_dk)}只）</h3>'
            html += '<table><thead><tr><th>名称</th><th>暗盘</th><th>首日</th><th>Day3</th><th>Day5</th></tr></thead><tbody>'
            for d in sim_dk:
                html += f'<tr><td>{d["name"]}</td>'
                for k in ["dark_return", "day1_return", "day3_return", "day5_return"]:
                    v = d.get(k)
                    if v is not None:
                        html += f'<td style="color:{get_color(v)}">{v:+.1f}%</td>'
                    else:
                        html += '<td>-</td>'
                html += '</tr>\n'
            html += '</tbody></table>'
        
        html += f'<div style="margin-top:10px;color:#666;font-size:0.8em;">样本量: {dark_fb.get("sample_size",0)}只 | 转换率: 暗盘→首日 {dark_fb["conversion_rates"]["d2d1"]:.2f}x'
        if dark_fb["conversion_rates"].get("d2d3"):
            html += f' | 暗盘→Day3 {dark_fb["conversion_rates"]["d2d3"]:.2f}x'
        html += '</div></div></div>\n'

    # ============ V3.4: 相似度雷达图 + 同类群详情 ============
    sim_peers = result.get("sim_peers", [])
    if sim_peers:
        # 生成 SVG 雷达图（5维：超购/基石/行业/募资/18C）
        dims = ["超购", "基石", "行业", "募资", "18C"]
        dim_keys = ["sub", "cs", "cat", "fund", "is_18c"]
        # 取 top-1 peer 的 breakdown 作为雷达展示
        top_bd = sim_peers[0]["breakdown"]
        avg_bd = {}
        for k in dim_keys:
            vals = [sp["breakdown"][k] for sp in sim_peers[:5]]
            avg_bd[k] = sum(vals) / len(vals) if vals else 0
        
        # SVG 雷达图参数
        cx, cy, r = 120, 120, 90
        n_dims = len(dims)
        
        def polar(i, val, radius=r):
            angle = -_math.pi/2 + 2*_math.pi*i/n_dims
            x = cx + radius * val * _math.cos(angle)
            y = cy + radius * val * _math.sin(angle)
            return x, y
        
        # 网格
        svg = f'<svg width="240" height="260" viewBox="0 0 240 260" xmlns="http://www.w3.org/2000/svg">'
        for level in [0.25, 0.5, 0.75, 1.0]:
            pts = " ".join(f"{polar(i,level)[0]:.1f},{polar(i,level)[1]:.1f}" for i in range(n_dims))
            svg += f'<polygon points="{pts}" fill="none" stroke="rgba(255,255,255,0.1)" stroke-width="0.5"/>'
        # 轴线
        for i in range(n_dims):
            x2, y2 = polar(i, 1.0)
            svg += f'<line x1="{cx}" y1="{cy}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="rgba(255,255,255,0.15)" stroke-width="0.5"/>'
        # 标签
        for i, dim in enumerate(dims):
            lx, ly = polar(i, 1.2)
            svg += f'<text x="{lx:.0f}" y="{ly:.0f}" text-anchor="middle" fill="#aaa" font-size="11">{dim}</text>'
        # Top-1 peer 多边形
        pts1 = " ".join(f"{polar(i, top_bd[dim_keys[i]])[0]:.1f},{polar(i, top_bd[dim_keys[i]])[1]:.1f}" for i in range(n_dims))
        svg += f'<polygon points="{pts1}" fill="rgba(255,140,0,0.2)" stroke="#ff8c00" stroke-width="1.5"/>'
        # Top-5 均值多边形
        pts2 = " ".join(f"{polar(i, avg_bd[dim_keys[i]])[0]:.1f},{polar(i, avg_bd[dim_keys[i]])[1]:.1f}" for i in range(n_dims))
        svg += f'<polygon points="{pts2}" fill="rgba(100,200,255,0.1)" stroke="#66ccff" stroke-width="1" stroke-dasharray="4,2"/>'
        # 顶点标记
        for i in range(n_dims):
            x, y = polar(i, top_bd[dim_keys[i]])
            svg += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="#ff8c00"/>'
        svg += f'<text x="{cx}" y="255" text-anchor="middle" fill="#888" font-size="10">橙色=最相似 | 蓝色=Top5均值</text>'
        svg += '</svg>'
        
        html += f'''<div class="section">
<h2>🎯 多维相似度匹配（V3.4）</h2>
<div class="radar-wrap">
{svg}
<div class="radar-legend">
<div><span class="dot" style="background:#ff8c00"></span><b>最相似: {sim_peers[0]["stock"]["name"]}</b> ({sim_peers[0]["similarity"]:.2f})</div>
<div style="margin-top:4px;"><span class="dot" style="background:#66ccff"></span>Top 5 平均相似度</div>
<div style="margin-top:12px;color:#aaa;font-size:0.85em;">
超购: {top_bd["sub"]:.2f} | 基石: {top_bd["cs"]:.0f} | 行业: {top_bd["cat"]:.2f}<br>
募资: {top_bd["fund"]:.2f} | 18C: {top_bd["is_18c"]:.0f}
</div>
</div></div>
<h3 style="margin-top:20px;">相似度排名详情</h3>
<table><thead><tr><th>#</th><th>名称</th><th>相似度</th><th>超购</th><th>基石</th><th>行业</th><th>暗盘</th><th>首日</th></tr></thead><tbody>'''
        for idx, sp in enumerate(sim_peers):
            s = sp["stock"]
            sim = sp["similarity"]
            bar_w = max(sim * 100, 5)
            html += f'<tr><td>{idx+1}</td><td>{s["name"]}</td>'
            html += f'<td><div style="display:flex;align-items:center;gap:6px;"><div class="sim-bar" style="width:60px;"><div class="sim-bar-fill" style="width:{bar_w:.0f}%"></div></div><span style="color:#ffaa00">{sim:.2f}</span></div></td>'
            html += f'<td>{s["subscription_mult"]:.0f}x</td>'
            html += f'<td>{"✓" if s.get("has_cornerstone") else "✗"}</td>'
            html += f'<td>{s.get("category","")}</td>'
            dk = s.get("dark_return")
            d1 = s.get("day1_return")
            html += f'<td style="color:{get_color(dk or 0)}">{dk:+.1f}%</td>' if dk is not None else '<td>-</td>'
            html += f'<td style="color:{get_color(d1 or 0)}">{d1:+.1f}%</td>' if d1 is not None else '<td>-</td>'
            html += '</tr>\n'
        html += '</tbody></table></div>\n'

    # ============ 时点对比 ============
    html += '<div class="section"><h2>⏱️ 各时点收益预估（基于同类群历史数据）</h2>'
    html += '<table><thead><tr><th>时点</th><th>样本</th><th>平均涨幅</th><th>胜率</th><th>期望收益</th></tr></thead><tbody>'
    for tp in result["tp_stats"]:
        is_best = result["best_tp"] and tp["label"] == result["best_tp"]["label"]
        rc = "best-row" if is_best else ""
        html += f'<tr class="{rc}"><td><b>{tp["label"]}{"⭐" if is_best else ""}</b></td><td>{tp["count"]}</td>'
        html += f'<td style="color:{get_color(tp["avg"])}">{tp["avg"]:+.1f}%</td>'
        html += f'<td style="color:{wr_color(tp["win_rate"])}">{tp["win_rate"]:.0f}%</td>'
        html += f'<td style="color:{get_color(tp["expected"])};font-weight:bold">{tp["expected"]:+.1f}%</td></tr>\n'
    html += '</tbody></table></div>\n'

    # ============ V3.4: 18C 独立分析 ============
    a18 = result.get("is_18c_analysis")
    if a18 and is_18c:
        html += f'''<div class="section">
<h2>⚠️ 18C / B类上市机制专项分析</h2>
<p style="color:#aaa;margin-bottom:15px;">18C 机制允许未盈利企业上市，此类股票波动性较大。以下为 {a18["total"]} 只 18C 历史股票统计。</p>
<div class="card-grid">'''
        if a18["stats"]:
            html += f'<div class="stat-card"><div class="label">18C 首日均值</div><div class="value" style="color:{get_color(a18["stats"]["avg"])}">{a18["stats"]["avg"]:+.1f}%</div><div class="sub">胜率 {a18["stats"]["win_rate"]:.0f}%</div></div>'
        if a18["dark_stats"]:
            html += f'<div class="stat-card"><div class="label">18C 暗盘均值</div><div class="value" style="color:{get_color(a18["dark_stats"]["avg"])}">{a18["dark_stats"]["avg"]:+.1f}%</div><div class="sub">胜率 {a18["dark_stats"]["win_rate"]:.0f}%</div></div>'
        wcs = a18.get("with_cs", {})
        ncs = a18.get("no_cs", {})
        if wcs.get("stats"):
            html += f'<div class="stat-card"><div class="label">18C 有基石</div><div class="value" style="color:{get_color(wcs["stats"]["avg"])}">{wcs["stats"]["avg"]:+.1f}%</div><div class="sub">{wcs["count"]}只</div></div>'
        if ncs.get("stats"):
            html += f'<div class="stat-card" style="border-color:rgba(255,68,68,0.3)"><div class="label">18C 无基石</div><div class="value" style="color:{get_color(ncs["stats"]["avg"])}">{ncs["stats"]["avg"]:+.1f}%</div><div class="sub">{ncs["count"]}只 ⚠️</div></div>'
        html += '</div>'
        # 风险提示
        if ncs.get("stats") and ncs["stats"]["win_rate"] < 50:
            html += f'<div style="margin-top:12px;padding:10px 15px;background:rgba(255,68,68,0.1);border:1px solid rgba(255,68,68,0.3);border-radius:8px;color:#ff6666;font-size:0.9em;">⚠️ <b>高风险警告：</b>18C 无基石股票历史胜率仅 {ncs["stats"]["win_rate"]:.0f}%，需格外谨慎</div>'
        html += '</div>\n'

    # ============ 同类群参考（旧版兼容） ============
    if result.get("peers") and not sim_peers:
        html += '<div class="section"><h2>📋 同类群历史参考</h2><table><thead><tr><th>名称</th><th>超购</th><th>暗盘</th><th>首日</th><th>3天</th><th>5天</th></tr></thead><tbody>'
        for peer in result["peers"]:
            html += f'<tr><td>{peer["name"]}</td><td>{peer["subscription_mult"]:.0f}x</td>'
            for k in ["dark_return", "day1_return", "day3_return", "day5_return"]:
                v = peer.get(k)
                if v is not None:
                    html += f'<td style="color:{get_color(v)}">{v:+.1f}%</td>'
                else:
                    html += '<td>-</td>'
            html += '</tr>\n'
        html += '</tbody></table></div>\n'

    html += '''<div class="disclaimer">⚠️ 以上策略基于历史同类群回测，不构成投资建议。实际走势受市场环境、打新情绪等多因素影响。<br>
hk-ipo-sweet-spot V3.4 精准匹配与暗盘联动版</div></div></body></html>'''
    return html
