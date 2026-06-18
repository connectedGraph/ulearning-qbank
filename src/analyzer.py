import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.utils import load_config, decode_html_entities, get_path

def load_papers(papers_dir):
    papers = []
    if not os.path.exists(papers_dir):
        return papers
    for filename in os.listdir(papers_dir):
        if not filename.endswith(".json"):
            continue
        filepath = os.path.join(papers_dir, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data.get("code") == 1 and data.get("result"):
                    papers.append(data)
        except Exception as e:
            print(f"警告 / Warning: 无法加载 {filename}: {e}")
    return papers


def extract_questions(papers):
    question_dict = {}
    question_frequency = Counter()

    for paper in papers:
        parts = paper.get("result", {}).get("part", [])
        for part in parts:
            for child in part.get("children", []):
                qid = child.get("questionid")
                if not qid:
                    continue

                question_frequency[qid] += 1

                if qid not in question_dict:
                    title = decode_html_entities(child.get("title", ""))
                    items = child.get("item", [])
                    decoded_items = [
                        {**item, "title": decode_html_entities(item.get("title", ""))}
                        for item in items
                    ]

                    question_dict[qid] = {
                        "questionid": qid,
                        "title": title,
                        "typeTitle": child.get("typeTitle", ""),
                        "type": child.get("type"),
                        "score": child.get("score", 0),
                        "item": decoded_items,
                        "correctreply": child.get("correctreply", "")
                    }

    return list(question_dict.values()), question_frequency

def export_json(questions, output_path):
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(questions, f, indent=2, ensure_ascii=False)

def export_markdown(questions, output_path):
    type_groups = {"判断题": [], "单选题": [], "多选题": [], "其他": []}

    for q in questions:
        type_name = q["typeTitle"]
        if type_name in type_groups:
            type_groups[type_name].append(q)
        else:
            type_groups["其他"].append(q)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# 题库导出 / Question Bank Export\n\n")
        f.write(f"共包含 **{len(questions)}** 道独立题目 / Total {len(questions)} unique questions\n\n")

        for type_name, questions_in_type in type_groups.items():
            if not questions_in_type:
                continue

            f.write(f"## {type_name} (共 {len(questions_in_type)} 题)\n\n")

            for idx, q in enumerate(questions_in_type, 1):
                f.write(f"### Q{idx}. {q['title']} (ID: {q['questionid']})\n\n")

                if q["item"]:
                    choices = ["A", "B", "C", "D", "E", "F", "G", "H"]
                    for i, item in enumerate(q["item"]):
                        if i < len(choices):
                            f.write(f"{choices[i]}. {item['title']}\n")
                    f.write("\n")

                answer = q["correctreply"] or "暂无（服务器未下发此题答案解析）"
                f.write(f"> **参考答案/解析**：{answer}\n\n---\n\n")

def main():
    print("=== Ulearning 题库分析工具 / Question Bank Analyzer ===\n")

    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.json", help="Path to config file")
    args = parser.parse_known_args()[0]

    try:
        config = load_config(args.config, validate_crawler=False)
    except Exception as e:

        print(f"提示 / Info: {e}. 将使用默认路径配置。\n")
        config = {}

    papers_dir = get_path(config, "papers_dir", "papers_json")
    json_output = get_path(config, "question_bank_json", "question_bank.json")
    md_output = get_path(config, "question_bank_md", "question_bank.md")


    if not os.path.exists(papers_dir):
        print(f"错误 / ERROR: 找不到 {papers_dir} 目录")
        print(f"请先运行 downloader.py 下载试卷 / Please run downloader.py first")
        return

    print(f"加载试卷 / Loading papers from {papers_dir}...")
    papers = load_papers(papers_dir)
    print(f"成功加载 {len(papers)} 份试卷 / Loaded {len(papers)} papers\n")

    print("提取并去重题目 / Extracting and deduplicating questions...")
    questions, frequency = extract_questions(papers)
    print(f"去重后共 {len(questions)} 道题目 / Total {len(questions)} unique questions\n")

    print(f"导出 JSON / Exporting JSON to {json_output}...")
    export_json(questions, json_output)

    print(f"导出 Markdown / Exporting Markdown to {md_output}...")
    export_markdown(questions, md_output)

    print("\n完成 / Completed!")
    print(f"  - JSON: {json_output}")
    print(f"  - Markdown: {md_output}")

    freq_dist = Counter(frequency.values())
    print(f"\n题目频次分布 / Question Frequency Distribution:")
    for count in sorted(freq_dist.keys()):
        print(f"  出现 {count} 次: {freq_dist[count]} 道题")

if __name__ == "__main__":
    main()
