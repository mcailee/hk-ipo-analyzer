"""Jinja2 HTML 报告渲染。

v3.0: 支持卖出时机建议 + 市场情绪 + 概率预测 + 中签率估算。
"""
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


def _confidence_label(conf: str) -> str:
    return {"high": "高", "medium": "中", "low": "低"}.get(conf, conf)


def _strategy_label(strat: str) -> str:
    return {
        "quick_flip": "⚡ 速战速决",
        "short_hold": "📈 短线持有",
        "medium_hold": "🏦 中线持有",
    }.get(strat, strat)


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

    # 卖出时机建议（如果有）
    sell_timing_data = None
    if report.sell_timing:
        st = report.sell_timing
        sell_timing_data = {
            "strategy": _strategy_label(st.strategy),
            "suggested_days": st.suggested_days,
            "rationale": st.rationale,
            "stop_loss_pct": st.stop_loss_pct,
            "take_profit_pct": st.take_profit_pct,
            "confidence": _confidence_label(st.confidence),
        }

    # 概率预测区间（P3 新增）
    probability_data = None
    if report.probability:
        p = report.probability
        probability_data = {
            "first_day_up_prob": p.first_day_up_prob,
            "first_day_down_prob": p.first_day_down_prob,
            "expected_return_low": p.expected_return_low,
            "expected_return_mid": p.expected_return_mid,
            "expected_return_high": p.expected_return_high,
            "confidence_level": _confidence_label(p.confidence_level),
            "methodology": p.methodology,
        }

    # 中签率估算（P3 新增）
    allotment_data = None
    if report.allotment:
        a = report.allotment
        allotment_data = {
            "estimated_allocation_rate": a.estimated_allocation_rate,
            "estimated_one_hand_win_rate": a.estimated_one_hand_win_rate,
            "optimal_hands": a.optimal_hands,
            "expected_profit_per_hand": a.expected_profit_per_hand,
            "capital_required": a.capital_required,
            "capital_efficiency": a.capital_efficiency,
            "methodology": a.methodology,
        }

    # 打新策略推荐（P4 新增）
    strategy_data = None
    if report.strategy and report.strategy.recommended_strategy:
        s = report.strategy
        accounts_list = []
        for acct in s.accounts:
            accounts_list.append({
                "account_id": acct.account_id,
                "group": "甲组" if acct.group == "A" else "乙组",
                "hands": acct.subscription_hands,
                "financing_label": f"{acct.financing_mult:.0f}倍孖展" if acct.financing_mult > 0 else "现金",
                "own_capital": acct.own_capital,
                "financing_cost": acct.financing_cost,
                "winning_hands": acct.expected_winning_hands,
                "net_profit": acct.expected_net_profit,
                "roi": acct.roi,
            })
        strategy_data = {
            "investor_tier_label": s.investor_tier_label,
            "total_capital": s.total_capital,
            "num_accounts": s.num_accounts,
            "strategy_label": s.strategy_label,
            "strategy_rationale": s.strategy_rationale,
            "group_a_one_hand_rate": s.group_a_sim.one_hand_rate if s.group_a_sim else None,
            "group_b_alloc_rate": s.group_b_sim.allocation_rate if s.group_b_sim else None,
            "accounts": accounts_list,
            "total_own_capital": s.total_own_capital,
            "total_financing_cost": s.total_financing_cost,
            "total_net_profit": s.total_expected_net_profit,
            "overall_roi": s.overall_roi,
            "annualized_roi": s.capital_efficiency_annualized,
            "breakeven_return": s.breakeven_return,
            "max_loss": s.max_loss_scenario,
            "methodology": s.methodology,
        }

    # 渲染
    html = template.render(
        report=report,
        score_color_class=_score_color_class(report.total_score),
        rating_class=_rating_class(report.rating),
        radar_base64=radar_base64,
        dimension_scores_sorted=dim_sorted,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        sell_timing=sell_timing_data,
        probability=probability_data,
        allotment=allotment_data,
        strategy=strategy_data,
    )

    # 保存
    html_path = output_dir / f"report_phase{report.phase}.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    logger.info(f"HTML 报告已生成: {html_path}")
    return html_path
