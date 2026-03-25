"""财务状况分析器（14%）。"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from analyzers.base import BaseAnalyzer
from models.ipo_data import IPOData, DimensionScore, SubScore
from utils.helpers import detect_industry, format_pct


class FinancialAnalyzer(BaseAnalyzer):
    dimension_key = "financial"
    dimension_name = "财务状况"

    def analyze(self, data: IPOData, config: dict) -> DimensionScore:
        weight = config["dimensions"]["financial"]["weight"]
        f = data.financial
        scoring = config.get("financial_scoring", {})
        subs = []

        # 营收增速
        if f.revenue_cagr is not None:
            s = self.score_by_range(f.revenue_cagr, scoring.get("revenue_cagr", []))
            subs.append(SubScore("营收增速", s, f"营收复合增速 {f.revenue_cagr:.1f}%", f.revenue_cagr))

        # 净利润率
        if f.net_margin is not None:
            s = self.score_by_range(f.net_margin, scoring.get("net_margin", []))
            subs.append(SubScore("净利润率", s, f"净利润率 {f.net_margin:.1f}%", f.net_margin))

        # 毛利率
        if f.gross_margin is not None:
            if f.gross_margin >= 60:
                s = 90
            elif f.gross_margin >= 40:
                s = 75
            elif f.gross_margin >= 25:
                s = 55
            else:
                s = 35
            subs.append(SubScore("毛利率", s, f"毛利率 {f.gross_margin:.1f}%", f.gross_margin))

        # 资产负债率
        if f.debt_ratio is not None:
            s = self.score_by_range(f.debt_ratio, scoring.get("debt_ratio", []))
            subs.append(SubScore("资产负债率", s, f"资产负债率 {f.debt_ratio:.1f}%", f.debt_ratio))

        # ROE
        if f.roe is not None:
            s = self.score_by_range(f.roe, scoring.get("roe", []))
            subs.append(SubScore("ROE", s, f"ROE {f.roe:.1f}%", f.roe))

        # 经营现金流
        if f.operating_cashflow is not None:
            if f.operating_cashflow > 0:
                s = 75
            else:
                s = 30
            subs.append(SubScore("经营现金流", s,
                                 f"经营现金流 {'正' if f.operating_cashflow > 0 else '负'}",
                                 f.operating_cashflow))

        # 行业专属财务指标
        industry_type = detect_industry(data.company.industry, config)
        if industry_type:
            from analyzers.industry_specific import get_industry_analyzer
            ind = get_industry_analyzer(industry_type)
            if ind:
                ind_subs = ind.analyze(data)
                subs.extend(ind_subs)

        if not subs:
            return self.handle_missing(weight)

        score = self.avg_scores(subs)
        analysis = self._build_analysis(f, score)

        return DimensionScore(
            dimension=self.dimension_key,
            display_name=self.dimension_name,
            score=self.cap_score(score),
            weight=weight,
            sub_scores=subs,
            analysis=analysis,
            data_sufficient=len(subs) >= 3,
        )

    def _build_analysis(self, f, score):
        parts = []
        if f.revenue_cagr is not None:
            parts.append(f"营收增速 {f.revenue_cagr:.1f}%。")
        if f.net_margin is not None:
            parts.append(f"净利润率 {f.net_margin:.1f}%。")

        if score >= 75:
            parts.append("财务状况优秀，盈利能力强，成长性好。")
        elif score >= 55:
            parts.append("财务状况良好，各项指标处于中上水平。")
        elif score >= 40:
            parts.append("财务状况一般，部分指标存在隐忧。")
        else:
            parts.append("财务状况较差，盈利能力弱或亏损，需谨慎。")
        return " ".join(parts)
