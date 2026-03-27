"""股东构成分析器（1%）。"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from analyzers.base import BaseAnalyzer
from models.ipo_data import IPOData, DimensionScore, SubScore


class ShareholderAnalyzer(BaseAnalyzer):
    dimension_key = "shareholder"
    dimension_name = "股东构成"

    def analyze(self, data: IPOData, config: dict) -> DimensionScore:
        weight = config["dimensions"]["shareholder"]["weight"]
        sh = data.shareholder
        subs = []

        # 实控人持股
        if sh.controller_stake is not None:
            if 30 <= sh.controller_stake <= 65:
                s = 80
                detail = f"实控人持股 {sh.controller_stake:.1f}%，比例合理"
            elif sh.controller_stake > 65:
                s = 55
                detail = f"实控人持股 {sh.controller_stake:.1f}%，集中度偏高"
            else:
                s = 45
                detail = f"实控人持股 {sh.controller_stake:.1f}%，控制力偏弱"
            subs.append(SubScore("实控人持股", s, detail, sh.controller_stake))

        # 同股不同权
        if sh.has_dual_class is not None:
            s = 55 if sh.has_dual_class else 70
            subs.append(SubScore("股权结构", s,
                                 "同股不同权（AB股）" if sh.has_dual_class else "同股同权"))

        # 代持风险
        if sh.has_trust_nominee is not None:
            s = 30 if sh.has_trust_nominee else 75
            subs.append(SubScore("代持风险", s,
                                 "存在代持安排，有治理风险" if sh.has_trust_nominee else "无代持"))

        if not subs:
            return self.handle_missing(weight)

        score = self.avg_scores(subs)
        return DimensionScore(
            dimension=self.dimension_key,
            display_name=self.dimension_name,
            score=self.cap_score(score),
            weight=weight,
            sub_scores=subs,
            analysis=f"股东构成综合评分 {score:.0f} 分。" +
                     ("结构清晰，治理风险较低。" if score >= 65 else "存在一定治理风险，需关注。"),
            data_sufficient=bool(subs),
        )
