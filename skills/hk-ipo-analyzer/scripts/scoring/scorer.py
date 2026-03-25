"""综合评分引擎 — 支持分阶段加权评分。"""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models.ipo_data import IPOData, DimensionScore, FinalReport, SubScore
from utils.helpers import get_config, detect_industry, logger


class Scorer:
    """加权评分引擎。"""

    def __init__(self, config: dict | None = None):
        self.config = config or get_config()

    def score_phase1(self, data: IPOData,
                     dimension_scores: list[DimensionScore]) -> FinalReport:
        """Phase1 评分：9 维度，权重等比放大至 100%。"""
        return self._compute(data, dimension_scores, phase=1)

    def score_phase2(self, data: IPOData,
                     dimension_scores: list[DimensionScore],
                     phase1_report: FinalReport | None = None) -> FinalReport:
        """Phase2 评分：全 11 维度。"""
        report = self._compute(data, dimension_scores, phase=2)
        if phase1_report:
            report.phase1_score = phase1_report.total_score
            report.phase1_rating = phase1_report.rating
        return report

    def _compute(self, data: IPOData,
                 dimension_scores: list[DimensionScore],
                 phase: int) -> FinalReport:
        """加权计算综合评分。"""
        dim_cfg = self.config["dimensions"]

        # 计算可用维度的总权重（用于等比放大）
        total_weight = sum(ds.weight for ds in dimension_scores)
        if total_weight <= 0:
            total_weight = 1.0

        # 加权求和
        weighted_sum = 0.0
        for ds in dimension_scores:
            normalized_weight = ds.weight / total_weight
            weighted_sum += ds.score * normalized_weight

        total_score = max(0, min(100, weighted_sum))

        # 评级映射
        from scoring.rating import RatingMapper
        mapper = RatingMapper(self.config)
        rating = mapper.map_rating(total_score)

        # 检查降级
        original_rating = None
        downgrade_reasons = []
        all_red_flags = []
        for ds in dimension_scores:
            all_red_flags.extend(ds.red_flags)

        if all_red_flags:
            original_rating = rating
            rating = mapper.downgrade(rating)
            downgrade_reasons = all_red_flags
            logger.warning(f"⚠️ 触发降级: {rating} (原: {original_rating}), 原因: {all_red_flags}")

        # 行业专属指标
        industry_type = detect_industry(data.company.industry, self.config)
        industry_subs = []
        for ds in dimension_scores:
            if ds.dimension in ("financial", "industry"):
                for ss in ds.sub_scores:
                    if ss.name in ("Rule of 40", "MAU", "ARPU", "LTV/CAC",
                                   "经常性收入占比", "大客户集中度",
                                   "管线数量", "核心产品阶段", "适应症市场",
                                   "同店增长", "门店扩张", "库存周转"):
                        industry_subs.append(ss)

        # 生成摘要
        summary = self._build_summary(data, total_score, rating,
                                       dimension_scores, phase)

        return FinalReport(
            stock_code=data.company.stock_code or "unknown",
            company_name=data.company.name or "未知公司",
            phase=phase,
            total_score=round(total_score, 1),
            rating=rating,
            original_rating=original_rating,
            downgrade_reasons=downgrade_reasons,
            dimension_scores=dimension_scores,
            industry=industry_type,
            industry_specific_scores=industry_subs,
            summary=summary,
        )

    def _build_summary(self, data, score, rating, dim_scores, phase):
        """生成分析摘要。"""
        name = data.company.name or data.company.stock_code or "该公司"
        parts = [f"【Phase {phase} 分析报告】{name}"]
        parts.append(f"综合评分: {score:.1f}/100 → 投资建议: {rating}")
        parts.append("")

        # 亮点和风险
        highlights = []
        risks = []
        for ds in dim_scores:
            if ds.score >= 75:
                highlights.append(f"✅ {ds.display_name}({ds.score:.0f}分)")
            elif ds.score < 40:
                risks.append(f"⚠️ {ds.display_name}({ds.score:.0f}分)")

        if highlights:
            parts.append("亮点: " + ", ".join(highlights))
        if risks:
            parts.append("风险: " + ", ".join(risks))

        return "\n".join(parts)
