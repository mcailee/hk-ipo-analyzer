#!/usr/bin/env python3
"""Phase2 更新入口 — 认购期补充热度数据并二次评分。

v3.0 新增:
  - 同批次新股横向对比参数
  - A+H 股分析参数
  - 暗盘数据输入
  - 概率预测区间输出
  - 中签率计算器输出
"""

import sys
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import click
from pathlib import Path


@click.command()
@click.argument("stock_code")
# ── 认购数据（传统机制A）──
@click.option("--public-mult", type=float, default=None, help="公开认购倍数")
@click.option("--intl-mult", type=float, default=None, help="国际配售倍数")
@click.option("--clawback/--no-clawback", default=None, help="是否触发回拨（机制A）")
@click.option("--concurrent", type=int, default=None, help="同期上市新股数量")
@click.option("--break-rate", type=float, default=None, help="近期新股破发率(%)")
@click.option("--allocation-rate", type=float, default=None, help="中签率(%)")
# ── 机制A/B 选择 ──
@click.option("--mechanism", type=click.Choice(["A", "B"]), default=None, help="IPO定价机制(A=传统/B=新机制)")
# ── 机制B 专属参数 ──
@click.option("--mech-b-price-pos", type=float, default=None, help="[机制B] 定价相对指示区间位置(0-1)")
@click.option("--mech-b-inst-orders", type=float, default=None, help="[机制B] 机构下单倍数")
@click.option("--mech-b-retail-mult", type=float, default=None, help="[机制B] 散户意向认购倍数")
# ── 流动性数据 ──
@click.option("--free-float-cap", type=float, default=None, help="自由流通市值(百万港元)")
@click.option("--hk-connect/--no-hk-connect", default=None, help="是否可能纳入港股通")
@click.option("--market-maker/--no-market-maker", default=None, help="是否有做市商")
@click.option("--daily-turnover", type=float, default=None, help="预估日均成交(百万港元)")
# ── 市场情绪数据 ──
@click.option("--hsi-1m-change", type=float, default=None, help="恒指近1月涨跌幅(%)")
@click.option("--ipo-break-rate-30d", type=float, default=None, help="近30日IPO破发率(%)")
@click.option("--southbound-flow", type=float, default=None, help="南向资金净流入(亿港元)")
@click.option("--hsi-volatility", type=float, default=None, help="恒指波动率(%)")
# ── P2: 暗盘数据 ──
@click.option("--grey-market-price", type=float, default=None, help="暗盘价格(港元)")
@click.option("--grey-market-volume", type=float, default=None, help="暗盘成交量(手)")
@click.option("--grey-market-turnover", type=float, default=None, help="暗盘成交额(百万港元)")
@click.option("--grey-market-source", type=str, default=None, help="暗盘数据来源(辉立/耀才)")
# ── P2: A+H 股参数 ──
@click.option("--a-stock-code", type=str, default=None, help="对应A股代码")
@click.option("--a-stock-price", type=float, default=None, help="A股当前价格(CNY)")
@click.option("--ah-premium", type=float, default=None, help="A/H溢价率(%)")
@click.option("--a-share-pe", type=float, default=None, help="A股PE")
# ── P2: 同批次对比 ──
@click.option("--batch-break-rate", type=float, default=None, help="同批次新股破发率(%)")
@click.option("--batch-avg-return", type=float, default=None, help="同批次平均首日涨幅(%)")
@click.option("--batch-avg-mult", type=float, default=None, help="同批次平均认购倍数")
@click.option("--batch-total", type=int, default=None, help="同批次新股总数")
# ── 输出 ──
@click.option("--output", default=None, help="输出目录（需与 Phase1 一致）")
def update(stock_code, public_mult, intl_mult, clawback, concurrent,
           break_rate, allocation_rate, mechanism,
           mech_b_price_pos, mech_b_inst_orders, mech_b_retail_mult,
           free_float_cap, hk_connect, market_maker, daily_turnover,
           hsi_1m_change, ipo_break_rate_30d, southbound_flow, hsi_volatility,
           grey_market_price, grey_market_volume, grey_market_turnover, grey_market_source,
           a_stock_code, a_stock_price, ah_premium, a_share_pe,
           batch_break_rate, batch_avg_return, batch_avg_mult, batch_total,
           output):
    """港股 IPO 打新分析（Phase 2 — 认购期更新）。

    STOCK_CODE: 港股股票代码

    支持机制A（传统）和机制B（2025.08改革后）两种定价模式。
    """
    from rich.console import Console

    from models.ipo_data import (
        IPOData, SubscriptionInfo, LiquidityInfo, MarketSentimentInfo, FinalReport,
        GreyMarketInfo, AHStockInfo, PeerComparisonInfo,
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
    data = IPOData()
    # 补充 Phase2 数据
    data.subscription = SubscriptionInfo(
        public_subscription_mult=public_mult,
        intl_placement_mult=intl_mult,
        clawback_triggered=clawback,
        concurrent_ipos=concurrent,
        recent_break_rate=break_rate,
        pricing_mechanism=mechanism,
        mech_b_price_vs_range=mech_b_price_pos,
        mech_b_institutional_orders=mech_b_inst_orders,
        mech_b_retail_indicated_mult=mech_b_retail_mult,
        allocation_rate=allocation_rate,
    )
    data.liquidity = LiquidityInfo(
        free_float_market_cap=free_float_cap,
        hk_connect_eligible=hk_connect,
        has_market_maker=market_maker,
        estimated_daily_turnover=daily_turnover,
    )
    data.market_sentiment = MarketSentimentInfo(
        hsi_1m_change=hsi_1m_change,
        ipo_break_rate_30d=ipo_break_rate_30d,
        southbound_net_flow=southbound_flow,
        hsi_volatility=hsi_volatility,
    )

    # P2/P3 新增数据
    # 暗盘数据
    if grey_market_price is not None:
        offer_price = data.valuation.final_price if hasattr(data.valuation, 'final_price') else None
        gm_premium = None
        if offer_price and offer_price > 0:
            gm_premium = (grey_market_price - offer_price) / offer_price * 100
        data.grey_market = GreyMarketInfo(
            grey_market_price=grey_market_price,
            offer_price=offer_price,
            grey_market_premium=gm_premium,
            grey_market_volume=grey_market_volume,
            grey_market_turnover=grey_market_turnover,
            data_source=grey_market_source,
        )

    # A+H 股数据
    if a_stock_code is not None:
        data.ah_stock = AHStockInfo(
            has_a_share=True,
            a_stock_code=a_stock_code,
            a_stock_price=a_stock_price,
            ah_premium=ah_premium,
            a_share_pe=a_share_pe,
            h_share_pe=data.valuation.pe_ratio if hasattr(data.valuation, 'pe_ratio') else None,
        )

    # 同批次新股对比
    if batch_total is not None or batch_break_rate is not None:
        data.peer_comparison = PeerComparisonInfo(
            batch_break_rate=batch_break_rate,
            batch_avg_first_day_return=batch_avg_return,
            batch_avg_subscription_mult=batch_avg_mult,
            total_in_batch=batch_total,
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
        data.valuation.total_shares = val.get("total_shares")
        fin = phase1_data_raw.get("financial", {})
        data.financial.revenue_cagr = fin.get("revenue_cagr")
        data.financial.net_margin = fin.get("net_margin")
        data.financial.gross_margin = fin.get("gross_margin")
        data.financial.debt_ratio = fin.get("debt_ratio")
        data.financial.roe = fin.get("roe")
        data.financial.net_assets = fin.get("net_assets")
        # 恢复承销信息（发行规模评估需要）
        uw = phase1_data_raw.get("underwriting", {})
        data.underwriting.offer_size = uw.get("offer_size")
        data.underwriting.sponsor = uw.get("sponsor")
        # 恢复市场情绪（如果Phase1已有，Phase2未提供则继承）
        sent_raw = phase1_data_raw.get("market_sentiment", {})
        if hsi_1m_change is None and sent_raw.get("hsi_1m_change") is not None:
            data.market_sentiment.hsi_1m_change = sent_raw["hsi_1m_change"]
        if ipo_break_rate_30d is None and sent_raw.get("ipo_break_rate_30d") is not None:
            data.market_sentiment.ipo_break_rate_30d = sent_raw["ipo_break_rate_30d"]
        if southbound_flow is None and sent_raw.get("southbound_net_flow") is not None:
            data.market_sentiment.southbound_net_flow = sent_raw["southbound_net_flow"]
        if hsi_volatility is None and sent_raw.get("hsi_volatility") is not None:
            data.market_sentiment.hsi_volatility = sent_raw["hsi_volatility"]

    # 运行全部分析器（含条件性维度）
    all_analyzers = get_phase1_analyzers() + get_phase2_analyzers()
    dim_scores = []
    for analyzer in all_analyzers:
        try:
            score = analyzer.analyze(data, config)
            dim_scores.append(score)
        except Exception as e:
            logger.warning(f"{analyzer.dimension_name} 分析异常: {e}")
            dim_weight = config["dimensions"].get(analyzer.dimension_key, {}).get("weight", 0)
            dim_scores.append(analyzer.handle_missing(dim_weight))

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

    # 评分（含卖出时机建议 + 概率预测 + 中签率计算）
    scorer = Scorer(config)
    report = scorer.score_phase2(data, dim_scores, phase1_report)

    # 输出
    print_report(report)

    # 卖出时机建议
    if report.sell_timing:
        st = report.sell_timing
        console.print()
        console.print("[bold cyan]💡 卖出时机建议[/bold cyan]")
        console.print(f"  策略: {st.strategy} ({st.rationale})")
        console.print(f"  建议持有: ≤{st.suggested_days}天")
        console.print(f"  止损线: {st.stop_loss_pct}%  止盈线: +{st.take_profit_pct}%")
        console.print(f"  置信度: {st.confidence}")

    # 概率预测区间（P3 新增）
    if report.probability:
        prob = report.probability
        console.print()
        console.print("[bold magenta]🎲 概率预测[/bold magenta]")
        console.print(f"  首日上涨概率: {prob.first_day_up_prob:.1f}%  下跌概率: {prob.first_day_down_prob:.1f}%")
        console.print(f"  预期收益区间: {prob.expected_return_low:+.1f}% ~ {prob.expected_return_mid:+.1f}% ~ {prob.expected_return_high:+.1f}%")
        console.print(f"  置信度: {prob.confidence_level}  方法: {prob.methodology}")

    # 中签率估算（P3 新增）
    if report.allotment and report.allotment.estimated_allocation_rate is not None:
        allot = report.allotment
        console.print()
        console.print("[bold yellow]🎯 中签率估算[/bold yellow]")
        console.print(f"  基础中签率: {allot.estimated_allocation_rate:.2f}%")
        if allot.estimated_one_hand_win_rate is not None:
            console.print(f"  一手中签率: {allot.estimated_one_hand_win_rate:.1f}%")
        console.print(f"  建议认购: {allot.optimal_hands} 手  所需本金: HK${allot.capital_required:,.0f}")
        if allot.expected_profit_per_hand is not None:
            console.print(f"  每手预期盈利: HK${allot.expected_profit_per_hand:,.0f}")
        if allot.capital_efficiency is not None:
            console.print(f"  资金效率(年化): {allot.capital_efficiency:.1f}%")

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
