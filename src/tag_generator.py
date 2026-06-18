#!/usr/bin/env python3
import argparse
import concurrent.futures
import html
import json
import os
import re
import sys
import threading
import time
from pathlib import Path
from urllib import request

# Align path resolution
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.utils import load_config, get_path

DEFAULT_BASE_URL = "http://127.0.0.1:8081/v1"
DEFAULT_API_KEY = "sk-gemini-local"
DEFAULT_MODEL = "gemini-flash-lite"


def clean_text(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value or "")
    value = html.unescape(value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def call_openai(base_url: str, api_key: str, prompt: str, model: str, timeout: int) -> str:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "temperature": 0.1,
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    with request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    obj = json.loads(raw)
    return obj["choices"][0]["message"]["content"]


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


def resolve_answer_text(item: dict, result: dict) -> str:
    final = clean_text(result.get("final", ""))
    if not final:
        return ""
    if not item.get("item"):
        return final
    options = item.get("item") or []
    label_map = {}
    for idx, opt in enumerate(options):
        label = chr(ord("A") + idx)
        label_map[label] = clean_text(opt.get("title", ""))
    picks = re.findall(r"[A-Z]", final.upper())
    if not picks:
        return final
    texts = [label_map[p] for p in picks if p in label_map]
    return " / ".join(texts) if texts else final


def build_prompt(title: str, answer_text: str) -> str:
    return (
        "提取这道题对应的知识点标签，返回 2 到 4 个。\n"
        "只返回 JSON 数组，不要解释。\n"
        "标签要像：资产阶级革命派、中华民国约法、十一届三中全会、护国运动。\n"
        "不要返回泛词。\n\n"
        f"题目：{title}\n"
        f"答案：{answer_text}\n"
    )


def parse_tags(text: str) -> list[str]:
    text = text.strip()
    m = re.search(r"\[[\s\S]*\]", text)
    if not m:
        return []
    try:
        arr = json.loads(m.group(0))
    except json.JSONDecodeError:
        return []
    tags = []
    for x in arr:
        x = clean_text(str(x))
        if 2 <= len(x) <= 12 and x not in tags:
            tags.append(x)
    return tags[:4]


def solve_one(item: dict, result: dict, base_url: str, api_key: str, model: str, max_retries: int) -> dict:
    title = clean_text(item.get("title", ""))
    type_title = clean_text(item.get("typeTitle", ""))
    answer_text = resolve_answer_text(item, result)
    prompt = build_prompt(title, answer_text)
    last = ""
    started = time.time()
    source_tags = []
    raw = ""
    for attempt in range(1, max_retries + 2):
        try:
            raw = call_openai(base_url, api_key, prompt, model, timeout=120)
            source_tags = parse_tags(raw)
            if source_tags:
                break
            last = "empty tags"
        except Exception as exc:
            last = str(exc)
        if attempt < max_retries + 1:
            time.sleep(0.6)
    return {
        "questionid": item.get("questionid"),
        "title": title,
        "typeTitle": type_title,
        "answer_text": answer_text,
        "source_tags": source_tags,
        "canonical_tags": source_tags,
        "raw": raw,
        "error": last if not source_tags else "",
        "elapsed_sec": round(time.time() - started, 3),
    }


def load_done(path: Path) -> set[int]:
    done = set()
    if not path.exists():
        return done
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        qid = row.get("questionid")
        if isinstance(qid, int) and row.get("source_tags"):
            done.add(qid)
    return done


def main() -> int:
    # Pre-parse --config to load the correct paths/settings
    pre_ap = argparse.ArgumentParser(add_help=False)
    pre_ap.add_argument("--config", default="config.json")
    pre_args, _ = pre_ap.parse_known_args()

    try:
        config = load_config(pre_args.config, validate_crawler=False)
    except Exception:
        config = {}

    openai_cfg = config.get("openai", {})

    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.json", help="Path to config file")
    ap.add_argument("--paper", default=get_path(config, "question_bank_json", "question_bank.json"))
    ap.add_argument("--results", default=get_path(config, "batch_results_jsonl", "batch_results.jsonl"))
    ap.add_argument("--out", default=get_path(config, "title_tags_jsonl", "title_tags.jsonl"))
    ap.add_argument("--base-url", default=os.environ.get("WEB2API_BASE_URL", openai_cfg.get("base_url", DEFAULT_BASE_URL)))
    ap.add_argument("--api-key", default=os.environ.get("WEB2API_API_KEY", openai_cfg.get("api_key", DEFAULT_API_KEY)))
    ap.add_argument("--model", default=os.environ.get("WEB2API_MODEL", openai_cfg.get("model", DEFAULT_MODEL)))
    ap.add_argument("--concurrency", type=int, default=openai_cfg.get("concurrency", 50))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--max-retries", type=int, default=2)
    args = ap.parse_args()


    paper_path = Path(args.paper)
    results_path = Path(args.results)
    out_path = Path(args.out)

    if not paper_path.exists():
        print(f"错误: 题库文件不存在 {paper_path}，请先运行 analyzer.py")
        return 1

    if not results_path.exists():
        print(f"错误: 解答结果文件不存在 {results_path}，请先运行 solver.py")
        return 1

    out_path.parent.mkdir(parents=True, exist_ok=True)

    paper = json.loads(paper_path.read_text(encoding="utf-8"))
    results = load_results(results_path)

    if args.limit > 0:
        paper = paper[:args.limit]
    done = load_done(out_path) if args.resume else set()
    items = [x for x in paper if x.get("questionid") not in done]

    if not args.resume:
        out_path.write_text("", encoding="utf-8")

    total = len(items)
    if total == 0:
        print("没有需要生成标签的题目 / No questions to tag.")
        return 0

    completed = 0
    lock = threading.Lock()

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as pool:
        futures = [
            pool.submit(
                solve_one,
                item,
                results.get(item.get("questionid"), {}),
                args.base_url,
                args.api_key,
                args.model,
                args.max_retries,
            )
            for item in items
        ]
        for fut in concurrent.futures.as_completed(futures):
            row = fut.result()
            with lock:
                with open(out_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
            completed += 1
            tags = ", ".join(row["source_tags"]) if row["source_tags"] else f"ERROR: {row['error']}"
            print(f"[{completed}/{total}] {row['questionid']} -> {tags} ({row['elapsed_sec']}s)")

    print(f"written: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
