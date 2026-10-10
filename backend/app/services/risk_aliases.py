"""统一风险分类的别名词典。

各家 Benchmark 对同一风险有不同说法：HarmBench 直接给 ``chemical_biological``，
中文数据集写"生化武器"，有些写 ``CBRN``。别名词典把这些说法收敛到同一个
统一风险类别上，这是"统一风险分类"能跨 Benchmark 成立的关键。

词典以统一 ``risk_categories.code`` 为锚点，不绑定具体 taxonomy 的主键，
因此换一套风险体系、或者用户自建 taxonomy 时依然可用：只有该 taxonomy 里
真实存在的 code 才会被播种。
"""
from sqlalchemy import select

from app.db.models import RiskCategory, RiskLabelAlias, RiskTaxonomy

#: 统一风险 code -> 常见别名（中英文、缩写、同义表述）
BUILTIN_ALIASES: dict[str, tuple[str, ...]] = {
    "chemical_biological": (
        "化生武器",
        "生化武器",
        "生物武器",
        "化学武器",
        "大规模杀伤性武器",
        "cbrn",
        "chemical",
        "biological",
        "bio",
        "bioweapon",
        "weapons",
        "wmd",
    ),
    "cybercrime_intrusion": (
        "网络犯罪",
        "网络入侵",
        "网络攻击",
        "黑客攻击",
        "恶意代码",
        "漏洞利用",
        "cybercrime",
        "cyber",
        "hacking",
        "intrusion",
        "malware",
        "exploit",
    ),
    "illegal": (
        "违法行为",
        "非法行为",
        "非法活动",
        "犯罪",
        "诈骗",
        "illegal",
        "crime",
        "unlawful",
        "fraud",
    ),
    "misinformation_disinformation": (
        "虚假信息",
        "错误信息",
        "不实信息",
        "谣言",
        "造谣",
        "misinformation",
        "disinformation",
        "fake news",
        "propaganda",
    ),
    "harassment_bullying": (
        "骚扰",
        "霸凌",
        "欺凌",
        "人身攻击",
        "仇恨言论",
        "歧视",
        "harassment",
        "bullying",
        "hate speech",
        "hate",
    ),
    "harmful": (
        "一般有害内容",
        "有害内容",
        "有害",
        "不安全内容",
        "暴力",
        "色情",
        "自残",
        "harmful",
        "unsafe",
        "toxic",
        "violence",
        "self-harm",
    ),
    "copyright": (
        "版权侵权",
        "版权",
        "侵权",
        "盗版",
        "copyright",
        "intellectual property",
        "piracy",
    ),
}


def resolve_default_taxonomy_id(uow) -> int | None:
    """没显式传 taxonomy 时，取默认 taxonomy；没有默认则取第一个。"""
    defaults = uow.risk_taxonomies.list(page=1, page_size=1, is_default=True)
    if defaults:
        return defaults[0].id
    any_taxonomy = uow.risk_taxonomies.list(page=1, page_size=1, order_by=RiskTaxonomy.id.asc())
    return any_taxonomy[0].id if any_taxonomy else None


def ensure_builtin_aliases(uow, taxonomy_id: int) -> int:
    """为该 taxonomy 补齐内置别名，返回新增条数。已存在的不重复插入。"""
    categories = uow.session.scalars(
        select(RiskCategory).where(RiskCategory.taxonomy_id == taxonomy_id)
    ).all()
    category_by_code = {category.code: category for category in categories}
    if not category_by_code:
        return 0

    existing = {
        row.alias
        for row in uow.risk_label_aliases.list(page=1, page_size=1000, taxonomy_id=taxonomy_id)
    }

    created = 0
    for code, aliases in BUILTIN_ALIASES.items():
        category = category_by_code.get(code)
        if category is None:
            continue
        for alias in aliases:
            if alias in existing:
                continue
            uow.risk_label_aliases.add(
                RiskLabelAlias(
                    taxonomy_id=taxonomy_id,
                    alias=alias,
                    risk_category_id=category.id,
                    source="builtin",
                    confidence=0.9,
                    note="系统内置别名词典",
                )
            )
            existing.add(alias)
            created += 1
    return created
