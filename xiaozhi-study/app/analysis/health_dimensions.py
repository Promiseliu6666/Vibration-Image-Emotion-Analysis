"""健康维度分类：把 13 种状态归入四个健康维度。

同一状态可以同时计入多个维度 —— 阅读既属于"用眼负荷"（近距离用眼），
也属于"久坐与体态"（静态久坐）。因此这是**标签式归属，不是互斥分类**，
各维度占比之和会大于 100%，界面上必须如实说明这一点。

本文件是唯一事实来源；前端对应 static/health-dimensions.js，两边必须保持一致。
"""

DIMENSIONS = [
    {"key": "vision",    "label": "用眼负荷",   "hint": "持续近距离与屏幕用眼"},
    {"key": "sedentary", "label": "久坐与体态", "hint": "静态久坐、坐姿与活动"},
    {"key": "attention", "label": "注意力与心理", "hint": "学习活动、手机使用与视线变化"},
    {"key": "rhythm",    "label": "作息与休息", "hint": "休息与疲劳节律"},
]

STATES = {
    "vision": ["engaged_reading", "engaged_writing", "engaged_screen",
               "engaged_computer", "distracted_phone", "fatigued"],
    "sedentary": ["engaged_reading", "engaged_writing", "engaged_screen",
                  "engaged_computer", "engaged_discussing", "distracted_phone",
                  "standing", "resting"],
    "attention": ["engaged_reading", "engaged_writing", "engaged_screen",
                  "engaged_computer", "engaged_hand_raising", "engaged_discussing",
                  "distracted_phone", "distracted_away", "resting", "fatigued"],
    "rhythm": ["resting", "fatigued"],
}

# 维度内部的方向性：偏正向 / 偏风险，用于在占比之外再给一个方向
POSITIVE = {
    "sedentary": ["standing"],
    "attention": ["engaged_reading", "engaged_writing", "engaged_screen",
                  "engaged_computer", "engaged_hand_raising", "engaged_discussing"],
    "rhythm": ["resting"],
}
RISK = {
    "sedentary": ["resting"],
    "attention": ["distracted_phone", "distracted_away", "resting", "fatigued"],
    "rhythm": ["fatigued"],
}

# ---- 主归属：每个状态恰好一个，用于"时间构成"这类需要加总的呈现 ----
# 说明：STATES 是标签式归属（可重叠，占比之和会>100%）；
# PRIMARY 是互斥归属（每个状态只算一次，占比之和 = 100%）。
# 主归属的取舍逻辑：这个状态最该被干预的那个健康维度。
PRIMARY_LABELS = {
    "vision": "用眼负荷",
    "sedentary": "久坐与体态",
    "attention": "注意力",
    "data": "数据状态",
}

PRIMARY = {
    "engaged_reading": "vision",
    "engaged_writing": "vision",
    "engaged_screen": "vision",
    "engaged_computer": "vision",
    "distracted_phone": "vision",
    "fatigued": "vision",
    "engaged_discussing": "sedentary",
    "standing": "sedentary",
    "resting": "sedentary",
    "distracted_away": "attention",
    "engaged_hand_raising": "attention",
    "thinking": "data",
    "absent": "data",
}


def primary_bucket(state):
    """未知状态一律归入"数据状态"，不猜成健康维度。"""
    return PRIMARY.get(state, "data")


def primary_summary(counts, total):
    """互斥主归属汇总：四个桶的占比之和为 100%（total>0 时）。"""
    total = int(total or 0)
    buckets = {k: 0 for k in PRIMARY_LABELS}
    for state, n in (counts or {}).items():
        buckets[primary_bucket(state)] += int(n or 0)
    out = []
    for key, label in PRIMARY_LABELS.items():
        n = buckets[key]
        out.append({
            "key": key,
            "label": label,
            "samples": n,
            "pct": round(n / total * 100, 1) if total else None,
        })
    return out


def summarize(counts, total):
    """把 {状态码: 样本数} 汇总成四个维度的占比。

    counts 为 0/空时返回占比 None，交由界面显示"—"，不编造 0%。
    """
    total = int(total or 0)

    def share(n):
        return round(n / total * 100, 1) if total else None

    out = []
    for dim in DIMENSIONS:
        key = dim["key"]
        members = STATES[key]
        samples = sum(int(counts.get(s, 0) or 0) for s in members)
        positive = sum(int(counts.get(s, 0) or 0) for s in POSITIVE.get(key, []))
        risk = sum(int(counts.get(s, 0) or 0) for s in RISK.get(key, []))
        out.append({
            "key": key,
            "label": dim["label"],
            "hint": dim["hint"],
            "samples": samples,
            "pct": share(samples),
            "positive_pct": share(positive),
            "risk_pct": share(risk),
            "members": [{"state": s, "count": int(counts.get(s, 0) or 0)}
                        for s in members if counts.get(s)],
        })
    return out
