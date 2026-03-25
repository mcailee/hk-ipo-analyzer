"""行业专属分析器路由。"""
from __future__ import annotations
from typing import Optional

def get_industry_analyzer(industry_type: str) -> Optional["IndustrySpecificAnalyzer"]:
    """根据行业类型返回对应的专属分析器实例。"""
    if industry_type == "tmt":
        from analyzers.industry_specific.tmt import TMTAnalyzer
        return TMTAnalyzer()
    elif industry_type == "pharma":
        from analyzers.industry_specific.pharma import PharmaAnalyzer
        return PharmaAnalyzer()
    elif industry_type == "consumer":
        from analyzers.industry_specific.consumer import ConsumerAnalyzer
        return ConsumerAnalyzer()
    return None
