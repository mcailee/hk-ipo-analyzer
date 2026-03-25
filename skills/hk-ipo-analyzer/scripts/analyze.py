#!/usr/bin/env python3
"""Phase1 分析入口 — 招股期基本面分析。"""

import sys
import os

# 确保 scripts/ 在 Python 路径中
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import click
from pathlib import Path


@click.command()
@click.argument("stock_code")
@click.option("--pdf", default=None, help="招股书 PDF 文件路径")
@click.option("--output", default=None, help="输出目录（默认 ./output/{code}_{date}/）")
@click.option("--no-html", is_flag=True, help="不生成 HTML 报告")
@click.option("--no-chart", is_flag=True, help="不生成雷达图")
def analyze(stock_code: str, pdf: str, output: str, no_html: bool, no_chart: bool):
    """港股 IPO 打新分析（Phase 1 — 招股期基本面）。

    STOCK_CODE: 港股股票代码，如 9999 或 09999
    """
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn

    from models.ipo_data import IPOData
    from scrapers.hkex import HKEXScraper
    from scrapers.xueqiu import XueqiuScraper
    from analyzers import get_phase1_analyzers
    from scoring.scorer import Scorer
    from reports.terminal import print_report
    from reports.chart import generate_radar_chart
    from reports.html_report import generate_html_report
    from utils.helpers import get_config, get_output_dir, save_phase_data, save_report_json, logger

    console = Console()
    config = get_config()

    # 输出目录
    out_dir = Path(output) if output else get_output_dir(stock_code)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:

        # ── 数据采集 ──
        task = progress.add_task("📡 从港交所披露易获取数据...", total=None)
        data = IPOData()
        try:
            hkex = HKEXScraper(config)
            data = hkex.scrape(stock_code)
        except Exception as e:
            logger.warning(f"HKEX 爬取失败: {e}")
        progress.update(task, description="✅ 港交所数据获取完成")

        task2 = progress.add_task("📡 从雪球获取补充数据...", total=None)
        try:
            xueqiu = XueqiuScraper(config)
            data = xueqiu.scrape(stock_code, existing_data=data)
        except Exception as e:
            logger.warning(f"雪球爬取失败: {e}")
        progress.update(task2, description="✅ 雪球数据获取完成")

        # PDF 解析
        if pdf:
            task3 = progress.add_task("📄 解析招股书 PDF...", total=None)
            try:
                from scrapers.pdf_parser import PDFParser
                parser = PDFParser()
                data = parser.parse(pdf, existing_data=data)
            except Exception as e:
                logger.warning(f"PDF 解析失败: {e}")
            progress.update(task3, description="✅ PDF 解析完成")

        # ── 分析评分 ──
        task4 = progress.add_task("🔍 执行 9 维度基本面分析...", total=None)
        analyzers = get_phase1_analyzers()
        dim_scores = []
        for analyzer in analyzers:
            try:
                score = analyzer.analyze(data, config)
                dim_scores.append(score)
            except Exception as e:
                logger.warning(f"{analyzer.dimension_name} 分析异常: {e}")
                dim_scores.append(analyzer.handle_missing(
                    config["dimensions"][analyzer.dimension_key]["weight"]
                ))
        progress.update(task4, description="✅ 分析完成")

        # ── 评分 ──
        task5 = progress.add_task("📊 计算综合评分...", total=None)
        scorer = Scorer(config)
        report = scorer.score_phase1(data, dim_scores)
        progress.update(task5, description="✅ 评分完成")

    # ── 输出报告 ──
    console.print()
    print_report(report)

    # 雷达图
    chart_path = None
    if not no_chart:
        try:
            chart_path = generate_radar_chart(report, out_dir)
            console.print(f"\n📈 雷达图已保存: {chart_path}")
        except Exception as e:
            logger.warning(f"雷达图生成失败: {e}")

    # HTML 报告
    if not no_html:
        try:
            html_path = generate_html_report(report, out_dir, chart_path)
            console.print(f"📄 HTML 报告已保存: {html_path}")
        except Exception as e:
            logger.warning(f"HTML 报告生成失败: {e}")

    # 持久化 Phase1 数据
    save_phase_data(data, out_dir, phase=1)
    save_report_json(report, out_dir, phase=1)

    console.print(f"\n📁 输出目录: {out_dir}")
    console.print(f"\n💡 认购数据公布后，运行 Phase2 更新: update.py {stock_code}")


if __name__ == "__main__":
    analyze()
