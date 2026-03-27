"""估值定价分析器（15%）— 最高权重维度之一。

v2.0 优化:
  - 新增发行规模独立评估子指标
  - 微型IPO炒作警告
  - 大型IPO机构参与度评估
"""
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
        red_flags = []

        # 1. PE 相对同行折价率
        if v.pe_ratio and v.pe_ratio > 0 and v.peer_avg_pe and v.peer_avg_pe > 0:
            discount = (v.pe_ratio - v.peer_avg_pe) / v.peer_avg_pe * 100
            s = self.score_by_range(discount, scoring.get("pe_discount", []))
            subs.append(SubScore("PE同行折价率", s,
                                 f"发行PE {v.pe_ratio:.1f}x vs 同行 {v.peer_avg_pe:.1f}x, 折价 {discount:.1f}%",
                                 discount))
        elif v.ps_ratio and v.ps_ratio > 0 and v.peer_avg_ps and v.peer_avg_ps > 0:
            # PE 不可用（亏损公司或无数据），切换到 PS 估值
            ps_discount = (v.ps_ratio - v.peer_avg_ps) / v.peer_avg_ps * 100
            s = self.score_by_range(ps_discount, scoring.get("pe_discount", []))
            subs.append(SubScore("PS同行折价率", s,
                                 f"发行PS {v.ps_ratio:.1f}x vs 同行 {v.peer_avg_ps:.1f}x, 折价 {ps_discount:.1f}%（PE不可用，使用PS替代）",
                                 ps_discount))
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

        # 4. 发行规模独立评估（新增）
        offer_size = data.underwriting.offer_size
        market_cap = v.market_cap
        size_tiers = config.get("offer_size_tiers", {})

        if offer_size is not None:
            s, detail, flag = self._evaluate_offer_size(offer_size, market_cap, size_tiers)
            subs.append(SubScore("发行规模评估", s, detail, offer_size))
            if flag:
                red_flags.append(flag)
        elif market_cap is not None:
            # 用市值近似
            s, detail, flag = self._evaluate_market_cap_proxy(market_cap, size_tiers)
            subs.append(SubScore("市值规模", s, detail, market_cap))
            if flag:
                red_flags.append(flag)

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
            red_flags=red_flags,
        )

    def _evaluate_offer_size(self, offer_size, market_cap, tiers):
        """发行规模独立评估。"""
        micro = tiers.get("micro", 200)
        small = tiers.get("small", 1000)
        medium = tiers.get("medium", 5000)
        large = tiers.get("large", 10000)
        flag = None

        if offer_size < micro:
            # 微型IPO — 炒作风险
            s = 55
            detail = f"⚠️ 微型IPO（发行规模 HK${offer_size:.0f}百万），流动性极差易被操纵，炒作风险高"
            flag = "微型IPO炒作风险"
        elif offer_size < small:
            s = 70
            detail = f"小型IPO（发行规模 HK${offer_size:.0f}百万），流通盘小利于短炒"
        elif offer_size < medium:
            s = 68
            detail = f"中型IPO（发行规模 HK${offer_size:.0f}百万），规模适中"
        elif offer_size < large:
            s = 65
            detail = f"大型IPO（发行规模 HK${offer_size:.0f}百万），机构参与度高，价格较稳定"
        else:
            s = 60
            detail = f"超大型IPO（发行规模 HK${offer_size:.0f}百万），超级明星股，但抽中难度高"

        return s, detail, flag

    def _evaluate_market_cap_proxy(self, market_cap, tiers):
        """用市值近似评估（无发行规模数据时的降级方案）。"""
        flag = None
        if market_cap < 500:
            s = 55
            detail = f"⚠️ 微型股（市值 HK${market_cap:.0f}百万），流动性差"
            flag = "微型股炒作风险"
        elif market_cap < 2000:
            s = 72
            detail = f"小市值（HK${market_cap:.0f}百万），利于短线打新"
        elif market_cap < 10000:
            s = 65
            detail = f"中等市值（HK${market_cap:.0f}百万）"
        else:
            s = 60
            detail = f"大市值（HK${market_cap:.0f}百万），价格稳定性高"
        return s, detail, flag

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
