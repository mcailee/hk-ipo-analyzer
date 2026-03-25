"""承销发行分析器（8%）。"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from analyzers.base import BaseAnalyzer
from models.ipo_data import IPOData, DimensionScore, SubScore


# 知名保荐人列表及历史表现
TOP_SPONSORS = {
    "高盛": 85, "Goldman Sachs": 85,
    "摩根士丹利": 85, "Morgan Stanley": 85,
    "中金": 80, "CICC": 80,
    "华泰": 75, "中信证券": 75, "CITIC": 75,
    "海通国际": 70, "招银国际": 70,
    "瑞银": 80, "UBS": 80,
    "花旗": 78, "Citigroup": 78,
    "美银": 78, "BofA": 78,
    "摩根大通": 85, "J.P. Morgan": 85, "JPMorgan": 85,
}


class UnderwritingAnalyzer(BaseAnalyzer):
    dimension_key = "underwriting"
    dimension_name = "承销发行"

    def analyze(self, data: IPOData, config: dict) -> DimensionScore:
        weight = config["dimensions"]["underwriting"]["weight"]
        uw = data.underwriting
        subs = []

        # 保荐人资质
        if uw.sponsor:
            sponsor_score = 55  # 默认中等
            for name, s in TOP_SPONSORS.items():
                if name.lower() in uw.sponsor.lower():
                    sponsor_score = s
                    break
            subs.append(SubScore("保荐人资质", sponsor_score,
                                 f"保荐人: {uw.sponsor}"))

        # 承销团规模
        team_size = len(uw.underwriters) + len(uw.joint_sponsors)
        if team_size >= 5:
            subs.append(SubScore("承销团规模", 80, f"承销团 {team_size} 家，阵容强大"))
        elif team_size >= 3:
            subs.append(SubScore("承销团规模", 65, f"承销团 {team_size} 家"))
        elif team_size >= 1:
            subs.append(SubScore("承销团规模", 50, f"承销团 {team_size} 家，规模偏小"))
        else:
            subs.append(SubScore("承销团规模", 50, "承销团信息缺失"))

        # 保荐人历史破发率
        if uw.sponsor_historical_break_rate is not None:
            rate = uw.sponsor_historical_break_rate
            if rate < 20:
                s = 85
            elif rate < 35:
                s = 65
            elif rate < 50:
                s = 45
            else:
                s = 25
            subs.append(SubScore("保荐人破发率", s,
                                 f"历史首日破发率 {rate:.0f}%", rate))

        # 递表次数
        if uw.application_times is not None:
            if uw.application_times == 1:
                subs.append(SubScore("递表次数", 80, "首次递表即通过"))
            elif uw.application_times == 2:
                subs.append(SubScore("递表次数", 55, "二次递表"))
            else:
                subs.append(SubScore("递表次数", 30,
                                     f"第 {uw.application_times} 次递表，上市路坎坷"))

        if not subs:
            return self.handle_missing(weight)

        score = self.avg_scores(subs)
        return DimensionScore(
            dimension=self.dimension_key,
            display_name=self.dimension_name,
            score=self.cap_score(score),
            weight=weight,
            sub_scores=subs,
            analysis=f"保荐人: {uw.sponsor or '未知'}。" +
                     ("承销团实力强劲。" if score >= 70 else
                      "承销团配置中等。" if score >= 50 else
                      "承销团实力偏弱，需注意。"),
            data_sufficient=bool(uw.sponsor),
        )
