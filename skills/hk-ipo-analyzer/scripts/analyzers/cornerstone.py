"""基石投资者分析器（10%）— 含反向扣分机制。"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from analyzers.base import BaseAnalyzer
from models.ipo_data import IPOData, DimensionScore, SubScore


class CornerstoneAnalyzer(BaseAnalyzer):
    dimension_key = "cornerstone"
    dimension_name = "基石投资者"

    def analyze(self, data: IPOData, config: dict) -> DimensionScore:
        weight = config["dimensions"]["cornerstone"]["weight"]
        cs = data.cornerstone
        rules = config.get("cornerstone_rules", {})
        subs = []

        investors = cs.investors
        if not investors:
            subs.append(SubScore("基石投资者", 35, "无基石投资者，市场信心不足"))
            return DimensionScore(
                dimension=self.dimension_key,
                display_name=self.dimension_name,
                score=35,
                weight=weight,
                sub_scores=subs,
                analysis="未引入基石投资者，市场认可度存疑。",
                data_sufficient=True,
            )

        # 1. 基石数量
        count = len(investors)
        if count >= 5:
            subs.append(SubScore("基石数量", 80, f"共 {count} 家基石投资者", count))
        elif count >= 3:
            subs.append(SubScore("基石数量", 70, f"共 {count} 家基石投资者", count))
        elif count >= 1:
            subs.append(SubScore("基石数量", 55, f"仅 {count} 家基石投资者", count))

        # 2. 基石质量分级
        top_count = sum(1 for i in investors if i.tier in ("sovereign", "top_pe"))
        related_count = sum(1 for i in investors if i.is_related_party)
        quality_score = 60
        bonus = 0

        if top_count > 0:
            bonus = rules.get("top_investor_bonus", 15)
            subs.append(SubScore("顶级机构参与", 90,
                                 f"{top_count} 家顶级机构/主权基金参与 (+{bonus}分)"))
            quality_score += bonus

        related_ratio = related_count / count if count > 0 else 0
        if related_ratio > rules.get("related_party_threshold", 0.50):
            penalty = rules.get("related_party_penalty", -20)
            subs.append(SubScore("关联方占比", 20,
                                 f"关联方占比 {related_ratio:.0%} 过高 ({penalty}分)"))
            quality_score += penalty
        elif related_count > 0:
            subs.append(SubScore("关联方占比", 50,
                                 f"关联方 {related_count} 家，占比 {related_ratio:.0%}"))

        # 3. 基石认购总占比
        if cs.total_ratio is not None:
            ratio = cs.total_ratio / 100 if cs.total_ratio > 1 else cs.total_ratio
            if ratio > rules.get("high_ratio_threshold", 0.70):
                penalty = rules.get("high_ratio_penalty", -15)
                subs.append(SubScore("基石占比", 25,
                                     f"基石占比 {ratio:.0%} 过高（散户机构不买账）({penalty}分)"))
                quality_score += penalty
            elif ratio >= 0.30:
                subs.append(SubScore("基石占比", 75, f"基石占比 {ratio:.0%}，适中"))
            else:
                subs.append(SubScore("基石占比", 60, f"基石占比 {ratio:.0%}，偏低"))

        # 4. 锁定期
        lockups = [i.lockup_months for i in investors if i.lockup_months]
        if lockups:
            avg_lockup = sum(lockups) / len(lockups)
            if avg_lockup >= 12:
                subs.append(SubScore("锁定期", 85, f"平均锁定 {avg_lockup:.0f} 个月，信心充足"))
            elif avg_lockup >= 6:
                subs.append(SubScore("锁定期", 70, f"平均锁定 {avg_lockup:.0f} 个月"))
            else:
                subs.append(SubScore("锁定期", 45, f"平均锁定仅 {avg_lockup:.0f} 个月，偏短"))

        score = self.cap_score(self.avg_scores(subs))
        names = [i.name for i in investors[:5]]
        analysis = f"共 {count} 家基石投资者（{', '.join(names)}{'等' if count > 5 else ''}）。"
        if score >= 70:
            analysis += "基石阵容强大，市场信心充足。"
        elif score >= 50:
            analysis += "基石投资者结构一般。"
        else:
            analysis += "基石投资者质量堪忧，需警惕关联方认购或占比过高的信号。"

        return DimensionScore(
            dimension=self.dimension_key,
            display_name=self.dimension_name,
            score=score,
            weight=weight,
            sub_scores=subs,
            analysis=analysis,
            data_sufficient=True,
        )
