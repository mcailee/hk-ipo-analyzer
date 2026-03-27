"""医药行业专属分析器。"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from analyzers.industry_specific.base import IndustrySpecificAnalyzer
from models.ipo_data import IPOData, SubScore
from utils.helpers import safe_float, safe_int


class PharmaAnalyzer(IndustrySpecificAnalyzer):
    industry_name = "医药"

    def analyze(self, data: IPOData) -> list[SubScore]:
        d = data.industry_specific.data if data.industry_specific else {}
        subs = []

        # 管线数量
        pipeline_count = safe_int(d.get("pipeline_count"))
        if pipeline_count is not None:
            if pipeline_count >= 10:
                s = 85
            elif pipeline_count >= 5:
                s = 70
            elif pipeline_count >= 2:
                s = 50
            else:
                s = 30
            subs.append(SubScore("管线数量", s, f"在研管线 {pipeline_count} 个", pipeline_count))

        # 核心产品临床阶段
        stage = d.get("core_product_stage", "").upper()
        stage_scores = {"NDA": 90, "III": 80, "II": 60, "I": 40, "PRE": 25}
        for k, v in stage_scores.items():
            if k in stage:
                subs.append(SubScore("核心产品阶段", v, f"核心产品处于 {stage} 阶段"))
                break

        # 适应症市场空间
        market_size = safe_float(d.get("indication_market_size_usd"))
        if market_size is not None:
            if market_size >= 10:  # 十亿美元
                s = 90
            elif market_size >= 5:
                s = 75
            elif market_size >= 1:
                s = 55
            else:
                s = 35
            subs.append(SubScore("适应症市场", s,
                                 f"核心适应症市场 ${market_size:.0f}B", market_size))

        # 研发费用率
        rd_ratio = safe_float(d.get("rd_expense_ratio"))
        if rd_ratio is not None:
            if 20 <= rd_ratio <= 50:
                s = 75
            elif rd_ratio > 50:
                s = 55  # 烧钱过猛
            elif rd_ratio >= 10:
                s = 60
            else:
                s = 40
            subs.append(SubScore("研发费用率", s, f"研发费用率 {rd_ratio:.0f}%", rd_ratio))

        # 首创 vs 仿制（不设默认值，数据缺失时跳过）
        is_innovative = d.get("is_innovative")
        if is_innovative is not None:
            s = 80 if is_innovative else 45
            subs.append(SubScore("创新属性", s,
                                 "以创新药为主" if is_innovative else "以仿制/改良为主"))

        return subs
