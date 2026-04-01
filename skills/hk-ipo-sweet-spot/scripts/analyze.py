#!/usr/bin/env python3
"""港股打新甜蜜区间分析器 - 主入口 (V3.5 Ensemble 混合版)
Usage:
  python3 analyze.py                                    # 全量回测报告
  python3 analyze.py --code 02097                       # 已上市股票回测
  python3 analyze.py --code 01021 --subscription-mult 5063 --has-cornerstone --category 机器人 --fundraising 8.5  # 未上市新股策略
  python3 analyze.py --code 03625 --subscription-mult 3118 --category 半导体 --fundraising 5 --is-18c  # 18C新股策略
  python3 analyze.py --code 03625 --subscription-mult 3118 --category 半导体 --fundraising 5 --is-18c --dark-return -5  # 暗盘联动
  python3 analyze.py --market-state bull                # 指定市场状态（bull/bear/neutral/auto）
"""
import sys, os, argparse

# 确保能导入同目录模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data import ipo_data, hsi_monthly
from engine import (
    analyze_by_subscription_range, analyze_by_cornerstone,
    analyze_by_category, analyze_fundraising_vs_return,
    compute_factor_weights, score_ipo, get_tier, analyze_by_score_tier,
    analyze_selling_timepoints, analyze_timepoint_by_dimension,
    get_sub_range_label, get_fundraising_label,
    analyze_by_quarter, analyze_by_month,
    analyze_single_stock, predict_selling_strategy,
    find_sweet_spot_range,
    RANGES,
    # 条件子模型相关
    classify_market_state, get_current_market_state,
    label_data_market_state, compute_conditional_models,
    get_model_for_state, analyze_by_market_state,
    BULL, BEAR, NEUTRAL, STATE_LABELS,
    # V3.3 新增
    bootstrap_confidence, time_series_cv, analyze_tier_selling_strategy,
    # V3.4 新增：多维相似度、暗盘联动、18C 分析
    compute_similarity_peers, compute_dark_feedback, analyze_18c_effect,
)
from report import (
    generate_full_report, generate_single_report, generate_strategy_report
)


def find_stock(code, data, date=None):
    """在数据集中查找股票（支持省略前导零）
    当有重复代码时（如02645），可通过 date 参数精确匹配
    """
    code = code.zfill(5)
    matches = [d for d in data if d["code"] == code or d["code"].lstrip("0") == code.lstrip("0")]
    if not matches:
        return None
    if len(matches) == 1:
        return matches[0]
    # 多个匹配（代码重用），尝试用日期精确匹配
    if date:
        for d in matches:
            if d["date"] == date:
                return d
    # 无日期参数或无精确匹配，返回最新的一条
    return sorted(matches, key=lambda d: d["date"], reverse=True)[0]


def resolve_market_state(args_state, date_str="未上市"):
    """解析用户指定的市场状态或自动判定"""
    if args_state and args_state.lower() != "auto":
        mapping = {"bull": BULL, "bear": BEAR, "neutral": NEUTRAL}
        return mapping.get(args_state.lower(), NEUTRAL)
    # auto模式：根据日期或当前环境判定
    if date_str != "未上市":
        state = classify_market_state(date_str, hsi_monthly)
        if state:
            return state
    return get_current_market_state(hsi_monthly)


def main():
    parser = argparse.ArgumentParser(description="港股打新甜蜜区间分析器 V3.5（Ensemble混合版）")
    parser.add_argument("--code", type=str, help="港股代码")
    parser.add_argument("--subscription-mult", type=float, help="公开认购倍数(未上市新股)")
    parser.add_argument("--has-cornerstone", action="store_true", help="是否有基石投资者")
    parser.add_argument("--category", type=str, default="其他", help="行业分类")
    parser.add_argument("--fundraising", type=float, default=5.0, help="募资额(亿港元)")
    parser.add_argument("--dark-return", type=float, help="暗盘涨跌幅%%")
    parser.add_argument("--is-18c", action="store_true", help="是否为18C/B类上市机制（允许未盈利公司上市）")
    parser.add_argument("--name", type=str, help="证券简称")
    parser.add_argument("--output", type=str, help="输出目录")
    parser.add_argument("--market-state", type=str, default="auto",
                        help="市场状态: bull/bear/neutral/auto (默认auto自动判定)")
    args = parser.parse_args()

    output_dir = args.output or os.getcwd()
    os.makedirs(output_dir, exist_ok=True)

    # ======== 预计算：条件子模型 ========
    print("🔧 训练条件子模型...")
    
    # 1. 先为所有数据打市场状态标签
    label_data_market_state(ipo_data, hsi_monthly)
    
    # 2. 训练条件子模型
    cond_result = compute_conditional_models(ipo_data, hsi_monthly)
    
    # 3. 全局模型（用于整体统计和后备）
    global_weights = cond_result["global"]["weights"]
    global_extra = cond_result["global"]["extra"]
    global_cat_encoding = global_extra.get("cat_encoding", {})
    global_norm_stats = cond_result["global"].get("norm_stats", {})

    # 给所有数据算评分（用全局权重保持一致性）
    for d in ipo_data:
        d["_score"] = score_ipo(d, global_weights, global_cat_encoding, global_norm_stats, global_extra)
        d["_tier"] = get_tier(d["_score"])

    print(f"📊 数据集: {len(ipo_data)} 只新股")
    print(f"🧠 全局模型 R²: {global_extra.get('r2', 0):.4f}")
    
    # 输出市场状态分布
    dist = cond_result["state_distribution"]
    for state in [BULL, BEAR, NEUTRAL]:
        n = dist.get(state, 0)
        label = STATE_LABELS.get(state, state)
        degraded = "（已降级至全局）" if state in cond_result["degraded_states"] else ""
        model = cond_result["models"].get(state, {})
        r2 = model.get("extra", {}).get("r2", 0) if not state in cond_result["degraded_states"] else global_extra.get("r2", 0)
        print(f"   {label}: {n}只 | R²={r2:.4f} {degraded}")

    for name, w in sorted(global_weights.items(), key=lambda x: -x[1]):
        print(f"   {name}: {w*100:.1f}%")

    if args.code:
        stock = find_stock(args.code, ipo_data)
        if stock:
            # ======== 模式2: 已上市股票回测 ========
            print(f"\n📈 分析已上市股票: {stock['name']} ({stock['code']})")
            
            # 确定该股的市场状态
            ms = resolve_market_state(args.market_state, stock["date"])
            sw, sc, sns, sxtra, sw_warning = get_model_for_state(cond_result, ms)
            model_source = f"子模型({STATE_LABELS.get(ms, ms)})" if ms not in cond_result["degraded_states"] else "全局模型（降级）"
            
            analysis = analyze_single_stock(stock, ipo_data, sw, sc, sns, sxtra)
            analysis["market_state"] = ms
            analysis["model_source"] = model_source
            analysis["model_warning"] = sw_warning
            
            html = generate_single_report(analysis)
            out_path = os.path.join(output_dir, f"sweet_spot_{stock['code']}.html")
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(html)
            print(f"✅ 报告已生成: {out_path}")
            print(f"   评分: {analysis['score']:.0f} ({analysis['tier']}档)")
            print(f"   市场状态: {STATE_LABELS.get(ms, ms)} | 模型: {model_source}")
            print(f"   排名: {analysis['rank']}/{analysis['total']}")
        else:
            # ======== 模式3: 未上市新股策略 ========
            if not args.subscription_mult:
                print(f"❌ 股票代码 {args.code} 不在数据集中（未上市新股）")
                print("   请提供 --subscription-mult 参数以获取卖出策略建议")
                sys.exit(1)
            
            params = {
                "code": args.code.zfill(5),
                "name": args.name or args.code.zfill(5),
                "subscription_mult": args.subscription_mult,
                "has_cornerstone": args.has_cornerstone,
                "category": args.category,
                "fundraising": args.fundraising,
                "dark_return": args.dark_return,
                "is_18c": args.is_18c,
                "day1_return": None,
                "day3_return": None,
                "day5_return": None,
                "date": "未上市",
            }
            
            # 确定市场状态
            ms = resolve_market_state(args.market_state)
            sw, sc, sns, sxtra, sw_warning = get_model_for_state(cond_result, ms)
            model_source = f"子模型({STATE_LABELS.get(ms, ms)})" if ms not in cond_result["degraded_states"] else "全局模型（降级）"
            
            print(f"\n🎯 生成卖出策略: {params['name']} ({params['code']})")
            print(f"   市场状态: {STATE_LABELS.get(ms, ms)} | 模型: {model_source}")
            if params.get("is_18c"):
                print(f"   ⚠️ 18C/B类上市机制 {'(有基石)' if params['has_cornerstone'] else '(无基石)'}")
            
            result = predict_selling_strategy(params, ipo_data, sw, sc,
                                              market_state=ms, model_source=model_source,
                                              norm_stats=sns, extra=sxtra)
            result["model_warning"] = sw_warning
            
            html = generate_strategy_report(result)
            out_path = os.path.join(output_dir, f"sweet_spot_{params['code']}_strategy.html")
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(html)
            print(f"✅ 策略报告已生成: {out_path}")
            print(f"   评分: {result['score']:.0f} ({result['tier']}档)")
            if result.get("sim_peers"):
                top_sim = result["sim_peers"][0]
                print(f"   最相似标的: {top_sim['stock']['name']} (相似度 {top_sim['similarity']:.2f})")
            if result.get("dark_feedback"):
                df = result["dark_feedback"]
                print(f"   暗盘联动: {df['pattern']} | 修正首日预期 {df['corrected_day1']:+.1f}%")
            if result["best_tp"]:
                print(f"   最优卖出时点: {result['best_tp']['label']} (期望 {result['best_tp']['expected']:+.1f}%)")
    else:
        # ======== 模式1: 全量回测报告 ========
        print("\n📊 运行全量回测分析...")
        range_res = analyze_by_subscription_range(ipo_data)
        cs_res = analyze_by_cornerstone(ipo_data)
        cat_res = analyze_by_category(ipo_data)
        fund_res = analyze_fundraising_vs_return(ipo_data)
        tier_res = analyze_by_score_tier(ipo_data, global_weights, global_cat_encoding, global_norm_stats, global_extra)
        tp_res = analyze_selling_timepoints(ipo_data)

        sub_labels = ["< 20倍", "20-100倍", "100-500倍", "500-2000倍", "2000-5000倍", "> 5000倍"]
        tp_by_sub = analyze_timepoint_by_dimension(ipo_data, "超购区间", get_sub_range_label, sub_labels)
        tp_by_cat = analyze_timepoint_by_dimension(ipo_data, "行业", lambda d: d["category"])
        fund_labels = ["< 5亿", "5-20亿", "20-50亿", "50-100亿", "> 100亿"]
        tp_by_fund = analyze_timepoint_by_dimension(ipo_data, "募资规模", get_fundraising_label, fund_labels)
        quarter_res = analyze_by_quarter(ipo_data)
        month_res = analyze_by_month(ipo_data)
        
        # 新增：市场状态维度分析
        ms_res = analyze_by_market_state(ipo_data, hsi_monthly, cond_result)

        # V3.4 新增：18C 效应分析
        effect_18c = analyze_18c_effect(ipo_data)
        print(f"\n🏷️ 18C 效应分析: {effect_18c['is_18c_count']}只18C vs {effect_18c['non_18c_count']}只非18C")
        if effect_18c["is_18c_stats"]:
            print(f"   18C 首日均值: {effect_18c['is_18c_stats']['avg']:+.1f}% | 非18C: {effect_18c['non_18c_stats']['avg']:+.1f}%")

        # V3.3 新增分析
        # 1. 时序交叉验证
        cv_res = time_series_cv(ipo_data, n_folds=4)
        if cv_res:
            print(f"\n📐 时序交叉验证 ({len(cv_res)} 折):")
            for fold in cv_res:
                print(f"   Fold {fold['fold']}: 训练{fold['train_n']}只 测试{fold['test_n']}只 | "
                      f"训练R²={fold['train_r2']:.3f} Spearman={fold['spearman']:.3f} "
                      f"档位准确率={fold['tier_accuracy']:.0f}%")
        
        # 2. 分档位卖出策略
        tier_sell_res = analyze_tier_selling_strategy(ipo_data, global_weights, global_cat_encoding, global_norm_stats, global_extra)
        print(f"\n🎯 分档位最优卖出时点:")
        for ts in tier_sell_res:
            if ts["count"] > 0:
                bs_str = ""
                if ts["bootstrap"]:
                    bs = ts["bootstrap"]
                    bs_str = f" (90%CI: {bs['exp_ci_lo']:+.1f}%~{bs['exp_ci_hi']:+.1f}%)"
                print(f"   {ts['tier']}档({ts['count']}只): {ts['best_tp']} 期望{ts['best_expected']:+.1f}%{bs_str}")
        
        # 3. Bootstrap 各超购区间置信区间
        from engine import bootstrap_confidence
        bootstrap_ranges = []
        for r in range_res:
            if r["count"] >= 5:
                bs = bootstrap_confidence(r["stocks"])
                bootstrap_ranges.append({"label": r["label"], "bootstrap": bs})
            else:
                bootstrap_ranges.append({"label": r["label"], "bootstrap": None})

        # 动态甜蜜区间（从数据中自动计算）
        sweet_spot_label = find_sweet_spot_range(range_res)

        html = generate_full_report(
            ipo_data, range_res, cs_res, cat_res, fund_res,
            global_weights, global_extra, tier_res, tp_res,
            tp_by_sub, tp_by_cat, tp_by_fund,
            quarter_res, month_res,
            cond_result=cond_result, ms_res=ms_res,
            sweet_spot_label=sweet_spot_label,
            cv_res=cv_res, tier_sell_res=tier_sell_res,
            bootstrap_ranges=bootstrap_ranges,
            effect_18c=effect_18c,
        )
        out_path = os.path.join(output_dir, "hk_ipo_sweet_spot.html")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"\n✅ 报告已生成: {out_path}")
        print(f"🎯 甜蜜区间: {sweet_spot_label}")
        for r in range_res:
            if r["count"] > 0:
                print(f"   {r['label']}: {r['count']}只 | 胜率 {r['win_rate']:.0f}% | 期望 {r['expected']:+.1f}%")


if __name__ == "__main__":
    main()
