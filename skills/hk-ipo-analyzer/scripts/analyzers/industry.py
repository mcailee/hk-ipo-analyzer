"""行业竞争分析器（12%）。"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from analyzers.base import BaseAnalyzer
from models.ipo_data import IPOData, DimensionScore, SubScore
from utils.helpers import detect_industry


class IndustryAnalyzer(BaseAnalyzer):
    dimension_key = "industry"
    dimension_name = "行业竞争"

    def analyze(self, data: IPOData, config: dict) -> DimensionScore:
        weight = config["dimensions"]["industry"]["weight"]
        subs = []

        industry = data.company.industry or ""
        industry_type = detect_industry(industry, config)

        # 行业景气度（基于行业分类简单评估）
        hot_industries = ["人工智能", "AI", "半导体", "新能源", "SaaS", "云计算", "创新药"]
        cold_industries = ["房地产", "传统零售", "煤炭", "钢铁"]
        if any(h in industry for h in hot_industries):
            subs.append(SubScore("行业景气度", 85, f"热门赛道: {industry}"))
        elif any(c in industry for c in cold_industries):
            subs.append(SubScore("行业景气度", 30, f"低迷行业: {industry}"))
        elif industry:
            subs.append(SubScore("行业景气度", 60, f"行业: {industry}"))
        else:
            subs.append(SubScore("行业景气度", 50, "行业信息缺失"))

        # 行业专属指标补充
        if industry_type:
            from analyzers.industry_specific import get_industry_analyzer
            ind_analyzer = get_industry_analyzer(industry_type)
            if ind_analyzer:
                ind_subs = ind_analyzer.analyze(data)
                subs.extend(ind_subs)

        score = self.avg_scores(subs)
        analysis = f"所属行业：{industry or '未知'}。"
        if score >= 70:
            analysis += "行业景气度较高，市场空间广阔。"
        elif score >= 50:
            analysis += "行业表现中性，需关注细分赛道定位。"
        else:
            analysis += "行业景气度偏低，整体市场环境不利。"

        return DimensionScore(
            dimension=self.dimension_key,
            display_name=self.dimension_name,
            score=self.cap_score(score),
            weight=weight,
            sub_scores=subs,
            analysis=analysis,
            data_sufficient=bool(industry),
        )
