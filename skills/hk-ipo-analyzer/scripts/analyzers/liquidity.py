"""上市后流动性分析器（7%）。"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from analyzers.base import BaseAnalyzer
from models.ipo_data import IPOData, DimensionScore, SubScore


class LiquidityAnalyzer(BaseAnalyzer):
    dimension_key = "liquidity"
    dimension_name = "上市后流动性"

    def analyze(self, data: IPOData, config: dict) -> DimensionScore:
        weight = config["dimensions"]["liquidity"]["weight"]
        lq = data.liquidity
        subs = []

        # 自由流通市值
        if lq.free_float_market_cap is not None:
            cap = lq.free_float_market_cap
            if cap >= 5000:  # > 50亿
                s = 85
            elif cap >= 1000:  # > 10亿
                s = 70
            elif cap >= 500:
                s = 50
            else:
                s = 25
            subs.append(SubScore("自由流通市值", s,
                                 f"自由流通市值 HK${cap:.0f}百万",
                                 cap))

        # 港股通可能性
        if lq.hk_connect_eligible is not None:
            s = 85 if lq.hk_connect_eligible else 40
            subs.append(SubScore("港股通", s,
                                 "可能纳入港股通（南向资金可参与）" if lq.hk_connect_eligible
                                 else "暂不符合港股通条件"))

        # 做市商
        if lq.has_market_maker is not None:
            s = 75 if lq.has_market_maker else 45
            subs.append(SubScore("做市商", s,
                                 "有做市商安排" if lq.has_market_maker else "无做市商"))

        # 预估日均成交
        if lq.estimated_daily_turnover is not None:
            tv = lq.estimated_daily_turnover
            if tv >= 100:
                s = 85
            elif tv >= 30:
                s = 65
            elif tv >= 10:
                s = 45
            else:
                s = 20
            subs.append(SubScore("日均成交预估", s,
                                 f"预估日均成交 HK${tv:.0f}百万",
                                 tv))

        if not subs:
            return self.handle_missing(weight)

        score = self.avg_scores(subs)
        return DimensionScore(
            dimension=self.dimension_key,
            display_name=self.dimension_name,
            score=self.cap_score(score),
            weight=weight,
            sub_scores=subs,
            analysis=f"流动性评分 {score:.0f} 分。" +
                     ("流动性充裕，退出通畅。" if score >= 70 else
                      "流动性中等。" if score >= 50 else
                      "流动性不足，港股小盘股流动性陷阱风险较高。"),
            data_sufficient=len(subs) >= 2,
        )
