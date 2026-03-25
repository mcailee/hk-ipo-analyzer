"""通用工具函数。"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import yaml


# ── 日志 ──────────────────────────────────────────────────

def setup_logger(name: str = "hk-ipo", level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
        logger.addHandler(handler)
    logger.setLevel(level)
    return logger


logger = setup_logger()


# ── 路径 ──────────────────────────────────────────────────

def get_skill_root() -> Path:
    """返回 skill 根目录（scripts/ 的父目录）。"""
    return Path(__file__).resolve().parent.parent.parent


def get_config() -> dict:
    """加载 assets/config.yaml。"""
    config_path = get_skill_root() / "assets" / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_output_dir(stock_code: str) -> Path:
    """创建并返回输出目录: ./output/{stock_code}_{date}/"""
    date_str = datetime.now().strftime("%Y%m%d")
    output_dir = Path.cwd() / "output" / f"{stock_code}_{date_str}"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


# ── 数值处理 ──────────────────────────────────────────────

def safe_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    """安全转换为 float。"""
    if value is None:
        return default
    try:
        if isinstance(value, str):
            value = value.replace(",", "").replace("，", "").strip()
            value = re.sub(r'[^\d.\-]', '', value)
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    """安全转换为 int。"""
    f = safe_float(value)
    return int(f) if f is not None else default


def format_hkd(amount: Optional[float], unit: str = "百万") -> str:
    """格式化港币金额。"""
    if amount is None:
        return "N/A"
    if unit == "百万":
        if amount >= 1000:
            return f"HK${amount / 1000:.2f}十亿"
        return f"HK${amount:.2f}百万"
    return f"HK${amount:,.2f}"


def format_pct(value: Optional[float], decimal: int = 1) -> str:
    """格式化百分比。"""
    if value is None:
        return "N/A"
    return f"{value:.{decimal}f}%"


def format_mult(value: Optional[float]) -> str:
    """格式化倍数。"""
    if value is None:
        return "N/A"
    return f"{value:.1f}x"


def format_large_number(value: Optional[float]) -> str:
    """大数格式化（亿/万）。"""
    if value is None:
        return "N/A"
    if abs(value) >= 1e8:
        return f"{value / 1e8:.2f}亿"
    if abs(value) >= 1e4:
        return f"{value / 1e4:.2f}万"
    return f"{value:,.0f}"


# ── JSON 序列化 ──────────────────────────────────────────

def save_phase_data(data: Any, output_dir: Path, phase: int):
    """保存阶段数据为 JSON。"""
    filepath = output_dir / f"phase{phase}_data.json"
    d = asdict(data) if hasattr(data, '__dataclass_fields__') else data
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2, default=str)
    logger.info(f"Phase{phase} 数据已保存: {filepath}")
    return filepath


def load_phase_data(output_dir: Path, phase: int) -> Optional[dict]:
    """加载阶段 JSON 数据。"""
    filepath = output_dir / f"phase{phase}_data.json"
    if not filepath.exists():
        return None
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def save_report_json(report: Any, output_dir: Path, phase: int):
    """保存报告为 JSON。"""
    filepath = output_dir / f"phase{phase}_report.json"
    d = asdict(report) if hasattr(report, '__dataclass_fields__') else report
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2, default=str)
    logger.info(f"Phase{phase} 报告已保存: {filepath}")
    return filepath


# ── 行业识别 ──────────────────────────────────────────────

def detect_industry(industry_text: Optional[str], config: Optional[dict] = None) -> Optional[str]:
    """根据行业文本识别行业类型 (tmt/pharma/consumer/None)。"""
    if not industry_text:
        return None
    if config is None:
        config = get_config()
    text = industry_text.lower()
    keywords = config.get("industry_keywords", {})
    for industry_type, kws in keywords.items():
        for kw in kws:
            if kw.lower() in text:
                return industry_type
    return None
