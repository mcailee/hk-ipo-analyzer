"""同批次新股横向对比分析器（P2 新增）。

分析当前 IPO 在同批次（近期同时上市）新股中的相对位置，
通过对比估值、认购热度、首日表现等维度给出竞争力评分。

子指标：
  1. 认购倍数排名
  2. 估值（PE）相对排名
  3. 同批次破发率参考
  4. 首日涨幅同批次对比（如有历史数据）
"""
from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from analyzers.base import BaseAnalyzer
from models.ipo_data import IPOData, DimensionScore, SubScore


class PeerComparisonAnalyzer(BaseAnalyzer):
    dimension_key = "peer_comparison"
    dimension_name = "同批次对比"

    def analyze(self, data: IPOData, config: dict) -> DimensionScore:
        weight = config["dimensions"].get("peer_comparison", {}).get("weight", 0.0)
        pc = data.peer_comparison
        scoring = config.get("peer_comparison_scoring", {})
        subs = []
        red_flags = []

        peers = pc.peers or []

        if not peers:
            return self.handle_missing(weight)

        total_in_batch = pc.total_in_batch or len(peers)

        # 1. 认购倍数排名
        current_mult = data.subscription.public_subscription_mult
        if current_mult is not None:
            peer_mults = [p.subscription_mult for p in peers if p.subscription_mult is not None]
            if peer_mults:
                all_mults = sorted(peer_mults + [current_mult], reverse=True)
                rank = all_mults.index(current_mult) + 1
                percentile = (1 - (rank - 1) / max(len(all_mults), 1)) * 100
                s = self._rank_to_score(percentile, scoring.get("rank_score_map", {}))
                subs.append(SubScore(
                    "认购倍数排名", s,
                    f"认购 {current_mult:.0f}x，同批 {len(all_mults)} 只中排第 {rank}",
                    rank
                ))

        # 2. PE 估值排名
        current_pe = data.valuation.pe_ratio
        if current_pe is not None:
            peer_pes = [p.pe_ratio for p in peers if p.pe_ratio is not None]
            if peer_pes:
                all_pes = sorted(peer_pes + [current_pe])  # PE 越低越好
                rank = all_pes.index(current_pe) + 1
                percentile = (1 - (rank - 1) / max(len(all_pes), 1)) * 100
                s = self._rank_to_score(percentile, scoring.get("rank_score_map", {}))
                subs.append(SubScore(
                    "PE估值排名", s,
                    f"PE {current_pe:.1f}x，同批次中估值排第 {rank}/{len(all_pes)}（越低越好）",
                    rank
                ))

        # 3. 同批次破发率
        if pc.batch_break_rate is not None:
            s = self.score_by_range(pc.batch_break_rate,
                                     scoring.get("batch_break_rate", []))
            label = "较低" if pc.batch_break_rate < 30 else "较高" if pc.batch_break_rate > 50 else "中等"
            subs.append(SubScore(
                "同批次破发率", s,
                f"同批次新股破发率 {pc.batch_break_rate:.0f}%（{label}）",
                pc.batch_break_rate
            ))
            if pc.batch_break_rate > 60:
                red_flags.append("同批次破发率超60%，市场环境恶劣")

        # 4. 同批次平均首日涨幅参考
        if pc.batch_avg_first_day_return is not None:
            s = self.score_by_range(pc.batch_avg_first_day_return,
                                     scoring.get("batch_avg_return", []))
            direction = "上涨" if pc.batch_avg_first_day_return >= 0 else "下跌"
            subs.append(SubScore(
                "同批次首日表现", s,
                f"同批次平均首日{direction} {abs(pc.batch_avg_first_day_return):.1f}%",
                pc.batch_avg_first_day_return
            ))

        # 5. 发行规模对比
        current_size = data.underwriting.offer_size
        if current_size is not None:
            peer_sizes = [p.offer_size for p in peers if p.offer_size is not None]
            if peer_sizes:
                avg_size = sum(peer_sizes) / len(peer_sizes)
                ratio = current_size / avg_size if avg_size > 0 else 1
                if ratio < 0.3:
                    s = 55
                    detail = f"发行规模远小于同批次均值（{current_size:.0f}M vs 均值{avg_size:.0f}M）"
                elif ratio < 0.7:
                    s = 65
                    detail = f"发行规模低于同批次均值（{current_size:.0f}M vs 均值{avg_size:.0f}M）"
                elif ratio < 1.5:
                    s = 70
                    detail = f"发行规模与同批次接近（{current_size:.0f}M vs 均值{avg_size:.0f}M）"
                else:
                    s = 60
                    detail = f"发行规模显著大于同批次（{current_size:.0f}M vs 均值{avg_size:.0f}M）"
                subs.append(SubScore("规模对比", s, detail, ratio))

        if not subs:
            return self.handle_missing(weight)

        score = self.avg_scores(subs)
        analysis = self._build_analysis(pc, score, total_in_batch)

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

    @staticmethod
    def _rank_to_score(percentile: float, score_map: dict) -> float:
        """百分位排名 → 评分。"""
        if percentile >= 80:
            return score_map.get("top20", 90)
        elif percentile >= 60:
            return score_map.get("top40", 75)
        elif percentile >= 40:
            return score_map.get("mid", 60)
        elif percentile >= 20:
            return score_map.get("bottom40", 45)
        else:
            return score_map.get("bottom20", 30)

    def _build_analysis(self, pc, score, total):
        parts = []
        if total:
            parts.append(f"同批次共 {total} 只新股上市。")
        if pc.batch_avg_subscription_mult:
            parts.append(f"批次平均认购 {pc.batch_avg_subscription_mult:.0f}x。")
        if pc.batch_avg_first_day_return is not None:
            parts.append(f"批次平均首日涨幅 {pc.batch_avg_first_day_return:.1f}%。")

        if score >= 75:
            parts.append("在同批次中表现突出，竞争力强。")
        elif score >= 60:
            parts.append("在同批次中处于中上水平。")
        elif score >= 45:
            parts.append("在同批次中表现一般。")
        else:
            parts.append("在同批次中表现落后，需谨慎。")
        return " ".join(parts)
