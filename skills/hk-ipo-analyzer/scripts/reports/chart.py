"""matplotlib 雷达图生成。"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Optional

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np

from models.ipo_data import FinalReport


# 尝试使用中文字体
def _setup_chinese_font():
    """配置中文字体。"""
    candidates = [
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            plt.rcParams["font.family"] = fm.FontProperties(fname=path).get_name()
            return
    plt.rcParams["font.sans-serif"] = ["SimHei", "Heiti TC", "Arial Unicode MS", "sans-serif"]
    plt.rcParams["axes.unicode_minus"] = False


_setup_chinese_font()


def generate_radar_chart(report: FinalReport,
                         output_path: Path,
                         phase1_report: Optional[FinalReport] = None) -> Path:
    """生成雷达图 PNG 文件。"""
    scores = report.dimension_scores
    if not scores:
        return output_path

    # 按权重排序
    scores = sorted(scores, key=lambda x: x.weight, reverse=True)

    labels = [ds.display_name for ds in scores]
    values = [ds.score for ds in scores]
    n = len(labels)

    # 计算角度
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False).tolist()
    values_closed = values + [values[0]]
    angles_closed = angles + [angles[0]]

    fig, ax = plt.subplots(figsize=(10, 10), subplot_kw=dict(polar=True))

    # Phase2 叠加 Phase1 轮廓
    if phase1_report and phase1_report.dimension_scores:
        p1_scores = sorted(phase1_report.dimension_scores, key=lambda x: x.weight, reverse=True)
        p1_values = [ds.score for ds in p1_scores]
        # 如果 Phase1 维度少于 Phase2，补 50
        while len(p1_values) < n:
            p1_values.append(50)
        p1_closed = p1_values[:n] + [p1_values[0]]
        ax.plot(angles_closed, p1_closed, "o--", linewidth=1.5,
                label=f"Phase 1 ({phase1_report.total_score:.0f}分)",
                color="#999999", alpha=0.6)
        ax.fill(angles_closed, p1_closed, alpha=0.1, color="#999999")

    # 当前阶段
    color_map = {
        "强烈推荐": "#00b894",
        "推荐": "#0984e3",
        "中性": "#fdcb6e",
        "回避": "#d63031",
    }
    main_color = color_map.get(report.rating, "#0984e3")

    ax.plot(angles_closed, values_closed, "o-", linewidth=2.5,
            label=f"Phase {report.phase} ({report.total_score:.0f}分)",
            color=main_color)
    ax.fill(angles_closed, values_closed, alpha=0.25, color=main_color)

    # 标注分数
    for angle, value, label in zip(angles, values, labels):
        ax.annotate(f"{value:.0f}",
                    xy=(angle, value),
                    xytext=(5, 5),
                    textcoords="offset points",
                    fontsize=11, fontweight="bold",
                    color=main_color)

    ax.set_xticks(angles)
    ax.set_xticklabels(labels, fontsize=12)
    ax.set_ylim(0, 100)
    ax.set_yticks([20, 40, 60, 80])
    ax.set_yticklabels(["20", "40", "60", "80"], fontsize=9, color="grey")

    # 标题
    title = f"{report.company_name} ({report.stock_code}) — Phase {report.phase} 雷达图"
    ax.set_title(title, fontsize=14, fontweight="bold", pad=20)
    ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1))

    plt.tight_layout()

    # 保存
    chart_path = output_path / f"radar_phase{report.phase}.png"
    fig.savefig(str(chart_path), dpi=150, bbox_inches="tight",
                facecolor="white", edgecolor="none")
    plt.close(fig)

    return chart_path
