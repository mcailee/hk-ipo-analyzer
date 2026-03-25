"""公司基本面分析器（8%）。"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from analyzers.base import BaseAnalyzer
from models.ipo_data import IPOData, DimensionScore, SubScore
from datetime import datetime


class CompanyAnalyzer(BaseAnalyzer):
    dimension_key = "company"
    dimension_name = "公司基本面"

    def analyze(self, data: IPOData, config: dict) -> DimensionScore:
        weight = config["dimensions"]["company"]["weight"]
        c = data.company
        subs = []

        # 成立年限
        if c.founded_year:
            years = datetime.now().year - c.founded_year
            if years >= 10:
                s = 85
            elif years >= 5:
                s = 70
            elif years >= 3:
                s = 55
            else:
                s = 35
            subs.append(SubScore("成立年限", s, f"成立 {years} 年", years))
        else:
            subs.append(SubScore("成立年限", 50, "数据缺失"))

        # 主营业务清晰度
        if c.main_business and len(c.main_business) > 20:
            subs.append(SubScore("业务清晰度", 75, "业务描述清晰"))
        else:
            subs.append(SubScore("业务清晰度", 50, "业务描述不足"))

        # 员工规模
        if c.employee_count:
            if c.employee_count >= 5000:
                s = 80
            elif c.employee_count >= 1000:
                s = 70
            elif c.employee_count >= 200:
                s = 55
            else:
                s = 40
            subs.append(SubScore("员工规模", s, f"{c.employee_count} 人", c.employee_count))
        else:
            subs.append(SubScore("员工规模", 50, "数据缺失"))

        score = self.avg_scores(subs)
        analysis = self._build_analysis(c, score)

        return DimensionScore(
            dimension=self.dimension_key,
            display_name=self.dimension_name,
            score=self.cap_score(score),
            weight=weight,
            sub_scores=subs,
            analysis=analysis,
            data_sufficient=any(s.raw_value is not None for s in subs),
        )

    def _build_analysis(self, c, score):
        parts = []
        if c.name:
            parts.append(f"公司名称：{c.name}。")
        if c.main_business:
            parts.append(f"主营业务：{c.main_business[:100]}。")
        if score >= 70:
            parts.append("公司基本面整体良好，具备一定规模和成熟度。")
        elif score >= 50:
            parts.append("公司基本面中规中矩，需关注发展阶段和业务模式。")
        else:
            parts.append("公司基本面偏弱，成立时间较短或规模较小，风险较高。")
        return " ".join(parts)
