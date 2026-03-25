#!/usr/bin/env python3
"""Phase2 更新入口 — 认购期补充热度数据并二次评分。"""

import sys
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import click
from pathlib import Path


@click.command()
@click.argument("stock_code")
@click.option("--public-mult", type=float, default=None, help="公开认购倍数")
@click.option("--intl-mult", type=float, default=None, help="国际配售倍数")
@click.option("--clawback/--no-clawback", default=None, help="是否触发回拨")
@click.option("--concurrent", type=int, default=None, help="同期上市新股数量")
@click.option("--break-rate", type=float, default=None, help="近期新股破发率(%)")
@click.option("--free-float-cap", type=float, default=None, help="自由流通市值(百万港元)")
@click.option("--hk-connect/--no-hk-connect", default=None, help="是否可能纳入港股通")
@click.option("--market-maker/--no-market-maker", default=None, help="是否有做市商")
@click.option("--daily-turnover", type=float, default=None, help="预估日均成交(百万港元)")
@click.option("--output", default=None, help="输出目录（需与 Phase1 一致）")
def update(stock_code, public_mult, intl_mult, clawback, concurrent,
           break_rate, free_float_cap, hk_connect, market_maker,
           daily_turnover, output):
    """港股 IPO 打新分析（Phase 2 — 认购期更新）。

    STOCK_CODE: 港股股票代码
    """
    from rich.console import Console

    from models.ipo_data import (
        IPOData, SubscriptionInfo, LiquidityInfo, FinalReport,
    )
    from analyzers import get_phase1_analyzers, get_phase2_analyzers
    from scoring.scorer import Scorer
    from reports.terminal import print_report
    from reports.chart import generate_radar_chart
    from reports.html_report import generate_html_report
    from utils.helpers import (
        get_config, get_output_dir, load_phase_data,
        save_phase_data, save_report_json, logger,
    )

    console = Console()
    config = get_config()

    # 查找 Phase1 输出目录
    out_dir = Path(output) if output else get_output_dir(stock_code)
    phase1_data_raw = load_phase_data(out_dir, phase=1)
    phase1_report_raw = None

    # 尝试加载 Phase1 报告
    phase1_report_path = out_dir / "phase1_report.json"
    if phase1_report_path.exists():
        import json
        with open(phase1_report_path, "r") as f:
            phase1_report_raw = json.load(f)

    if phase1_data_raw is None:
        console.print("[bold red]❌ 未找到 Phase1 数据。请先运行 analyze.py。[/bold red]")
        sys.exit(1)

    console.print(f"[bold green]✅ 已加载 Phase1 数据[/bold green]")

    # 重建 IPOData 并补充认购数据
    data = IPOData()  # 简化：从 Phase1 JSON 重建
    # 补充 Phase2 数据
    data.subscription = SubscriptionInfo(
        public_subscription_mult=public_mult,
        intl_placement_mult=intl_mult,
        clawback_triggered=clawback,
        concurrent_ipos=concurrent,
        recent_break_rate=break_rate,
    )
    data.liquidity = LiquidityInfo(
        free_float_market_cap=free_float_cap,
        hk_connect_eligible=hk_connect,
        has_market_maker=market_maker,
        estimated_daily_turnover=daily_turnover,
    )

    # 从 Phase1 JSON 恢复公司信息
    if phase1_data_raw:
        company = phase1_data_raw.get("company", {})
        data.company.name = company.get("name")
        data.company.stock_code = company.get("stock_code") or stock_code
        data.company.industry = company.get("industry")
        # 恢复其他关键数据
        val = phase1_data_raw.get("valuation", {})
        data.valuation.pe_ratio = val.get("pe_ratio")
        data.valuation.peer_avg_pe = val.get("peer_avg_pe")
        data.valuation.offer_price_low = val.get("offer_price_low")
        data.valuation.offer_price_high = val.get("offer_price_high")
        data.valuation.final_price = val.get("final_price")
        data.valuation.market_cap = val.get("market_cap")
        fin = phase1_data_raw.get("financial", {})
        data.financial.revenue_cagr = fin.get("revenue_cagr")
        data.financial.net_margin = fin.get("net_margin")
        data.financial.gross_margin = fin.get("gross_margin")
        data.financial.debt_ratio = fin.get("debt_ratio")
        data.financial.roe = fin.get("roe")
        data.financial.net_assets = fin.get("net_assets")

    # 运行全部 11 个分析器
    all_analyzers = get_phase1_analyzers() + get_phase2_analyzers()
    dim_scores = []
    for analyzer in all_analyzers:
        try:
            score = analyzer.analyze(data, config)
            dim_scores.append(score)
        except Exception as e:
            logger.warning(f"{analyzer.dimension_name} 分析异常: {e}")
            dim_scores.append(analyzer.handle_missing(
                config["dimensions"][analyzer.dimension_key]["weight"]
            ))

    # Phase1 报告用于对比
    phase1_report = None
    if phase1_report_raw:
        phase1_report = FinalReport(
            stock_code=phase1_report_raw.get("stock_code", stock_code),
            company_name=phase1_report_raw.get("company_name", ""),
            phase=1,
            total_score=phase1_report_raw.get("total_score", 0),
            rating=phase1_report_raw.get("rating", ""),
        )

    # 评分
    scorer = Scorer(config)
    report = scorer.score_phase2(data, dim_scores, phase1_report)

    # 输出
    print_report(report)

    try:
        chart_path = generate_radar_chart(report, out_dir)
        console.print(f"\n📈 雷达图已保存: {chart_path}")
    except Exception as e:
        logger.warning(f"雷达图生成失败: {e}")
        chart_path = None

    try:
        html_path = generate_html_report(report, out_dir, chart_path)
        console.print(f"📄 HTML 报告已保存: {html_path}")
    except Exception as e:
        logger.warning(f"HTML 报告生成失败: {e}")

    save_phase_data(data, out_dir, phase=2)
    save_report_json(report, out_dir, phase=2)

    console.print(f"\n📁 输出目录: {out_dir}")


if __name__ == "__main__":
    update()
