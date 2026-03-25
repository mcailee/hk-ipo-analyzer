"""Jinja2 HTML 报告渲染。"""
from __future__ import annotations

import base64
from datetime import datetime
from pathlib import Path
from typing import Optional

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from jinja2 import Template
from models.ipo_data import FinalReport
from utils.helpers import get_skill_root, logger


def _score_color(score: float) -> str:
    if score >= 75:
        return "#00b894"
    elif score >= 60:
        return "#0984e3"
    elif score >= 45:
        return "#f39c12"
    return "#d63031"


def _score_color_class(score: float) -> str:
    if score >= 75:
        return "green"
    elif score >= 60:
        return "blue"
    elif score >= 45:
        return "yellow"
    return "red"


def _bar_class(score: float) -> str:
    if score >= 75:
        return "high"
    elif score >= 60:
        return "mid"
    elif score >= 45:
        return "low"
    return "danger"


def _rating_class(rating: str) -> str:
    return {
        "强烈推荐": "strong-buy",
        "推荐": "buy",
        "中性": "neutral",
        "回避": "avoid",
    }.get(rating, "neutral")


def generate_html_report(report: FinalReport,
                         output_dir: Path,
                         radar_png_path: Optional[Path] = None) -> Path:
    """渲染 HTML 报告。"""
    # 加载模板
    template_path = get_skill_root() / "assets" / "templates" / "report.html"
    with open(template_path, "r", encoding="utf-8") as f:
        template = Template(f.read())

    # 雷达图 base64
    radar_base64 = ""
    if radar_png_path and radar_png_path.exists():
        with open(radar_png_path, "rb") as f:
            radar_base64 = base64.b64encode(f.read()).decode("utf-8")

    # 给维度分数添加颜色辅助属性
    dim_sorted = sorted(report.dimension_scores, key=lambda x: x.weight, reverse=True)
    for ds in dim_sorted:
        ds._color = _score_color(ds.score)
        ds._bar_class = _bar_class(ds.score)

    # 渲染
    html = template.render(
        report=report,
        score_color_class=_score_color_class(report.total_score),
        rating_class=_rating_class(report.rating),
        radar_base64=radar_base64,
        dimension_scores_sorted=dim_sorted,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )

    # 保存
    html_path = output_dir / f"report_phase{report.phase}.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    logger.info(f"HTML 报告已生成: {html_path}")
    return html_path
