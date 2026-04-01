#!/usr/bin/env python3
"""v5.0 回测验证脚本 — 5只新股对比 v4.0 vs v5.0"""
import sys, json, os, math
sys.path.insert(0, '.')
from models.ipo_data import *
from scoring.probability import ProbabilityPredictor
from scoring.scorer import Scorer
from utils.helpers import get_config

predictor = ProbabilityPredictor()
config = get_config()
scorer = Scorer(config)

stocks = [
    {
        'name': '德适-B', 'code': '02526', 'industry': '医疗AI',
        'sub_industry': '医疗AI', 'is_18c': True,
        'offer_price': 99.0, 'lot_size': 50,
        'market_cap': 8800, 'offer_size': 832,
        'sub_mult': 1074, 'has_cornerstone': False, 'cs_ratio': 0,
        'has_greenshoe': False,
        'hsi_1m': -5.7,
        'dark_price': 193.6,
        'actual_close': 209.6,
        'v4_pred_mid': -24.2, 'v4_pred_up': 90.3,
        'dim_scores': [('估值',50,0.15),('财务',52,0.12),('认购',82,0.15),
                       ('基石',20,0.10),('行业',85,0.12),('法律',90,0.01),
                       ('绿鞋',20,0.03),('公司',60,0.06),('承销',55,0.08),
                       ('情绪',48,0.09),('规模',60,0.05),('股东',50,0.01)],
    },
    {
        'name': '极视角', 'code': '06636', 'industry': 'AI视觉',
        'sub_industry': 'AI视觉', 'is_18c': True,
        'offer_price': 40.0, 'lot_size': 50,
        'market_cap': 4500, 'offer_size': 499,
        'sub_mult': 4596, 'has_cornerstone': False, 'cs_ratio': 9.45,
        'has_greenshoe': False,
        'hsi_1m': -5.7,
        'dark_price': 62.2,
        'actual_close': 100.0,
        'v4_pred_mid': 16.4, 'v4_pred_up': 87.5,
        'dim_scores': [('估值',55,0.15),('财务',58,0.12),('认购',88,0.15),
                       ('基石',35,0.10),('行业',80,0.12),('法律',90,0.01),
                       ('绿鞋',20,0.03),('公司',62,0.06),('承销',55,0.08),
                       ('情绪',48,0.09),('规模',65,0.05),('股东',50,0.01)],
    },
    {
        'name': '华沿机器人', 'code': '01021', 'industry': '协作机器人',
        'sub_industry': '协作机器人', 'is_18c': False,
        'offer_price': 17.0, 'lot_size': 200,
        'market_cap': 9035, 'offer_size': 1373,
        'sub_mult': 4043, 'has_cornerstone': True, 'cs_ratio': 56.0,
        'has_greenshoe': True,
        'hsi_1m': -5.7,
        'dark_price': None,
        'actual_close': 18.4,
        'v4_pred_mid': 20.7, 'v4_pred_up': 90.2,
        'dim_scores': [('估值',59,0.15),('财务',65,0.12),('认购',85,0.15),
                       ('基石',78,0.10),('行业',75,0.12),('法律',90,0.01),
                       ('绿鞋',82,0.03),('公司',68,0.06),('承销',65,0.08),
                       ('情绪',48,0.09),('规模',58,0.05),('股东',55,0.01)],
    },
    {
        'name': '瀚天天成', 'code': '02726', 'industry': '碳化硅',
        'sub_industry': '碳化硅', 'is_18c': False,
        'offer_price': 76.26, 'lot_size': 50,
        'market_cap': 46800, 'offer_size': 1640,
        'sub_mult': 50.66, 'has_cornerstone': True, 'cs_ratio': 15.0,
        'has_greenshoe': True,
        'sponsor_tier': 'top',
        'gross_margin': 28.0,
        'operating_cashflow': 50,
        'hsi_1m': -5.7,
        'dark_price': 104.7,
        'actual_close': 103.0,
        'v4_pred_mid': -12.0, 'v4_pred_up': 58.0,
        'dim_scores': [('估值',65,0.15),('财务',72,0.12),('认购',52,0.15),
                       ('基石',55,0.10),('行业',78,0.12),('法律',90,0.01),
                       ('绿鞋',80,0.03),('公司',70,0.06),('承销',70,0.08),
                       ('情绪',48,0.09),('规模',68,0.05),('股东',60,0.01)],
    },
    {
        'name': '同仁堂医养', 'code': '02667', 'industry': '医养',
        'sub_industry': '医养', 'is_18c': False,
        'offer_price': 7.30, 'lot_size': 500,
        'market_cap': 7900, 'offer_size': 790,
        'sub_mult': 35.0, 'has_cornerstone': True, 'cs_ratio': 20.0,
        'has_greenshoe': True,
        'operating_cashflow': 100,
        'gross_margin': 45.0,
        'hsi_1m': -5.7,
        'dark_price': None,
        'actual_close': None,
        'v4_pred_mid': 4.4, 'v4_pred_up': 71.4,
        'dim_scores': [('估值',68,0.15),('财务',70,0.12),('认购',48,0.15),
                       ('基石',62,0.10),('行业',60,0.12),('法律',85,0.01),
                       ('绿鞋',75,0.03),('公司',72,0.06),('承销',65,0.08),
                       ('情绪',48,0.09),('规模',62,0.05),('股东',58,0.01)],
    },
]

print('=' * 90)
print('v5.0 回测验证 — 5只新股 v4.0 vs v5.0 对比')
print('=' * 90)

results = []
for s in stocks:
    data = IPOData()
    data.company.name = s['name']
    data.company.stock_code = s['code']
    data.company.industry = s['industry']
    data.company.sub_industry = s.get('sub_industry', s['industry'])
    data.company.is_18c = s.get('is_18c', False)
    data.valuation.final_price = s['offer_price']
    data.valuation.market_cap = s['market_cap']
    data.underwriting.offer_size = s['offer_size']
    data.underwriting.sponsor_tier = s.get('sponsor_tier', '')
    data.cornerstone.total_ratio = s['cs_ratio']
    data.subscription = SubscriptionInfo(public_subscription_mult=s['sub_mult'])
    data.greenshoe.has_greenshoe = s['has_greenshoe']
    data.financial.gross_margin = s.get('gross_margin')
    data.financial.operating_cashflow = s.get('operating_cashflow')
    data.market_sentiment = MarketSentimentInfo(hsi_1m_change=s['hsi_1m'])

    if s['dark_price']:
        gm_prem = (s['dark_price'] - s['offer_price']) / s['offer_price'] * 100
        data.grey_market = GreyMarketInfo(
            grey_market_price=s['dark_price'],
            offer_price=s['offer_price'],
            grey_market_premium=gm_prem,
        )

    dim_scores = [DimensionScore(n, n, sc, w, data_sufficient=True) for n, sc, w in s['dim_scores']]
    total_w = sum(ds.weight for ds in dim_scores)
    total_score = sum(ds.score * ds.weight / total_w for ds in dim_scores)

    report = FinalReport(
        stock_code=s['code'], company_name=s['name'], phase=2,
        total_score=round(total_score, 1),
        rating='推荐' if total_score >= 65 else '中性',
        dimension_scores=dim_scores,
    )

    # v5.0 预测
    prob = predictor.predict(data, report)
    sell = scorer._generate_sell_timing(data, report)

    actual_d1 = None
    if s['actual_close']:
        actual_d1 = (s['actual_close'] - s['offer_price']) / s['offer_price'] * 100

    dark_ret = None
    if s['dark_price']:
        dark_ret = (s['dark_price'] - s['offer_price']) / s['offer_price'] * 100

    direction_ok = None
    in_range = None
    if actual_d1 is not None:
        direction_ok = (prob.first_day_up_prob > 50 and actual_d1 > 0) or (prob.first_day_up_prob <= 50 and actual_d1 <= 0)
        in_range = prob.expected_return_low <= actual_d1 <= prob.expected_return_high

    r = {
        'name': s['name'], 'code': s['code'], 'industry': s['industry'],
        'is_18c': s.get('is_18c', False),
        'total_score': total_score, 'sub_mult': s['sub_mult'],
        'v5_up': prob.first_day_up_prob, 'v5_mid': prob.expected_return_mid,
        'v5_low': prob.expected_return_low, 'v5_high': prob.expected_return_high,
        'v4_mid': s['v4_pred_mid'], 'v4_up': s['v4_pred_up'],
        'confidence': prob.confidence_level,
        'sell_strategy': sell.strategy, 'sell_rationale': sell.rationale,
        'dark_ret': dark_ret, 'actual_d1': actual_d1,
        'direction_ok': direction_ok, 'in_range': in_range,
        'methodology': prob.methodology,
    }
    results.append(r)

    status = '推迟上市' if s['actual_close'] is None else '已上市'
    tag_18c = ' [18C]' if s.get('is_18c') else ''
    print(f"\n{'─' * 90}")
    print(f"  {s['name']} ({s['code']}) | {s['industry']}{tag_18c} | {status}")
    print(f"{'─' * 90}")
    print(f"  评分 {total_score:.1f} | 超购 {s['sub_mult']:.0f}x | 募资 {s['offer_size']/100:.1f}亿")
    print(f"  📊 v5.0: 上涨{prob.first_day_up_prob}% | {prob.expected_return_low:+.1f}%~{prob.expected_return_mid:+.1f}%~{prob.expected_return_high:+.1f}% | {prob.confidence_level}")
    print(f"  📊 v4.0: 上涨{s['v4_pred_up']}% | 中位{s['v4_pred_mid']:+.1f}%")
    print(f"  ⏱️ v5.0策略: {sell.strategy} | {sell.rationale}")
    print(f"  💡 方法论: {prob.methodology}")

    if actual_d1 is not None:
        v5_err = actual_d1 - prob.expected_return_mid
        v4_err = actual_d1 - s['v4_pred_mid']
        improved = abs(v5_err) < abs(v4_err)
        dk_str = f"{dark_ret:+.1f}%" if dark_ret is not None else "N/A"
        print(f"  📈 实际: 暗盘{dk_str} → 首日{actual_d1:+.1f}%")
        print(f"  🎯 v5.0偏差: {v5_err:+.1f}pp | v4.0偏差: {v4_err:+.1f}pp | {'✅ 改善' if improved else '⚠️ 恶化'}")
        print(f"  🎯 方向{'✅' if direction_ok else '❌'} | 区间{'✅ 命中' if in_range else '⚠️ 未命中'}")
    else:
        print(f"  ⚠️ 推迟上市")

# ═══ 汇总 ═══
print(f"\n{'=' * 90}")
print('📋 v4.0 vs v5.0 汇总对比')
print(f"{'=' * 90}")

traded = [r for r in results if r['actual_d1'] is not None]
d_ok = sum(1 for r in traded if r['direction_ok'])
i_ok = sum(1 for r in traded if r['in_range'])

print(f"\n已上市 {len(traded)}/5 | v5.0方向准确 {d_ok}/{len(traded)} ({d_ok/len(traded)*100:.0f}%) | v5.0区间命中 {i_ok}/{len(traded)} ({i_ok/len(traded)*100:.0f}%)")

# v4.0 区间命中（之前统计: 1/4 = 25%）
print(f"(对比: v4.0方向准确 4/4 (100%) | v4.0区间命中 1/4 (25%))")

print(f"\n{'─' * 90}")
print(f"  {'股票':<12} {'实际':>8} {'v4.0预测':>10} {'v4.0偏差':>10} {'v5.0预测':>10} {'v5.0偏差':>10} {'改善':>8}")
print(f"{'─' * 90}")

v4_errors = []
v5_errors = []
for r in traded:
    v5_err = r['actual_d1'] - r['v5_mid']
    v4_err = r['actual_d1'] - r['v4_mid']
    v4_errors.append(v4_err)
    v5_errors.append(v5_err)
    improved = abs(v5_err) < abs(v4_err)
    delta = abs(v4_err) - abs(v5_err)
    print(f"  {r['name']:<12} {r['actual_d1']:>+7.1f}% {r['v4_mid']:>+9.1f}% {v4_err:>+9.1f}pp {r['v5_mid']:>+9.1f}% {v5_err:>+9.1f}pp {'↓'+str(round(delta))+'pp' if improved else '↑'+str(round(-delta))+'pp':>8}")

v4_avg = sum(abs(e) for e in v4_errors) / len(v4_errors)
v5_avg = sum(abs(e) for e in v5_errors) / len(v5_errors)
improve_pct = (v4_avg - v5_avg) / v4_avg * 100

print(f"\n{'─' * 90}")
print(f"  v4.0 平均绝对偏差: {v4_avg:.1f}pp")
print(f"  v5.0 平均绝对偏差: {v5_avg:.1f}pp")
print(f"  改善幅度: ↓{v4_avg - v5_avg:.1f}pp ({improve_pct:.0f}%)")
print(f"  {'✅ v5.0 显著优于 v4.0' if improve_pct > 20 else '⚠️ 改善有限'}")
