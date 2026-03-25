"""A+H 股分析模块（P2 新增）。

对有 A 股对应标的的港股 IPO，分析 A/H 溢价率、
估值差异、套利空间等，为投资决策提供额外参考维度。

子指标：
  1. A/H 溢价率评估
  2. 估值折让（H股PE vs A股PE）
  3. 行业 A/H 溢价对标
  4. A股流动性（换手率）参考
"""
from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from analyzers.base import BaseAnalyzer
from models.ipo_data import IPOData, DimensionScore, SubScore


class AHStockAnalyzer(BaseAnalyzer):
    dimension_key = "ah_stock"
    dimension_name = "A+H股分析"

    def analyze(self, data: IPOData, config: dict) -> DimensionScore:
        weight = config["dimensions"].get("ah_stock", {}).get("weight", 0.0)
        ah = data.ah_stock
        scoring = config.get("ah_stock_scoring", {})
        subs = []

        # 如果没有 A 股对标，返回中性（不参与加权）
        if not ah.has_a_share:
            return DimensionScore(
                dimension=self.dimension_key,
                display_name=self.dimension_name,
                score=50.0,
                weight=0.0,  # 无 A 股时权重设为 0，不影响总分
                sub_scores=[],
                analysis="该标的无对应A股，A+H分析不适用。",
                data_sufficient=False,
            )

        # 1. A/H 溢价率评估
        if ah.ah_premium is not None:
            s = self.score_by_range(ah.ah_premium,
                                     scoring.get("ah_premium", []))
            if ah.ah_premium > 0:
                desc = f"A股溢价 {ah.ah_premium:.1f}%（H股更便宜，打新有折价保护）"
            elif ah.ah_premium > -10:
                desc = f"A/H价差较小（{ah.ah_premium:.1f}%），估值接近"
            else:
                desc = f"H股溢价 {abs(ah.ah_premium):.1f}%（H股偏贵，打新需谨慎）"
            subs.append(SubScore("A/H溢价率", s, desc, ah.ah_premium))

        # 2. 估值折让（H vs A PE）
        if ah.a_share_pe is not None and ah.h_share_pe is not None and ah.a_share_pe > 0:
            pe_discount = (ah.h_share_pe - ah.a_share_pe) / ah.a_share_pe * 100
            s = self.score_by_range(pe_discount,
                                     scoring.get("pe_discount_ah", []))
            if pe_discount < 0:
                desc = f"H股PE {ah.h_share_pe:.1f}x vs A股 {ah.a_share_pe:.1f}x，折让 {abs(pe_discount):.1f}%"
            else:
                desc = f"H股PE {ah.h_share_pe:.1f}x vs A股 {ah.a_share_pe:.1f}x，溢价 {pe_discount:.1f}%"
            subs.append(SubScore("H/A估值折让", s, desc, pe_discount))

        # 3. 行业平均 A/H 溢价对标
        if ah.sector_avg_ah_premium is not None and ah.ah_premium is not None:
            diff = ah.ah_premium - ah.sector_avg_ah_premium
            if diff > 10:
                s = 80  # 当前A股溢价高于行业均值 → H股更便宜
                desc = f"A股溢价高于行业均值 {diff:.1f}个百分点，H股IPO折价吸引力更大"
            elif diff > 0:
                s = 65
                desc = f"A股溢价略高于行业均值（+{diff:.1f}%pt）"
            elif diff > -10:
                s = 50
                desc = f"A/H溢价与行业均值接近（{diff:.1f}%pt）"
            else:
                s = 35
                desc = f"A股溢价低于行业均值 {abs(diff):.1f}个百分点，H股吸引力不足"
            subs.append(SubScore("行业AH对标", s, desc, diff))

        # 4. A股流动性参考
        if ah.a_share_turnover_rate is not None:
            if ah.a_share_turnover_rate > 5:
                s = 75
                desc = f"A股日均换手率 {ah.a_share_turnover_rate:.1f}%（高活跃度，市场关注度高）"
            elif ah.a_share_turnover_rate > 2:
                s = 65
                desc = f"A股日均换手率 {ah.a_share_turnover_rate:.1f}%（正常活跃）"
            elif ah.a_share_turnover_rate > 0.5:
                s = 55
                desc = f"A股日均换手率 {ah.a_share_turnover_rate:.1f}%（偏低）"
            else:
                s = 40
                desc = f"A股日均换手率 {ah.a_share_turnover_rate:.1f}%（低迷，市场关注度不高）"
            subs.append(SubScore("A股流动性", s, desc, ah.a_share_turnover_rate))

        if not subs:
            return self.handle_missing(weight)

        score = self.avg_scores(subs)
        analysis = self._build_analysis(ah, score)

        return DimensionScore(
            dimension=self.dimension_key,
            display_name=self.dimension_name,
            score=self.cap_score(score),
            weight=weight,
            sub_scores=subs,
            analysis=analysis,
            data_sufficient=len(subs) >= 2,
        )

    def _build_analysis(self, ah, score):
        parts = []
        if ah.a_stock_code:
            parts.append(f"对应A股: {ah.a_stock_code}。")
        if ah.ah_premium is not None:
            if ah.ah_premium > 20:
                parts.append(f"A股相对H股溢价 {ah.ah_premium:.0f}%，H股IPO存在显著折价保护。")
            elif ah.ah_premium > 0:
                parts.append(f"A/H存在一定溢价（{ah.ah_premium:.0f}%），H股有一定折价空间。")
            else:
                parts.append(f"H股相对A股无折价优势。")

        if score >= 70:
            parts.append("A+H维度分析积极，H股IPO具有估值吸引力。")
        elif score >= 50:
            parts.append("A+H维度中性，需结合其他因素综合判断。")
        else:
            parts.append("A+H维度偏负面，H股估值不具备明显优势。")
        return " ".join(parts)
