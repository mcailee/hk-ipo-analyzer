"""法律诉讼分析器（1% + 降级红线）。"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from analyzers.base import BaseAnalyzer
from models.ipo_data import IPOData, DimensionScore, SubScore


class LegalAnalyzer(BaseAnalyzer):
    dimension_key = "legal"
    dimension_name = "法律诉讼"

    def analyze(self, data: IPOData, config: dict) -> DimensionScore:
        weight = config["dimensions"]["legal"]["weight"]
        lg = data.legal
        red_flag_cfg = config.get("legal_red_flags", {})
        subs = []
        red_flags = []

        # 涉诉数量
        if lg.total_cases is not None:
            if lg.total_cases == 0:
                subs.append(SubScore("涉诉数量", 90, "无诉讼记录", 0))
            elif lg.total_cases <= 3:
                subs.append(SubScore("涉诉数量", 65, f"{lg.total_cases} 件诉讼", lg.total_cases))
            else:
                subs.append(SubScore("涉诉数量", 35, f"{lg.total_cases} 件诉讼，偏多", lg.total_cases))
        else:
            subs.append(SubScore("涉诉数量", 60, "诉讼信息缺失"))

        # 涉诉金额 vs 净资产
        if lg.total_amount is not None and data.financial.net_assets:
            ratio = lg.total_amount / data.financial.net_assets
            threshold = red_flag_cfg.get("litigation_to_net_asset_ratio", 0.20)
            if ratio > threshold:
                subs.append(SubScore("涉诉金额", 15,
                                     f"涉诉金额占净资产 {ratio:.0%} ⚠️ 触发红线", ratio))
                red_flags.append(f"涉诉金额占净资产 {ratio:.0%}，超过 {threshold:.0%} 红线")
            elif ratio > 0.05:
                subs.append(SubScore("涉诉金额", 50, f"涉诉金额占净资产 {ratio:.1%}", ratio))
            else:
                subs.append(SubScore("涉诉金额", 80, f"涉诉金额占净资产仅 {ratio:.1%}", ratio))

        # 刑事诉讼
        if lg.has_criminal_case:
            subs.append(SubScore("刑事诉讼", 5, "⚠️ 存在刑事诉讼，严重风险"))
            red_flags.append("存在刑事诉讼")

        # 监管立案调查
        if lg.has_regulatory_investigation:
            subs.append(SubScore("监管调查", 10, "⚠️ 被监管部门立案调查"))
            red_flags.append("被监管部门立案调查")

        if not subs:
            return self.handle_missing(weight)

        score = self.avg_scores(subs)
        analysis = f"法律诉讼评分 {score:.0f} 分。"
        if red_flags:
            analysis += f" 🚨 触发降级红线: {'; '.join(red_flags)}。"
        elif score >= 70:
            analysis += "法律风险较低。"
        else:
            analysis += "存在一定法律风险，需关注。"

        return DimensionScore(
            dimension=self.dimension_key,
            display_name=self.dimension_name,
            score=self.cap_score(score),
            weight=weight,
            sub_scores=subs,
            analysis=analysis,
            data_sufficient=True,
            red_flags=red_flags,
        )
