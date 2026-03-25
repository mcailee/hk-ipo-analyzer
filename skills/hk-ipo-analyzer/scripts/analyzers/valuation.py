"""估值定价分析器（18%）— 最高权重维度。"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from analyzers.base import BaseAnalyzer
from models.ipo_data import IPOData, DimensionScore, SubScore


class ValuationAnalyzer(BaseAnalyzer):
    dimension_key = "valuation"
    dimension_name = "估值定价"

    def analyze(self, data: IPOData, config: dict) -> DimensionScore:
        weight = config["dimensions"]["valuation"]["weight"]
        v = data.valuation
        scoring = config.get("valuation_scoring", {})
        subs = []

        # 1. PE 相对同行折价率
        if v.pe_ratio and v.peer_avg_pe and v.peer_avg_pe > 0:
            discount = (v.pe_ratio - v.peer_avg_pe) / v.peer_avg_pe * 100
            s = self.score_by_range(discount, scoring.get("pe_discount", []))
            subs.append(SubScore("PE同行折价率", s,
                                 f"发行PE {v.pe_ratio:.1f}x vs 同行 {v.peer_avg_pe:.1f}x, 折价 {discount:.1f}%",
                                 discount))
        else:
            subs.append(SubScore("PE同行折价率", 50, "数据不足，无法比较"))

        # 2. 定价区间位置
        if v.offer_price_low and v.offer_price_high and v.final_price:
            price_range = v.offer_price_high - v.offer_price_low
            if price_range > 0:
                pos = (v.final_price - v.offer_price_low) / price_range
                s = self.score_by_range(pos, scoring.get("price_range_position", []))
                subs.append(SubScore("定价区间位置", s,
                                     f"定价 HK${v.final_price:.2f} (区间 {v.offer_price_low:.2f}-{v.offer_price_high:.2f}, 位置 {pos:.0%})",
                                     pos))
        elif v.offer_price_low and v.offer_price_high:
            subs.append(SubScore("定价区间位置", 60,
                                 f"招股价区间 HK${v.offer_price_low:.2f}-{v.offer_price_high:.2f}，最终定价待公布"))
        else:
            subs.append(SubScore("定价区间位置", 50, "招股价数据缺失"))

        # 3. 可比 IPO 首日表现
        if v.comparable_ipo_first_day is not None:
            if v.comparable_ipo_first_day > 20:
                s = 85
            elif v.comparable_ipo_first_day > 5:
                s = 70
            elif v.comparable_ipo_first_day > 0:
                s = 55
            else:
                s = 30
            subs.append(SubScore("可比IPO首日表现", s,
                                 f"同行业近期IPO首日平均涨幅 {v.comparable_ipo_first_day:.1f}%",
                                 v.comparable_ipo_first_day))

        # 4. 市值与流通盘
        if v.market_cap and v.total_shares:
            # 小流通盘更容易被炒作（对打新是利好）
            if v.market_cap < 2000:  # < 20亿港元
                s = 75
            elif v.market_cap < 10000:
                s = 65
            else:
                s = 55
            subs.append(SubScore("市值规模", s,
                                 f"上市市值 HK${v.market_cap:.0f}百万",
                                 v.market_cap))

        if not subs:
            return self.handle_missing(weight)

        score = self.avg_scores(subs)
        analysis = self._build_analysis(v, score)

        return DimensionScore(
            dimension=self.dimension_key,
            display_name=self.dimension_name,
            score=self.cap_score(score),
            weight=weight,
            sub_scores=subs,
            analysis=analysis,
            data_sufficient=len(subs) >= 2,
        )

    def _build_analysis(self, v, score):
        parts = []
        if v.pe_ratio:
            parts.append(f"发行市盈率 {v.pe_ratio:.1f}x。")
        if v.peer_avg_pe:
            parts.append(f"同行平均 PE {v.peer_avg_pe:.1f}x。")

        if score >= 75:
            parts.append("估值定价具有吸引力，相对同行有明显折让，打新安全边际较高。")
        elif score >= 60:
            parts.append("估值定价合理，折让幅度适中。")
        elif score >= 45:
            parts.append("估值偏高，折让不足，打新收益空间有限。")
        else:
            parts.append("估值明显偏高，溢价发行，打新风险较大。")
        return " ".join(parts)
