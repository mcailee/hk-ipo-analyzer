"""市场认购热度分析器（15%，Phase2 专属）。"""
from __future__ import annotations
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

        # 公开认购倍数
        if sub.public_subscription_mult is not None:
            s = self.score_by_range(sub.public_subscription_mult,
                                    scoring.get("public_mult", []))
            subs.append(SubScore("公开认购倍数", s,
                                 f"公开认购 {sub.public_subscription_mult:.1f} 倍",
                                 sub.public_subscription_mult))

        # 国际配售倍数
        if sub.intl_placement_mult is not None:
            s = self.score_by_range(sub.intl_placement_mult,
                                    scoring.get("intl_mult", []))
            subs.append(SubScore("国际配售倍数", s,
                                 f"国际配售 {sub.intl_placement_mult:.1f} 倍",
                                 sub.intl_placement_mult))

        # 回拨触发
        if sub.clawback_triggered is not None:
            s = 80 if sub.clawback_triggered else 45
            subs.append(SubScore("回拨机制", s,
                                 "触发回拨（认购火爆）" if sub.clawback_triggered else "未触发回拨"))

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
        analysis = self._build_analysis(sub, score)

        return DimensionScore(
            dimension=self.dimension_key,
            display_name=self.dimension_name,
            score=self.cap_score(score),
            weight=weight,
            sub_scores=subs,
            analysis=analysis,
            data_sufficient=len(subs) >= 2,
        )

    def _build_analysis(self, sub, score):
        parts = []
        if sub.public_subscription_mult:
            parts.append(f"公开认购 {sub.public_subscription_mult:.0f} 倍。")
        if sub.intl_placement_mult:
            parts.append(f"国际配售 {sub.intl_placement_mult:.0f} 倍。")

        if score >= 80:
            parts.append("市场认购极其火爆，打新胜率高。")
        elif score >= 65:
            parts.append("市场认购热度较高，看好情绪明显。")
        elif score >= 45:
            parts.append("市场认购热度一般。")
        else:
            parts.append("市场认购冷淡，需警惕上市首日表现。")
        return " ".join(parts)
