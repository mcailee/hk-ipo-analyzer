"""基石投资者分析器（10%）— v5.1 四级分级 + 信心倍增器。

v5.1 升级：
  - S/A/B/C 四级基石分类体系
  - WQS(数量加权) + AWQS(金额加权) 综合质量分
  - 信心倍增器: S/A 级机构高占比时额外加分
  - 关联方反向扣分保留
"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from analyzers.base import BaseAnalyzer
from models.ipo_data import IPOData, DimensionScore, SubScore, CORNERSTONE_TIER_WEIGHTS


# 分级中文标签
TIER_LABELS = {
    "sovereign": "S级·主权基金",
    "intl_top": "A级·国际顶级",
    "cn_major": "B级·国内大型",
    "cn_normal": "C级·国内普通",
    "related": "关联方",
    # 向后兼容
    "top_pe": "A级·国际顶级",
    "industry": "B级·国内大型",
    "other": "C级·国内普通",
}


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

        # ── 读取配置 ──
        tier_weights = rules.get("tier_weights", CORNERSTONE_TIER_WEIGHTS)
        wqs_awqs_ratio = rules.get("wqs_awqs_ratio", 0.4)

        # 1. 基石数量
        count = len(investors)
        if count >= 5:
            subs.append(SubScore("基石数量", 80, f"共 {count} 家基石投资者", count))
        elif count >= 3:
            subs.append(SubScore("基石数量", 70, f"共 {count} 家基石投资者", count))
        elif count >= 1:
            subs.append(SubScore("基石数量", 55, f"仅 {count} 家基石投资者", count))

        # 2. 四级分级分布
        tier_dist = {}
        for inv in investors:
            tier_dist[inv.tier] = tier_dist.get(inv.tier, 0) + 1
        dist_parts = []
        for tier_key in ("sovereign", "intl_top", "cn_major", "cn_normal", "related"):
            n = tier_dist.get(tier_key, 0)
            # 向后兼容：合并旧 tier 值
            if tier_key == "intl_top":
                n += tier_dist.get("top_pe", 0)
            elif tier_key == "cn_major":
                n += tier_dist.get("industry", 0)
            elif tier_key == "cn_normal":
                n += tier_dist.get("other", 0)
            if n > 0:
                label = TIER_LABELS.get(tier_key, tier_key)
                dist_parts.append(f"{label}×{n}")
        subs.append(SubScore("分级分布", 70,
                             f"基石分级: {', '.join(dist_parts)}"))

        # 3. 加权质量分 (WQS + AWQS + Combined)
        quality = cs.calc_quality_scores(tier_weights, wqs_awqs_ratio)
        wqs = quality["wqs"]
        awqs = quality["awqs"]
        combined = quality["combined"]
        sa_ratio = quality["sa_ratio"]
        conviction_bonus = quality["conviction_bonus"]

        subs.append(SubScore("数量加权质量(WQS)", self.cap_score(wqs),
                             f"WQS={wqs:.1f} (各级机构数量加权)", wqs))
        subs.append(SubScore("金额加权质量(AWQS)", self.cap_score(awqs),
                             f"AWQS={awqs:.1f} (认购金额×等级加权)", awqs))
        subs.append(SubScore("综合质量分", self.cap_score(combined),
                             f"综合={combined:.1f} (WQS×{wqs_awqs_ratio:.0%}+AWQS×{1-wqs_awqs_ratio:.0%})",
                             combined))

        # 4. 信心倍增器
        if conviction_bonus > 0:
            subs.append(SubScore("信心倍增器", min(95, 70 + conviction_bonus),
                                 f"S/A级占发行额 {sa_ratio:.1%} → 额外+{conviction_bonus}分"
                                 f"（顶级机构重注=深度尽调验证）",
                                 sa_ratio))

        # 5. 关联方风险
        related_count = sum(1 for i in investors if i.is_related_party or i.tier == "related")
        related_ratio = related_count / count if count > 0 else 0
        if related_ratio > rules.get("related_party_threshold", 0.50):
            penalty = rules.get("related_party_penalty", -20)
            subs.append(SubScore("关联方占比", 20,
                                 f"关联方占比 {related_ratio:.0%} 过高 ({penalty}分)"))
            combined += penalty
        elif related_count > 0:
            subs.append(SubScore("关联方占比", 50,
                                 f"关联方 {related_count} 家，占比 {related_ratio:.0%}"))

        # 6. 基石认购总占比
        if cs.total_ratio is not None:
            ratio = cs.total_ratio / 100 if cs.total_ratio > 1 else cs.total_ratio
            if ratio > rules.get("high_ratio_threshold", 0.70):
                penalty = rules.get("high_ratio_penalty", -15)
                subs.append(SubScore("基石占比", 25,
                                     f"基石占比 {ratio:.0%} 过高（散户机构不买账）({penalty}分)"))
                combined += penalty
            elif ratio >= 0.30:
                subs.append(SubScore("基石占比", 75, f"基石占比 {ratio:.0%}，适中"))
            else:
                subs.append(SubScore("基石占比", 60, f"基石占比 {ratio:.0%}，偏低"))

        # 7. 锁定期
        lockups = [i.lockup_months for i in investors if i.lockup_months]
        if lockups:
            avg_lockup = sum(lockups) / len(lockups)
            if avg_lockup >= 12:
                subs.append(SubScore("锁定期", 85, f"平均锁定 {avg_lockup:.0f} 个月，信心充足"))
            elif avg_lockup >= 6:
                subs.append(SubScore("锁定期", 70, f"平均锁定 {avg_lockup:.0f} 个月"))
            else:
                subs.append(SubScore("锁定期", 45, f"平均锁定仅 {avg_lockup:.0f} 个月，偏短"))

        # 8. 最终得分 = 子维度均分 + 信心倍增器
        base_score = self.cap_score(self.avg_scores(subs))
        score = self.cap_score(base_score + conviction_bonus)

        # 生成分析文本
        names = [i.name for i in investors[:5]]
        analysis = f"共 {count} 家基石投资者（{', '.join(names)}{'等' if count > 5 else ''}）。"
        if dist_parts:
            analysis += f"分级: {', '.join(dist_parts)}。"
        if conviction_bonus > 0:
            analysis += f"S/A级机构占发行额{sa_ratio:.0%}，信心倍增+{conviction_bonus}分。"
        if score >= 75:
            analysis += "基石阵容豪华，市场信心强劲。"
        elif score >= 60:
            analysis += "基石投资者结构良好。"
        elif score >= 45:
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
