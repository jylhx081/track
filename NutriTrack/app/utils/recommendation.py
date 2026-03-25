import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
from typing import List, Dict, Optional
from datetime import datetime, timedelta

def calculate_bmr(weight: float, height: float, age: int, gender: str) -> float:
    """
    Calculate BMR using Mifflin-St Jeor equation.
    优化：增强了对性别字段的容错处理。
    """
    # 默认处理：如果性别模糊，取男女性公式的中间值或偏向男性（10*w + 6.25*h - 5*a - 78）
    # 这里采用标准逻辑，但增加对 None 或空值的保护
    gender_str = str(gender).lower() if gender else "unknown"
    
    base_val = (10 * weight) + (6.25 * height) - (5 * age)
    
    if any(x in gender_str for x in ['male', '男']):
        return base_val + 5
    elif any(x in gender_str for x in ['female', '女']):
        return base_val - 161
    else:
        # 未知性别取中位值
        return base_val - 78

def get_activity_multiplier(level: str) -> float:
    levels = {
        'sedentary': 1.2, '久坐': 1.2, '久坐不动': 1.2,
        'light': 1.375, '轻度活动': 1.375,
        'moderate': 1.55, '中度活动': 1.55,
        'active': 1.725, '高度活动': 1.725,
        'very_active': 1.9, '极度活动': 1.9
    }
    for key, val in levels.items():
        if key in str(level).lower():
            return val
    return 1.2

def build_refined_matrix(
    rating_matrix: pd.DataFrame,
    orders: Optional[pd.DataFrame] = None,
    days: int = 60
) -> pd.DataFrame:
    """
    行为数据预处理（方案 A）：融合 60 天内复购行为与显式评价。
    """
    if rating_matrix is None or rating_matrix.empty:
        return rating_matrix

    # 1. 显式评分得分转换
    explicit = rating_matrix.copy()
    explicit_scores = pd.DataFrame(0.0, index=explicit.index, columns=explicit.columns)
    explicit_scores[explicit == 1] = 2.0
    explicit_scores[explicit == -1] = -5.0

    # 2. 隐式复购得分计算
    implicit_scores = pd.DataFrame(0.0, index=explicit.index, columns=explicit.columns)

    if orders is not None and not orders.empty:
        if all(col in orders.columns for col in ['user', 'dish_id', 'order_date']):
            now = datetime.now().date()
            cutoff = now - timedelta(days=days)

            def _to_date(v):
                return v.date() if isinstance(v, (datetime, pd.Timestamp)) else v

            tmp = orders.copy()
            tmp['order_date'] = tmp['order_date'].apply(_to_date)
            tmp = tmp[tmp['order_date'] >= cutoff]

            if not tmp.empty:
                grouped = tmp.groupby(['user', 'dish_id']).size().reset_index(name='buy_count')
                grouped['implicit_score'] = np.log2(grouped['buy_count'] + 1.0) * 1.5
                
                implicit_pivot = grouped.pivot(index='user', columns='dish_id', values='implicit_score')
                implicit_scores = implicit_pivot.reindex(
                    index=explicit.index, columns=explicit.columns, fill_value=0.0
                )

    # 3. 融合与约束
    refined = explicit_scores.add(implicit_scores, fill_value=0.0)
    refined = refined.clip(lower=-5.0, upper=5.0)

    # 显式讨厌(-1)具有最高优先级，强制降权
    mask_dislike = (explicit == -1)
    refined[mask_dislike] = np.minimum(refined[mask_dislike], -1.0)

    return refined.fillna(0.0)

def recommend_dishes(
    user_profile: Dict,
    selected_dishes: List[Dict],
    dish_pool: List[Dict],
    rating_matrix: pd.DataFrame,
    user_id: str,
    k: int = 5,
    top_n: int = 5,
    orders: Optional[pd.DataFrame] = None,
) -> List[Dict]:
    
    # --- 1. 数据准备与 Refined Matrix 构建 ---
    refined_matrix = build_refined_matrix(rating_matrix, orders=orders, days=60)
    
    # --- 2. 策略一：基于营养缺口的计算 ---
    weight = float(user_profile.get('weight', 60))
    height = float(user_profile.get('height', 170))
    age = int(user_profile.get('age', 25))
    gender = user_profile.get('gender', 'male')
    
    tdee = calculate_bmr(weight, height, age, gender) * get_activity_multiplier(user_profile.get('activity_level', 'sedentary'))
    
    goal = user_profile.get('health_goal', 'maintain')
    target_calories = tdee
    if '减脂' in str(goal): target_calories -= 500
    elif '增肌' in str(goal): target_calories += 300
    
    targets = {
        'calories': target_calories,
        'protein': (target_calories * 0.20) / 4,
        'fat': (target_calories * 0.30) / 9,
        'carbs': (target_calories * 0.50) / 4
    }
    
    current_intake = {k: sum(d.get(k, 0) for d in selected_dishes) for k in targets}
    gaps = {k: targets[k] - current_intake[k] for k in targets}
    macro_gaps = {k: gaps[k] for k in ['protein', 'fat', 'carbs']}
    main_gap_nutrient = max(macro_gaps, key=macro_gaps.get) if any(v > 0 for v in macro_gaps.values()) else 'calories'
    
    nutrient_candidates = []
    for dish in dish_pool:
        score, is_viable = 0, True
        for n in ['calories', 'protein', 'fat', 'carbs']:
            if gaps[n] < 0 and dish.get(n, 0) > 5:
                is_viable = False; break
        
        if is_viable:
            if gaps[main_gap_nutrient] > 0:
                score += (dish.get(main_gap_nutrient, 0) / gaps[main_gap_nutrient]) * 10
            for n, g_val in gaps.items():
                if g_val <= 0: score -= dish.get(n, 0) * 0.5
            if score > 0:
                d_copy = dish.copy(); d_copy['nutrient_score'] = score
                nutrient_candidates.append(d_copy)

    # --- 3. 策略二：微调后的 CF 预测逻辑 ---
    cf_candidates = []
    if refined_matrix is not None and user_id in refined_matrix.index:
        user_ratings = refined_matrix.loc[user_id].fillna(0).values.reshape(1, -1)
        other_users = refined_matrix.drop(index=user_id).fillna(0)
        
        if not other_users.empty:
            similarities = cosine_similarity(user_ratings, other_users.values)[0]
            
            # [微调点 2]：过滤掉相似度 <= 0 的无效邻居，防止噪声干扰
            pos_sim_mask = similarities > 0
            if pos_sim_mask.any():
                valid_sims = similarities[pos_sim_mask]
                valid_others = other_users[pos_sim_mask]
                
                # 获取 Top K 相似索引
                top_k_idx = valid_sims.argsort()[::-1][:k]
                top_k_sims = valid_sims[top_k_idx]
                top_k_ids = valid_others.index[top_k_idx]
                
                pool_ids = [d['id'] for d in dish_pool]
                for dish_id in pool_ids:
                    # [微调点 1]：黑名单保护 - 如果用户显式给过 -1，绝不推荐
                    if dish_id in rating_matrix.columns:
                        if rating_matrix.loc[user_id, dish_id] == -1:
                            continue
                    
                    if dish_id in refined_matrix.columns:
                        neighbor_ratings = refined_matrix.loc[top_k_ids, dish_id]
                        
                        w_sum, sim_sum = 0.0, 0.0
                        for i, (sim, rating) in enumerate(zip(top_k_sims, neighbor_ratings)):
                            if not pd.isna(rating):
                                w_sum += sim * rating
                                sim_sum += sim
                        
                        if sim_sum > 0:
                            pred_score = w_sum / sim_sum
                            if pred_score >= 0:
                                cf_candidates.append({'id': dish_id, 'pred_score': pred_score})

    # --- 4. 策略三：混合权重输出 ---
    cf_score_map = {c['id']: c['pred_score'] for c in cf_candidates}
    dish_map = {d['id']: d for d in dish_pool}
    nutrient_ids = {d['id'] for d in nutrient_candidates}
    cf_ids = {c['id'] for c in cf_candidates}
    common_ids = nutrient_ids.intersection(cf_ids)
    
    final_recs = []
    nutrient_cn = {'calories': '热量', 'protein': '蛋白质', 'fat': '脂肪', 'carbs': '碳水'}
    display_n = nutrient_cn.get(main_gap_nutrient, main_gap_nutrient)

    for did in common_ids:
        dish = dish_map[did].copy()
        # 混合得分权重：口味(0.7) + 营养(0.3)
        dish['final_score'] = cf_score_map[did] * 0.7 + dish.get('nutrient_score', 0) * 0.3
        dish['recommendation_reason'] = f"综合您的复购习惯与{display_n}补充需求推荐"
        final_recs.append(dish)

    # Fallback 逻辑保持不变...
    if len(final_recs) < top_n:
        for dish in sorted(nutrient_candidates, key=lambda x: x['nutrient_score'], reverse=True):
            if dish['id'] not in [r['id'] for r in final_recs]:
                dish['final_score'] = dish['nutrient_score']
                dish['recommendation_reason'] = f"优先补充您的{display_n}缺口"
                final_recs.append(dish)

    final_recs.sort(key=lambda x: x.get('final_score', 0), reverse=True)
    return final_recs[:top_n]