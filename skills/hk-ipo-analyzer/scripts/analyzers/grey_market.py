"""暗盘数据分析器（P3 新增）。

在 IPO 暗盘交易阶段（上市前一天晚），利用暗盘价格与成交数据，
提供最接近真实首日表现的预测性指标。

子指标：
  1. 暗盘溢价率
  2. 暗盘成交活跃度
  3. 暗盘与评分一致性（验证模型）
"""
from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from analyzers.base import BaseAnalyzer
from models.ipo_data import IPOData, DimensionScore, SubScore


class GreyMarketAnalyzer(BaseAnalyzer):
    dimension_key = "grey_market"
    dimension_name = "暗盘数据"

    def analyze(self, data: IPOData, config: dict) -> DimensionScore:
        weight = config["dimensions"].get("grey_market", {}).get("weight", 0.0)
        gm = data.grey_market
        scoring = config.get("grey_market_scoring", {})
        subs = []
        red_flags = []

        # 如果没有暗盘数据，返回不参与加权的中性
        if gm.grey_market_price is None:
            return DimensionScore(
                dimension=self.dimension_key,
                display_name=self.dimension_name,
                score=50.0,
                weight=0.0,  # 无暗盘数据时不影响总分
                sub_scores=[],
                analysis="暗盘数据暂未公布或不适用。",
                data_sufficient=False,
            )

        offer_price = gm.offer_price or data.valuation.final_price

        # 1. 暗盘溢价率
        if gm.grey_market_premium is not None:
            premium = gm.grey_market_premium
        elif offer_price and offer_price > 0:
            premium = (gm.grey_market_price - offer_price) / offer_price * 100
        else:
            premium = None

        if premium is not None:
            s = self.score_by_range(premium, scoring.get("premium", []))
            if premium > 0:
                desc = f"暗盘溢价 +{premium:.1f}%（暗盘价 HK${gm.grey_market_price:.2f} vs 发行价 HK${offer_price:.2f}）"
            elif premium == 0:
                desc = f"暗盘平收（暗盘价 = 发行价 HK${offer_price:.2f}）"
            else:
                desc = f"暗盘折价 {premium:.1f}%（暗盘价 HK${gm.grey_market_price:.2f} vs 发行价 HK${offer_price:.2f}）"
                # 渐进式惩罚：-3%开始预警，-10%触发红旗
                if premium < -10:
                    red_flags.append(f"暗盘深度破发 {premium:.1f}%")
                elif premium < -3:
                    # -3% ~ -10% 区间：线性衰减暗盘溢价率得分（通过 score_by_range 已自动处理）
                    # 但不触发 red_flag（避免 cliff effect）
                    pass
            subs.append(SubScore("暗盘溢价率", s, desc, premium))

        # 2. 暗盘成交活跃度
        if gm.grey_market_volume is not None:
            if gm.grey_market_volume > 5000:
                s = 75
                detail = f"暗盘成交 {gm.grey_market_volume:.0f} 手（活跃，参考性强）"
            elif gm.grey_market_volume > 1000:
                s = 65
                detail = f"暗盘成交 {gm.grey_market_volume:.0f} 手（正常）"
            elif gm.grey_market_volume > 200:
                s = 50
                detail = f"暗盘成交 {gm.grey_market_volume:.0f} 手（偏低）"
            else:
                s = 35
                detail = f"暗盘成交仅 {gm.grey_market_volume:.0f} 手（极低，参考性差）"
            subs.append(SubScore("暗盘活跃度", s, detail, gm.grey_market_volume))

        # 3. 暗盘成交额
        if gm.grey_market_turnover is not None:
            if gm.grey_market_turnover > 50:
                s = 80
                detail = f"暗盘成交额 HK${gm.grey_market_turnover:.1f}百万（高）"
            elif gm.grey_market_turnover > 10:
                s = 65
                detail = f"暗盘成交额 HK${gm.grey_market_turnover:.1f}百万（中等）"
            else:
                s = 45
                detail = f"暗盘成交额 HK${gm.grey_market_turnover:.1f}百万（低）"
            subs.append(SubScore("暗盘成交额", s, detail, gm.grey_market_turnover))

        if not subs:
            return self.handle_missing(weight)

        score = self.avg_scores(subs)
        analysis = self._build_analysis(gm, premium, score)

        return DimensionScore(
            dimension=self.dimension_key,
            display_name=self.dimension_name,
            score=self.cap_score(score),
            weight=weight,
            sub_scores=subs,
            analysis=analysis,
            data_sufficient=len(subs) >= 1,
            red_flags=red_flags,
        )

    def _build_analysis(self, gm, premium, score):
        parts = []
        source = f"（数据来源: {gm.data_source}）" if gm.data_source else ""

        if premium is not None:
            if premium > 10:
                parts.append(f"暗盘表现强劲（+{premium:.1f}%），首日上涨概率大。{source}")
            elif premium > 0:
                parts.append(f"暗盘小幅溢价（+{premium:.1f}%），首日表现可期。{source}")
            elif premium > -3:
                parts.append(f"暗盘接近平收（{premium:.1f}%），首日表现存在不确定性。{source}")
            else:
                parts.append(f"暗盘已破发（{premium:.1f}%），首日下跌风险高。{source}")

        if score >= 70:
            parts.append("暗盘数据积极，建议持有至上市。")
        elif score >= 50:
            parts.append("暗盘表现中性，建议上市首日观察后决定。")
        else:
            parts.append("暗盘数据偏弱，建议首日迅速止损或弃购。")

        return " ".join(parts)
