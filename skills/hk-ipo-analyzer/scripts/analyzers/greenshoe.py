"""绿鞋机制分析器（5%）。"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from analyzers.base import BaseAnalyzer
from models.ipo_data import IPOData, DimensionScore, SubScore


class GreenshoeAnalyzer(BaseAnalyzer):
    dimension_key = "greenshoe"
    dimension_name = "绿鞋机制"

    def analyze(self, data: IPOData, config: dict) -> DimensionScore:
        weight = config["dimensions"]["greenshoe"]["weight"]
        gs = data.greenshoe
        subs = []

        # 是否有绿鞋
        if gs.has_greenshoe is not None:
            if gs.has_greenshoe:
                subs.append(SubScore("绿鞋设置", 80, "已设置绿鞋机制，有稳价保护"))
            else:
                subs.append(SubScore("绿鞋设置", 30, "未设置绿鞋机制，缺乏稳价保护"))
        else:
            subs.append(SubScore("绿鞋设置", 50, "绿鞋机制信息缺失"))

        # 超额配售比例
        if gs.overallotment_ratio is not None:
            if gs.overallotment_ratio >= 15:
                s = 85
            elif gs.overallotment_ratio >= 10:
                s = 70
            else:
                s = 55
            subs.append(SubScore("超额配售比例", s,
                                 f"超额配售权 {gs.overallotment_ratio:.1f}%",
                                 gs.overallotment_ratio))

        # 稳价期
        if gs.stabilization_period_days is not None:
            if gs.stabilization_period_days >= 30:
                s = 80
            else:
                s = 60
            subs.append(SubScore("稳价期", s,
                                 f"稳价期 {gs.stabilization_period_days} 天",
                                 gs.stabilization_period_days))

        score = self.avg_scores(subs)
        has_gs = gs.has_greenshoe if gs.has_greenshoe is not None else False
        return DimensionScore(
            dimension=self.dimension_key,
            display_name=self.dimension_name,
            score=self.cap_score(score),
            weight=weight,
            sub_scores=subs,
            analysis=f"{'已设置' if has_gs else '未设置'}绿鞋机制。" +
                     ("绿鞋保护充分，上市后价格有稳价机制支撑。" if score >= 70 else
                      "绿鞋保护一般。" if score >= 50 else
                      "缺乏绿鞋保护，上市首日破发风险较大。"),
            data_sufficient=gs.has_greenshoe is not None,
        )
