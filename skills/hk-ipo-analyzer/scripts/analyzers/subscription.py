"""市场认购热度分析器（16%，Phase2 专属）。

v2.0 优化:
  - 公开认购倍数改为对数化评分 (score = base + slope × ln(mult))
  - 支持机制A/B双轨适配（2025.08港交所改革）
  - 机制B使用机构下单倍数 + 定价位置替代传统回拨
  - 中签率反向推算热度
"""
from __future__ import annotations
import math
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from analyzers.base import BaseAnalyzer
from models.ipo_data import IPOData, DimensionScore, SubScore


class SubscriptionAnalyzer(BaseAnalyzer):
    dimension_key = "subscription"
    dimension_name = "市场认购热度"

    def analyze(self, data: IPOData, config: dict) -> DimensionScore:
        weight = config["dimensions"]["subscription"]["weight"]
        sub = data.subscription
        scoring = config.get("subscription_scoring", {})
        subs = []

        mechanism = (sub.pricing_mechanism or "A").upper()

        if mechanism == "B":
            subs = self._analyze_mech_b(sub, scoring, subs)
        else:
            subs = self._analyze_mech_a(sub, scoring, subs)

        # ── 通用子指标（A/B共享）──
        # 国际配售倍数
        if sub.intl_placement_mult is not None:
            s = self.score_by_range(sub.intl_placement_mult,
                                    scoring.get("intl_mult", []))
            subs.append(SubScore("国际配售倍数", s,
                                 f"国际配售 {sub.intl_placement_mult:.1f} 倍",
                                 sub.intl_placement_mult))

        # 同期新股竞争
        if sub.concurrent_ipos is not None:
            if sub.concurrent_ipos <= 2:
                s = 80
            elif sub.concurrent_ipos <= 5:
                s = 60
            else:
                s = 35
            subs.append(SubScore("同期竞争", s,
                                 f"同期 {sub.concurrent_ipos} 只新股上市",
                                 sub.concurrent_ipos))

        # 近期破发率
        if sub.recent_break_rate is not None:
            if sub.recent_break_rate < 20:
                s = 80
            elif sub.recent_break_rate < 40:
                s = 60
            elif sub.recent_break_rate < 60:
                s = 40
            else:
                s = 20
            subs.append(SubScore("近期市场氛围", s,
                                 f"近期新股破发率 {sub.recent_break_rate:.0f}%",
                                 sub.recent_break_rate))

        if not subs:
            return self.handle_missing(weight)

        score = self.avg_scores(subs)
        analysis = self._build_analysis(sub, score, mechanism)

        return DimensionScore(
            dimension=self.dimension_key,
            display_name=self.dimension_name,
            score=self.cap_score(score),
            weight=weight,
            sub_scores=subs,
            analysis=analysis,
            data_sufficient=len(subs) >= 2,
        )

    def _analyze_mech_a(self, sub, scoring, subs):
        """机制A 传统路径：公开认购倍数（对数化）+ 回拨触发。"""
        log_params = scoring.get("public_mult_log", {})

        # 公开认购倍数 — 对数化评分
        if sub.public_subscription_mult is not None:
            s = self._log_score(sub.public_subscription_mult, log_params)
            subs.append(SubScore("公开认购倍数", s,
                                 f"公开认购 {sub.public_subscription_mult:.1f} 倍（对数化评分）",
                                 sub.public_subscription_mult))

        # 回拨触发
        if sub.clawback_triggered is not None:
            s = 80 if sub.clawback_triggered else 45
            subs.append(SubScore("回拨机制", s,
                                 "触发回拨（认购火爆）" if sub.clawback_triggered else "未触发回拨"))

        # 中签率（有则作为补充）
        if sub.allocation_rate is not None:
            s = self._allocation_rate_score(sub.allocation_rate)
            subs.append(SubScore("中签率", s,
                                 f"中签率 {sub.allocation_rate:.2f}%",
                                 sub.allocation_rate))

        return subs

    def _analyze_mech_b(self, sub, scoring, subs):
        """机制B 新路径：机构下单倍数 + 定价位置 + 散户意向倍数。"""
        mech_b_cfg = scoring.get("mech_b", {})

        # 机构投资者下单倍数
        if sub.mech_b_institutional_orders is not None:
            s = self.score_by_range(sub.mech_b_institutional_orders,
                                    mech_b_cfg.get("institutional_orders", []))
            subs.append(SubScore("机构下单倍数", s,
                                 f"机构投资者下单 {sub.mech_b_institutional_orders:.1f} 倍",
                                 sub.mech_b_institutional_orders))

        # 最终定价相对指示区间
        if sub.mech_b_price_vs_range is not None:
            s = self.score_by_range(sub.mech_b_price_vs_range,
                                    mech_b_cfg.get("price_vs_range", []))
            pos_pct = sub.mech_b_price_vs_range * 100
            subs.append(SubScore("定价位置（机制B）", s,
                                 f"定价在指示区间 {pos_pct:.0f}% 位置",
                                 sub.mech_b_price_vs_range))

        # 散户意向认购倍数（机制B下散户池独立）
        if sub.mech_b_retail_indicated_mult is not None:
            log_params = scoring.get("public_mult_log", {})
            s = self._log_score(sub.mech_b_retail_indicated_mult, log_params)
            subs.append(SubScore("散户意向倍数", s,
                                 f"散户意向认购 {sub.mech_b_retail_indicated_mult:.1f} 倍",
                                 sub.mech_b_retail_indicated_mult))

        # 公开认购倍数（如果有，也计入）
        if sub.public_subscription_mult is not None:
            log_params = scoring.get("public_mult_log", {})
            s = self._log_score(sub.public_subscription_mult, log_params)
            subs.append(SubScore("公开认购倍数", s,
                                 f"公开认购 {sub.public_subscription_mult:.1f} 倍（对数化评分）",
                                 sub.public_subscription_mult))

        # 中签率
        if sub.allocation_rate is not None:
            s = self._allocation_rate_score(sub.allocation_rate)
            subs.append(SubScore("中签率", s,
                                 f"中签率 {sub.allocation_rate:.2f}%",
                                 sub.allocation_rate))

        return subs

    @staticmethod
    def _log_score(mult: float, params: dict) -> float:
        """对数化认购倍数评分: score = base + slope × ln(mult)。"""
        base = params.get("base", 20)
        slope = params.get("slope", 10.5)
        max_score = params.get("max_score", 98)
        min_score = params.get("min_score", 10)

        if mult <= 0:
            return min_score
        if mult < 1:
            return min_score

        score = base + slope * math.log(mult)
        return max(min_score, min(max_score, round(score, 1)))

    @staticmethod
    def _allocation_rate_score(rate: float) -> float:
        """中签率评分（越低越火爆）。"""
        if rate <= 1:
            return 90
        elif rate <= 5:
            return 78
        elif rate <= 15:
            return 65
        elif rate <= 30:
            return 50
        elif rate <= 60:
            return 35
        else:
            return 18

    def _build_analysis(self, sub, score, mechanism):
        parts = []
        mech_label = f"[机制{mechanism}]" if mechanism in ("A", "B") else ""

        if sub.public_subscription_mult:
            parts.append(f"{mech_label}公开认购 {sub.public_subscription_mult:.0f} 倍。")
        if sub.intl_placement_mult:
            parts.append(f"国际配售 {sub.intl_placement_mult:.0f} 倍。")

        if mechanism == "B":
            if sub.mech_b_institutional_orders:
                parts.append(f"机构下单 {sub.mech_b_institutional_orders:.0f} 倍。")
            parts.append("（适用新机制B定价流程）")

        if score >= 80:
            parts.append("市场认购极其火爆，打新胜率高。")
        elif score >= 65:
            parts.append("市场认购热度较高，看好情绪明显。")
        elif score >= 45:
            parts.append("市场认购热度一般。")
        else:
            parts.append("市场认购冷淡，需警惕上市首日表现。")
        return " ".join(parts)
