from __future__ import annotations

import hashlib
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.content import EvidenceSource, KnowledgeItem


ORDINARY_SOURCE_REF = "ordinary-demo@2026-09-21"
NHC_2024_SOURCE_REF = "nhc-food-medicine-2024-4@2024-08-12"


INGREDIENT_SPECS = [
    ("water", "饮用水", "Water", "液体", ["直接使用", "煮沸"], []),
    ("oats", "燕麦", "Avena sativa L.", "籽粒", ["煮制", "焖制"], ["含麸质谷物交叉接触风险"]),
    ("apple", "苹果", "Malus domestica Borkh.", "果实", ["清洗生食", "切块煮制"], []),
    ("millet", "小米", "Setaria italica (L.) P.Beauv.", "籽粒", ["淘洗", "煮制"], []),
    ("pumpkin", "南瓜", "Cucurbita moschata Duchesne", "果肉", ["去皮去籽", "蒸煮"], []),
    ("tomato", "番茄", "Solanum lycopersicum L.", "果实", ["清洗", "切块熟制"], []),
    ("egg", "鸡蛋", "Gallus gallus domesticus", "卵", ["去壳", "彻底加热"], ["鸡蛋"]),
    ("napa_cabbage", "大白菜", "Brassica rapa subsp. pekinensis", "叶球", ["清洗", "切段熟制"], []),
    ("tofu", "北豆腐", "Glycine max (L.) Merr.", "豆制品", ["切块", "充分加热"], ["大豆"]),
    ("shiitake", "香菇", "Lentinula edodes", "子实体", ["清洗", "切片熟制"], []),
    ("bok_choy", "小白菜", "Brassica rapa subsp. chinensis", "叶及叶柄", ["清洗", "切段熟制"], []),
    ("carrot", "胡萝卜", "Daucus carota subsp. sativus", "肉质根", ["去皮", "切块熟制"], []),
    ("chicken_breast", "鸡胸肉", "Gallus gallus domesticus", "胸肌", ["去皮切块", "彻底加热"], []),
    ("rice", "大米", "Oryza sativa L.", "籽粒", ["淘洗", "煮制"], []),
    ("pear", "梨", "Pyrus pyrifolia (Burm.f.) Nakai", "果实", ["清洗去核", "切块煮制"], []),
    ("banana", "香蕉", "Musa acuminata Colla", "果实", ["去皮", "切片"], []),
    ("buckwheat_noodle", "荞麦面", "Fagopyrum esculentum Moench", "籽粒加工品", ["沸水煮制", "过凉开水"], ["荞麦", "含麸质谷物交叉接触风险"]),
    ("cucumber", "黄瓜", "Cucumis sativus L.", "果实", ["清洗", "切丝"], []),
    ("potato", "马铃薯", "Solanum tuberosum L.", "块茎", ["去皮去芽", "彻底熟制"], []),
    ("sweet_potato", "甘薯", "Ipomoea batatas (L.) Lam.", "块根", ["清洗去皮", "蒸煮"], []),
    ("broccoli", "西兰花", "Brassica oleracea var. italica", "花球及嫩茎", ["清洗切小朵", "熟制"], []),
    ("corn", "甜玉米", "Zea mays L.", "籽粒", ["清洗", "煮制"], []),
    ("green_peas", "青豌豆", "Pisum sativum L.", "种子", ["清洗", "彻底熟制"], []),
    ("sesame_oil", "芝麻油", "Sesamum indicum L.", "种子压榨油", ["拌入熟食"], ["芝麻"]),
]


FOOD_MEDICINE_SPECS = [
    ("rehmannia_root", "地黄", "Rehmannia glutinosa Libosch.", "块根"),
    ("ophiopogon_root", "麦冬", "Ophiopogon japonicus (L.f.) Ker Gawl.", "块根"),
    ("asparagus_cochinchinensis_root", "天冬", "Asparagus cochinchinensis (Lour.) Merr.", "块根"),
    (
        "citrus_grandis_peel",
        "化橘红",
        "Citrus grandis 'Tomentosa' 或 Citrus grandis (L.) Osbeck",
        "外层果皮",
    ),
]


RECIPE_SPECS = [
    ("oat_apple_porridge", "燕麦苹果粥", [("oats", 45), ("apple", 120), ("water", 500)], "pear"),
    ("millet_pumpkin_porridge", "小米南瓜粥", [("millet", 50), ("pumpkin", 120), ("water", 550)], "sweet_potato"),
    ("tomato_egg_soup", "番茄鸡蛋汤", [("tomato", 180), ("egg", 55), ("water", 450)], "tofu"),
    ("cabbage_tofu_soup", "白菜豆腐汤", [("napa_cabbage", 180), ("tofu", 120), ("water", 500)], "bok_choy"),
    ("shiitake_bokchoy_tofu", "香菇小白菜烧豆腐", [("shiitake", 60), ("bok_choy", 180), ("tofu", 150)], "napa_cabbage"),
    ("carrot_chicken_rice_porridge", "胡萝卜鸡肉米粥", [("carrot", 80), ("chicken_breast", 80), ("rice", 50), ("water", 600)], "pumpkin"),
    ("buckwheat_cucumber_noodles", "黄瓜荞麦面", [("buckwheat_noodle", 90), ("cucumber", 100), ("sesame_oil", 4)], "bok_choy"),
    ("broccoli_chicken_rice", "西兰花鸡肉饭", [("broccoli", 150), ("chicken_breast", 100), ("rice", 70)], "carrot"),
    ("corn_pea_rice", "玉米豌豆饭", [("corn", 80), ("green_peas", 60), ("rice", 70)], "carrot"),
    ("sweet_potato_millet_porridge", "甘薯小米粥", [("sweet_potato", 130), ("millet", 50), ("water", 550)], "pumpkin"),
    ("pear_oat_porridge", "梨燕麦粥", [("pear", 130), ("oats", 45), ("water", 500)], "apple"),
    ("banana_oat_bowl", "香蕉燕麦碗", [("banana", 100), ("oats", 45), ("water", 260)], "apple"),
    ("potato_carrot_chicken_stew", "土豆胡萝卜鸡肉炖", [("potato", 150), ("carrot", 90), ("chicken_breast", 110), ("water", 300)], "sweet_potato"),
    ("tomato_tofu_soup", "番茄豆腐汤", [("tomato", 180), ("tofu", 140), ("water", 450)], "napa_cabbage"),
    ("shiitake_chicken_rice", "香菇鸡肉饭", [("shiitake", 60), ("chicken_breast", 100), ("rice", 70)], "green_peas"),
    ("pumpkin_oat_porridge", "南瓜燕麦粥", [("pumpkin", 130), ("oats", 45), ("water", 520)], "sweet_potato"),
    ("bokchoy_egg_soup", "小白菜鸡蛋汤", [("bok_choy", 180), ("egg", 55), ("water", 450)], "tofu"),
    ("broccoli_tofu", "西兰花烧豆腐", [("broccoli", 160), ("tofu", 150), ("water", 120)], "napa_cabbage"),
    ("corn_chicken_porridge", "玉米鸡肉粥", [("corn", 80), ("chicken_breast", 80), ("rice", 50), ("water", 600)], "green_peas"),
    ("apple_millet_porridge", "苹果小米粥", [("apple", 120), ("millet", 50), ("water", 550)], "pear"),
]


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _ingredient_payload(
    latin_species: str,
    edible_part: str,
    methods: list[str],
    allergens: list[str],
) -> dict:
    return {
        "aliases": [],
        "latin_species": latin_species,
        "edible_part": edible_part,
        "category": "ordinary_food",
        "processing_methods": methods,
        "allergens": allergens,
        "contraindication_codes": [],
        "catalog_status": "ordinary_food",
        "catalog_ref": "合成演示食材清单；发布前须由专业人员复核",
        "source_refs": [ORDINARY_SOURCE_REF],
    }


def _recipe_payload(materials: list[tuple[str, int]], replacement: str) -> dict:
    material_payload = []
    for index, (code, grams) in enumerate(materials):
        substitutions = []
        if index == 0 and replacement != code:
            substitutions.append(
                {
                    "code": replacement,
                    "version": "1.0.0",
                    "ratio": 1.0,
                    "note": "按相同可食重量替换，仍需核对个人禁忌和口感。",
                }
            )
        material_payload.append(
            {
                "code": code,
                "version": "1.0.0",
                "grams": grams,
                "edible_part": "按食材条目记录的可食部",
                "preparation": "清洗并按食材条目的加工要求预处理",
                "substitutions": substitutions,
            }
        )

    material_codes = {code for code, _grams in materials}
    contraindications = []
    if "egg" in material_codes:
        contraindications.append("egg_allergy")
    if "tofu" in material_codes:
        contraindications.append("soy_allergy")
    if "buckwheat_noodle" in material_codes:
        contraindications.append("buckwheat_allergy")
    return {
        "servings": 2,
        "goal_statement": "提供可重复称量和记录的家庭餐食模板。",
        "target_tags": ["家庭烹饪", "称重记录", "合成演示"],
        "materials": material_payload,
        "preprocessing": [
            "使用厨房秤记录各材料可食部重量。",
            "生熟食器具分开，肉蛋类按条目要求彻底加热。",
        ],
        "steps": [
            {
                "order": 1,
                "instruction": "完成所有材料的清洗、称量和切配。",
                "duration_minutes": 8,
                "heat": "不开火",
                "cookware": ["厨房秤", "砧板", "刀具"],
            },
            {
                "order": 2,
                "instruction": "将需熟制材料放入锅中，按材料特点加热至完全熟透。",
                "duration_minutes": 18,
                "heat": "中火后转小火",
                "cookware": ["带盖汤锅", "锅铲"],
            },
            {
                "order": 3,
                "instruction": "关火后分成两份，记录实际食用量和剩余量。",
                "duration_minutes": 3,
                "heat": "关火",
                "cookware": ["餐碗", "厨房秤"],
            },
        ],
        "frequency": "由后续经审核的个人周计划安排，不依据本草稿自行增加频次。",
        "cycle": "按已确认方案周期使用，并记录每次实际份量。",
        "serving_note": "每份约为成品的一半；实际份量以称重记录为准。",
        "nutrition_tags": ["份量可量化", "家庭食材"],
        "contraindication_codes": contraindications,
        "caution": "本条目是合成候审食谱，不提供诊断或用药建议；过敏、特殊疾病、孕哺期及医生限制须先由专业人员确认。",
        "source_refs": [ORDINARY_SOURCE_REF],
    }


def _add_if_missing(db: Session, item: KnowledgeItem) -> None:
    existing = db.scalar(
        select(KnowledgeItem).where(
            KnowledgeItem.content_type == item.content_type,
            KnowledgeItem.code == item.code,
            KnowledgeItem.version == item.version,
        )
    )
    if existing is None:
        db.add(item)


def seed_content_knowledge(db: Session) -> None:
    checked_at = datetime(2026, 9, 21, tzinfo=timezone.utc)
    sources = [
        EvidenceSource(
            id="source-ordinary-demo-2026",
            code="ordinary-demo",
            version="2026-09-21",
            title="M4 合成普通食材与家庭食谱演示来源",
            publisher="云循开发演示",
            url_or_archive_ref="internal://synthetic-demo/m4-content",
            published_on=date(2026, 9, 21),
            jurisdiction="演示环境",
            content_hash=_digest("ordinary-demo|2026-09-21|synthetic-only"),
            status="active",
            checked_at=checked_at,
        ),
        EvidenceSource(
            id="source-nhc-food-medicine-2024-4",
            code="nhc-food-medicine-2024-4",
            version="2024-08-12",
            title="关于地黄等4种按照传统既是食品又是中药材的物质的公告",
            publisher="中华人民共和国国家卫生健康委员会、国家市场监督管理总局",
            url_or_archive_ref="https://www.nhc.gov.cn/wjw/c100175/202408/15135932f4a34553b1bd88b203282ecb.shtml",
            published_on=date(2024, 8, 12),
            jurisdiction="中华人民共和国",
            content_hash=_digest("nhc|2024-17|rehmannia|ophiopogon|asparagus|citrus-grandis"),
            status="active",
            checked_at=checked_at,
        ),
    ]
    for source in sources:
        existing = db.scalar(
            select(EvidenceSource).where(
                EvidenceSource.code == source.code,
                EvidenceSource.version == source.version,
            )
        )
        if existing is None:
            db.add(source)
    db.flush()

    for code, title, species, part, methods, allergens in INGREDIENT_SPECS:
        _add_if_missing(
            db,
            KnowledgeItem(
                id=f"ingredient-{code}-v1",
                content_type="ingredient",
                code=code,
                version="1.0.0",
                title=title,
                payload=_ingredient_payload(species, part, methods, allergens),
                status="draft",
                is_active=False,
                created_by="synthetic-seed",
            ),
        )

    for code, title, species, part in FOOD_MEDICINE_SPECS:
        _add_if_missing(
            db,
            KnowledgeItem(
                id=f"ingredient-{code}-v1",
                content_type="ingredient",
                code=code,
                version="1.0.0",
                title=title,
                payload={
                    "aliases": [],
                    "latin_species": species,
                    "edible_part": part,
                    "category": "food_medicine",
                    "processing_methods": ["仅按公告及后续专业审核确认的方式使用"],
                    "allergens": [],
                    "contraindication_codes": [],
                    "catalog_status": "listed",
                    "catalog_ref": "国家卫生健康委员会、国家市场监督管理总局公告2024年第17号",
                    "source_refs": [NHC_2024_SOURCE_REF],
                },
                status="draft",
                is_active=False,
                created_by="synthetic-seed",
            ),
        )

    contraindications = [
        ("egg_allergy", "鸡蛋过敏拦截", "egg", ["鸡蛋", "蛋类"]),
        ("soy_allergy", "大豆过敏拦截", "tofu", ["大豆", "豆制品"]),
        ("buckwheat_allergy", "荞麦过敏拦截", "buckwheat_noodle", ["荞麦"]),
    ]
    for code, title, subject_code, trigger_values in contraindications:
        _add_if_missing(
            db,
            KnowledgeItem(
                id=f"contraindication-{code}-v1",
                content_type="contraindication",
                code=code,
                version="1.0.0",
                title=title,
                payload={
                    "subject_type": "ingredient",
                    "subject_code": subject_code,
                    "trigger_type": "allergy",
                    "trigger_values": trigger_values,
                    "action": "block",
                    "message": "用户记录相关过敏时不得生成包含该食材的方案。",
                    "source_refs": [ORDINARY_SOURCE_REF],
                },
                status="draft",
                is_active=False,
                created_by="synthetic-seed",
            ),
        )

    for code, title, materials, replacement in RECIPE_SPECS:
        _add_if_missing(
            db,
            KnowledgeItem(
                id=f"recipe-{code}-v1",
                content_type="recipe",
                code=code,
                version="1.0.0",
                title=title,
                payload=_recipe_payload(materials, replacement),
                status="draft",
                is_active=False,
                created_by="synthetic-seed",
            ),
        )

    db.commit()
