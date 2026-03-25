"""Rich 终端美化输出。"""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich.text import Text

from models.ipo_data import FinalReport, DimensionScore


console = Console()


def _score_color(score: float) -> str:
    if score >= 75:
        return "green"
    elif score >= 60:
        return "cyan"
    elif score >= 45:
        return "yellow"
    else:
        return "red"


def _rating_style(rating: str) -> str:
    styles = {
        "强烈推荐": "bold green",
        "推荐": "bold cyan",
        "中性": "bold yellow",
        "回避": "bold red",
    }
    return styles.get(rating, "bold white")


def print_report(report: FinalReport):
    """在终端输出完整的分析报告。"""
    console.print()

    # ── 标题栏 ──
    title = f"📊 港股 IPO 打新分析报告 | Phase {report.phase}"
    console.rule(title, style="bold blue")
    console.print()

    # ── 公司信息 ──
    info_panel = Panel(
        f"[bold]{report.company_name}[/bold] ({report.stock_code})\n"
        f"行业: {report.industry or '未分类'}",
        title="🏢 公司信息",
        border_style="blue",
    )
    console.print(info_panel)

    # ── 综合评分 ──
    score_text = Text()
    score_text.append(f"\n  综合评分: ", style="bold")
    score_text.append(f"{report.total_score:.1f}", style=f"bold {_score_color(report.total_score)}")
    score_text.append(f" / 100\n", style="bold")
    score_text.append(f"  投资建议: ", style="bold")
    score_text.append(f"{report.rating}", style=_rating_style(report.rating))

    if report.original_rating:
        score_text.append(f"\n  ⚠️ 原评级 [{report.original_rating}] → 因降级红线降至 [{report.rating}]",
                          style="bold red")
    if report.phase1_score is not None:
        delta = report.total_score - report.phase1_score
        arrow = "↑" if delta > 0 else "↓" if delta < 0 else "→"
        score_text.append(f"\n  Phase1→2 变化: {report.phase1_score:.1f} → {report.total_score:.1f} ({arrow}{abs(delta):.1f})",
                          style="bold")

    console.print(Panel(score_text, title="🎯 综合评分", border_style="green"))

    # ── 降级警告 ──
    if report.downgrade_reasons:
        console.print()
        for reason in report.downgrade_reasons:
            console.print(f"  🚨 [bold red]{reason}[/bold red]")
        console.print()

    # ── 各维度详情表 ──
    table = Table(title="📋 各维度评分详情", show_header=True, header_style="bold magenta")
    table.add_column("维度", style="bold", width=16)
    table.add_column("评分", justify="center", width=8)
    table.add_column("权重", justify="center", width=8)
    table.add_column("加权得分", justify="center", width=10)
    table.add_column("数据", justify="center", width=6)
    table.add_column("核心分析", width=50)

    for ds in sorted(report.dimension_scores, key=lambda x: x.weight, reverse=True):
        color = _score_color(ds.score)
        weighted = ds.score * ds.weight
        data_status = "✅" if ds.data_sufficient else "⚠️"
        analysis_short = ds.analysis[:60] + "..." if len(ds.analysis) > 60 else ds.analysis

        table.add_row(
            ds.display_name,
            f"[{color}]{ds.score:.0f}[/{color}]",
            f"{ds.weight:.0%}",
            f"{weighted:.1f}",
            data_status,
            analysis_short,
        )

    console.print(table)

    # ── 子指标详情 ──
    console.print()
    for ds in report.dimension_scores:
        if ds.sub_scores:
            sub_table = Table(title=f"  {ds.display_name} 子指标",
                              show_header=True, header_style="dim")
            sub_table.add_column("指标", width=20)
            sub_table.add_column("评分", justify="center", width=8)
            sub_table.add_column("说明", width=50)

            for ss in ds.sub_scores:
                color = _score_color(ss.score)
                sub_table.add_row(
                    ss.name,
                    f"[{color}]{ss.score:.0f}[/{color}]",
                    ss.detail,
                )
            console.print(sub_table)
            console.print()

    # ── 行业专属指标 ──
    if report.industry_specific_scores:
        console.print(Panel(
            "\n".join(f"  {s.name}: [{_score_color(s.score)}]{s.score:.0f}[/{_score_color(s.score)}] — {s.detail}"
                      for s in report.industry_specific_scores),
            title=f"🏭 行业专属指标 ({report.industry or '通用'})",
            border_style="cyan",
        ))

    # ── 卖出时机建议 ──
    if report.sell_timing:
        st = report.sell_timing
        strat_labels = {
            "quick_flip": "⚡ 速战速决",
            "short_hold": "📈 短线持有",
            "medium_hold": "🏦 中线持有",
        }
        conf_labels = {"high": "高", "medium": "中", "low": "低"}
        timing_text = (
            f"  策略: [bold cyan]{strat_labels.get(st.strategy, st.strategy)}[/bold cyan]\n"
            f"  建议持有: ≤{st.suggested_days}天\n"
            f"  止损线: [red]{st.stop_loss_pct}%[/red]  止盈目标: [green]+{st.take_profit_pct}%[/green]\n"
            f"  逻辑: {st.rationale}\n"
            f"  置信度: {conf_labels.get(st.confidence, st.confidence)}"
        )
        console.print(Panel(timing_text, title="💡 卖出时机建议", border_style="cyan"))

    # ── 概率预测区间（P3 新增）──
    if report.probability:
        prob = report.probability
        conf_labels = {"high": "高", "medium": "中", "low": "低"}
        prob_text = (
            f"  首日上涨概率: [bold green]{prob.first_day_up_prob:.1f}%[/bold green]"
            f"  首日下跌概率: [bold red]{prob.first_day_down_prob:.1f}%[/bold red]\n"
            f"  预期收益区间: [red]{prob.expected_return_low:+.1f}%[/red]"
            f" ~ [bold]{prob.expected_return_mid:+.1f}%[/bold]"
            f" ~ [green]{prob.expected_return_high:+.1f}%[/green]\n"
            f"  置信度: {conf_labels.get(prob.confidence_level, prob.confidence_level)}\n"
            f"  方法: {prob.methodology}"
        )
        console.print(Panel(prob_text, title="🎲 概率预测区间", border_style="magenta"))

    # ── 中签率估算（P3 新增）──
    if report.allotment:
        allot = report.allotment
        allot_parts = []
        if allot.estimated_allocation_rate is not None:
            allot_parts.append(f"  估算中签率: [bold]{allot.estimated_allocation_rate:.2f}%[/bold]")
        if allot.estimated_one_hand_win_rate is not None:
            allot_parts.append(f"  一手中签率: [bold cyan]{allot.estimated_one_hand_win_rate:.1f}%[/bold cyan]")
        if allot.optimal_hands is not None:
            allot_parts.append(f"  建议认购: [bold]{allot.optimal_hands} 手[/bold]")
        if allot.expected_profit_per_hand is not None:
            color = "green" if allot.expected_profit_per_hand > 0 else "red"
            allot_parts.append(f"  每手预期盈利: [{color}]HK${allot.expected_profit_per_hand:,.0f}[/{color}]")
        if allot.capital_required is not None:
            allot_parts.append(f"  所需本金: HK${allot.capital_required:,.0f}")
        if allot.capital_efficiency is not None:
            allot_parts.append(f"  资金效率(年化): {allot.capital_efficiency:.1f}%")
        if allot.methodology:
            allot_parts.append(f"  [dim]{allot.methodology}[/dim]")
        if allot_parts:
            console.print(Panel("\n".join(allot_parts), title="🎯 中签率估算", border_style="yellow"))

    # ── 摘要 ──
    console.print(Panel(report.summary, title="📝 分析摘要", border_style="blue"))
    console.rule(style="dim")
