#!/usr/bin/env python3
import argparse
import json
import os
import re
import sys
from pathlib import Path

# Align path resolution
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.utils import load_config, get_path

SAFE_REWRITES = [
    (r"百日维新", "戊戌变法", "event_alias"),
    (r"戊戌维新", "戊戌变法", "event_alias"),
    (r"光绪帝|光绪皇帝|清德宗", "光绪", "person_title_strip"),
    (r"中国人民解放战争|人民解放战争|解放战争时期", "解放战争", "war_alias"),
    (r"全面内战的爆发|全面内战爆发|国民党反动派发动全面内战", "全面内战", "war_alias"),
    (r"国民党和共产党关系|国共两党关系|国共合作关系", "国共关系", "relation_alias"),
    (r"抗美援朝战争", "抗美援朝", "war_alias"),
    (r"辛亥革命.*", "辛亥革命", "event_trim"),
    (r"十一届三中全会.*", "十一届三中全会", "event_trim"),
    (r"遵义会议.*", "遵义会议", "event_trim"),
    (r"护国运动.*", "护国运动", "event_trim"),
    (r"中华民国临时约法", "中华民国临时约法", "exact"),
    (r"中华民国约法", "中华民国约法", "exact"),
]

GENERIC_BAD = {
    "思想", "理论", "总要求", "方针", "路线", "性质", "原因", "基础", "制度", "精神",
    "目标", "特征", "原则", "社会", "前提", "探索", "时期", "历史事件", "意义",
}

EVENT_HINTS = (
    "战争", "战役", "会议", "运动", "事变", "条约", "约法", "纲领", "谈判", "起义",
    "变法", "改革", "革命", "合作", "关系", "内战", "抗战", "政变", "全会",
)

DROP_ENDINGS = ("撤回", "提出", "召开", "告诫", "保持", "形成", "纠正", "实现", "标志")


def norm(tag: str) -> tuple[str, str]:
    tag = re.sub(r"\s+", "", str(tag or ""))
    tag = tag.strip("，,。．.；;：:、\"'`()（）[]【】")
    for pat, repl, rule_id in SAFE_REWRITES:
        if re.fullmatch(pat, tag):
            return repl, rule_id
    return tag, "exact"


def keep_canonical(tag: str) -> bool:
    if not tag or len(tag) < 2 or len(tag) > 12:
        return False
    if any(x in tag for x in GENERIC_BAD):
        return False
    if tag.endswith(DROP_ENDINGS):
        return False
    if any(x in tag for x in EVENT_HINTS):
        return True
    if 2 <= len(tag) <= 4:
        return True
    return False


def main() -> int:
    # Pre-parse --config to load the correct paths/settings
    pre_ap = argparse.ArgumentParser(add_help=False)
    pre_ap.add_argument("--config", default="config.json")
    pre_args, _ = pre_ap.parse_known_args()

    try:
        config = load_config(pre_args.config, validate_crawler=False)
    except Exception:
        config = {}

    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.json", help="Path to config file")
    ap.add_argument("--tags", default=get_path(config, "title_tags_jsonl", "title_tags.jsonl"))
    args = ap.parse_args()


    tags_path = Path(args.tags)
    if not tags_path.exists():
        print(f"错误: 标签文件不存在 {tags_path}，请先运行 tag_generator.py")
        return 1

    rows = []
    for line in tags_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        source = row.get("source_tags", []) or row.get("tags", []) or []
        canon = []
        mappings = []
        seen = set()
        for tag in source:
            t, rule_id = norm(tag)
            if not keep_canonical(t):
                continue
            if t in seen:
                continue
            seen.add(t)
            canon.append(t)
            mappings.append({
                "source_tag": tag,
                "canonical_tag": t,
                "rule_id": rule_id,
                "evidence": row.get("title", ""),
            })
        row["canonical_tags"] = canon[:4]
        row["tag_mappings"] = mappings[:4]
        rows.append(row)

    tags_path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    print(f"normalized {len(rows)} rows and saved back to {tags_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
