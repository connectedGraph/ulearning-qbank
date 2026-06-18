#!/usr/bin/env python3
import argparse
import html
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

# Align path resolution
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.utils import load_config, get_path

try:
    import jieba.posseg as pseg
    JIEBA_AVAILABLE = True
except ImportError:
    JIEBA_AVAILABLE = False

STOPWORDS = {
    "下列", "属于", "关于", "我国", "什么", "哪些", "哪项", "下列各项", "表明", "体现",
    "规定", "提出", "实现", "进行", "胜利", "开始", "结束", "成立", "问题", "内容",
    "原则", "原因", "特点", "意义", "基础", "事件", "制度", "方面", "时期", "社会",
    "历史", "精神", "目标", "道路", "作风", "建设", "的是", "在于", "一个", "一种",
    "一场", "一次", "主要", "正确", "错误", "时间", "地区", "国家", "人物", "思想",
    "理论", "方针", "路线", "会议", "运动", "革命", "战争",
}


def clean_text(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value or "")
    value = html.unescape(value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def load_results(path: Path) -> dict[int, dict]:
    rows = {}
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        qid = obj.get("questionid")
        if isinstance(qid, int):
            rows[qid] = obj
    return rows


def normalize_tag(tag: str) -> str:
    tag = clean_text(tag)
    replacements = [
        ("中国人民", ""),
        ("中国共产党", "中共"),
        ("中国", ""),
        ("人民", ""),
        ("革命", "革命"),
        ("全面内战", "全面内战"),
    ]
    for src, dst in replacements:
        tag = tag.replace(src, dst)
    return tag.strip("，,。．. ")


def load_model_tags(path: Path) -> dict[int, dict]:
    rows = {}
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        qid = obj.get("questionid")
        source_tags = [clean_text(x) for x in obj.get("source_tags", []) if clean_text(x)]
        canonical_tags = [normalize_tag(x) for x in obj.get("canonical_tags", []) if normalize_tag(x)]
        if isinstance(qid, int) and (source_tags or canonical_tags):
            rows[qid] = {
                "source_tags": source_tags[:4],
                "canonical_tags": canonical_tags[:4],
                "tag_mappings": obj.get("tag_mappings", [])[:8],
            }
    return rows


def phrase_tags(title: str, topk: int = 4) -> list[str]:
    if not JIEBA_AVAILABLE:
        # Graceful fallback when jieba is not installed
        return []
    try:
        raw = [(w.word.strip(), w.flag) for w in pseg.cut(title)]
        raw = [(w, f) for w, f in raw if w and re.search(r"[一-鿿A-Za-z0-9]", w)]
        nounish = ("n", "nr", "ns", "nt", "nz", "vn")

        def is_valid(word: str, flag: str) -> bool:
            if len(word) < 2 or len(word) > 10:
                return False
            if word in STOPWORDS:
                return False
            if re.fullmatch(r"[0-9年月日]+", word):
                return False
            return flag.startswith(nounish)

        tags = []
        current = []
        for word, flag in raw:
            if is_valid(word, flag):
                current.append(word)
            else:
                if current:
                    phrase = "".join(current)
                    if 3 <= len(phrase) <= 12 and phrase not in tags:
                        tags.append(phrase)
                    current = []
        if current:
            phrase = "".join(current)
            if 3 <= len(phrase) <= 12 and phrase not in tags:
                tags.append(phrase)

        for word, flag in raw:
            if is_valid(word, flag) and word not in tags:
                tags.append(word)

        return tags[:topk]
    except Exception as e:
        print(f"警告: 分词提取标签出错: {e}")
        return []


def build_markdown(items: list[dict]) -> str:
    parts = []
    for i, item in enumerate(items, start=1):
        parts.append(
            f"### Q{i}. {item['title']}\n\n"
            f"> **答案：{item['answer'] or '待确认'}**\n\n"
            f"> 解析：{item['analysis'] or '暂无解析'}\n"
        )
    return "\n---\n\n".join(parts)


def build_options(item: dict) -> list[dict]:
    rows = []
    for idx, opt in enumerate(item.get("item", []) or []):
        label = chr(ord("A") + idx)
        text = clean_text(opt.get("title", ""))
        if text:
            rows.append({"label": label, "text": text})
    return rows


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
    ap.add_argument("--paper", default=get_path(config, "question_bank_json", "question_bank.json"))
    ap.add_argument("--results", default=get_path(config, "batch_results_jsonl", "batch_results.jsonl"))
    ap.add_argument("--tags", default=get_path(config, "title_tags_jsonl", "title_tags.jsonl"))
    ap.add_argument("--subjective", default=get_path(config, "subjective_json", "subjective.json"))
    ap.add_argument("--template", default=str(Path(__file__).resolve().parent / "templates" / "viewer_template.html"))
    ap.add_argument("--out", default=get_path(config, "final_html", "final_answers.html"))
    args = ap.parse_args()


    paper_path = Path(args.paper)
    results_path = Path(args.results)
    tags_path = Path(args.tags)
    subjective_path = Path(args.subjective)
    template_path = Path(args.template)
    out_path = Path(args.out)

    if not paper_path.exists():
        print(f"错误: 找不到题库输入文件 {paper_path}，请先运行 analyzer.py")
        return 1

    if not template_path.exists():
        print(f"错误: 找不到网页模板文件 {template_path}")
        return 1

    out_path.parent.mkdir(parents=True, exist_ok=True)

    paper = json.loads(paper_path.read_text(encoding="utf-8"))
    results = load_results(results_path)
    model_tags = load_model_tags(tags_path)

    if not JIEBA_AVAILABLE and not tags_path.exists():
        print("提示: 未安装 'jieba' 库且未找到已生成的标签，网页中将不显示知识点标签。")
        print("提示: 可通过 'pip install jieba' 安装，或者运行 tag_generator.py 抽取标签。")

    items = []
    tag_counts = Counter()
    type_counts = Counter()

    for idx, item in enumerate(paper, start=1):
        qid = item.get("questionid")
        result = results.get(qid, {})
        title = clean_text(item.get("title", ""))
        tag_row = model_tags.get(qid) or {}
        source_tags = tag_row.get("source_tags") or phrase_tags(title, 4)
        canonical_tags = tag_row.get("canonical_tags") or source_tags
        row = {
            "index": idx,
            "questionid": qid,
            "typeTitle": clean_text(item.get("typeTitle", "")),
            "title": title,
            "options": build_options(item),
            "answer": clean_text(result.get("final", "")),
            "analysis": clean_text(result.get("analysis", "")),
            "source_tags": source_tags,
            "canonical_tags": canonical_tags,
            "tag_mappings": tag_row.get("tag_mappings", []),
        }
        items.append(row)
        type_counts[row["typeTitle"]] += 1
        for t in canonical_tags:
            tag_counts[t] += 1

    subjective_chapters = []
    if subjective_path.exists():
        try:
            subj_data = json.loads(subjective_path.read_text(encoding="utf-8"))
            subjective_chapters = subj_data.get("chapters", [])
            print(f"成功加载主观题/复习知识点，共 {len(subjective_chapters)} 个章节")
        except Exception as e:
            print(f"警告: 无法加载主观题数据 {subjective_path}: {e}")

    data = {
        "items": items,
        "types": [{"name": k, "count": v} for k, v in type_counts.items()],
        "tags": [{"name": k, "count": v} for k, v in tag_counts.most_common(60)],
        "allTags": [{"name": k, "count": v} for k, v in tag_counts.most_common()],
        "markdown": build_markdown(items),
        "subjective": subjective_chapters,
    }

    template = template_path.read_text(encoding="utf-8")
    js = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    output_html = template.replace("/*__DATA__*/", f"const DATA={js};")
    out_path.write_text(output_html, encoding="utf-8")
    print(f"网页构建完成！已写入: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
