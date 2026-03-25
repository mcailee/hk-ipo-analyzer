"""行业专属分析器基类。"""
from __future__ import annotations
from abc import ABC, abstractmethod
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from models.ipo_data import IPOData, SubScore


class IndustrySpecificAnalyzer(ABC):
    """行业专属分析器基类。"""
    industry_name: str = ""

    @abstractmethod
    def analyze(self, data: IPOData) -> list[SubScore]:
        """返回行业专属子指标评分列表。"""
        ...

    @staticmethod
    def safe_get(data_dict: dict, key: str, default=None):
        return data_dict.get(key, default)
