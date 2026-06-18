#!/usr/bin/env python3
import argparse
import concurrent.futures
import datetime as dt
import html
import json
import os
import random
import re
import sys
import threading
import time
from pathlib import Path
from typing import Any
from urllib import request

# Align path resolution
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.utils import load_config, get_path

DEFAULT_BASE_URL = "http://127.0.0.1:8081/v1"
DEFAULT_API_KEY = "sk-gemini-local"
DEFAULT_MODEL = "gemini-flash-lite"
DEFAULT_RPM = 30
OPTION_LABELS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def load_questions(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"未找到输入题目文件: {path}，请先运行 analyzer.py / input file not found.")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("expected JSON array")
    return data


def clean_text(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value or "")
    value = html.unescape(value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def build_prompt(item: dict[str, Any]) -> str:
    title = clean_text(item.get("title", ""))
    options = item.get("item") or []
    option_lines = []
    for idx, opt in enumerate(options, start=1):
        label = OPTION_LABELS[idx - 1] if idx - 1 < len(OPTION_LABELS) else str(idx)
        option_lines.append(f"{label}. {clean_text(opt.get('title', ''))}")
    option_block = "\n".join(option_lines)
    return (
        "请只输出 XML，格式必须严格为："
        "<think>...</think><analysis>...</analysis><final>...</final>\n"
        "其中 <think> 必须非常短，控制在 10 到 30 个汉字以内。\n"
        "<analysis> 用于简要分析题目，简单题简单分析，困难题列提纲。\n"
        "<final> 只写最终答案本身，不要解释；单选/多选优先写选项字母，判断题写 对 或 错。\n\n"
        f"题目：{title}\n"
        f"题型：{clean_text(item.get('typeTitle', ''))}\n"
        f"选项：\n{option_block if option_block else '无'}\n"
    )


def extract_tag(text: str, tag: str) -> str:
    m = re.search(rf"<{tag}>(.*?)</{tag}>", text, re.S | re.I)
    return m.group(1).strip() if m else ""


def shorten_think(text: str, max_chars: int = 30) -> str:
    text = clean_text(text)
    return text[:max_chars]


def answer_line(item: dict[str, Any], final: str) -> str:
    final = clean_text(final)
    type_title = clean_text(item.get("typeTitle", ""))
    return f"答案：{final}" if final else f"答案：待确认（{type_title}）"


def to_markdown_block(item: dict[str, Any], result: dict[str, Any]) -> str:
    lines = [
        f"### Q{result['index']}. {clean_text(item.get('title', ''))} (ID: {item.get('questionid')})",
        "",
        f"> **{answer_line(item, result.get('final', ''))}**",
    ]
    if result.get("analysis"):
        lines.extend(["", f"> 解析：{clean_text(result['analysis'])}"])
    lines.extend(["", "---", ""])
    return "\n".join(lines)


def load_done_ids(path: Path) -> set[int]:
    done = set()
    if not path.exists():
        return done
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        qid = obj.get("questionid")
        if isinstance(qid, int):
            done.add(qid)
    return done


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


def solve_question(
    index: int,
    item: dict[str, Any],
    *,
    base_url: str,
    api_key: str,
    model: str,
    max_retries: int,
    retry_jitter: float,
) -> dict[str, Any]:
    prompt = build_prompt(item)
    content = ""
    last_err = ""
    started = time.time()
    for attempt in range(1, max_retries + 2):
        try:
            content = call_openai(base_url, api_key, prompt, model, timeout=180)
            if extract_tag(content, "final"):
                break
            last_err = "missing <final>"
        except Exception as exc:
            last_err = str(exc)
        if attempt < max_retries + 1:
            time.sleep(max(0.5, 0.8 + random.uniform(0, retry_jitter)))

    return {
        "index": index,
        "questionid": item.get("questionid"),
        "typeTitle": item.get("typeTitle"),
        "title": clean_text(item.get("title", "")),
        "think": shorten_think(extract_tag(content, "think")),
        "analysis": extract_tag(content, "analysis"),
        "final": extract_tag(content, "final"),
        "raw": content,
        "error": last_err if not extract_tag(content, "final") else "",
        "elapsed_sec": round(time.time() - started, 3),
        "ts": dt.datetime.now().isoformat(timespec="seconds"),
    }


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
    ap.add_argument("--base-url", default=os.environ.get("WEB2API_BASE_URL", openai_cfg.get("base_url", DEFAULT_BASE_URL)))
    ap.add_argument("--api-key", default=os.environ.get("WEB2API_API_KEY", openai_cfg.get("api_key", DEFAULT_API_KEY)))
    ap.add_argument("--model", default=os.environ.get("WEB2API_MODEL", openai_cfg.get("model", DEFAULT_MODEL)))
    ap.add_argument("--rpm", type=float, default=openai_cfg.get("rpm", DEFAULT_RPM))
    ap.add_argument("--jitter", type=float, default=0.35)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out", default=get_path(config, "batch_results_jsonl", "batch_results.jsonl"))
    ap.add_argument("--md-out", default=get_path(config, "batch_results_md", "batch_results.md"))
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--max-retries", type=int, default=2)
    ap.add_argument("--concurrency", type=int, default=openai_cfg.get("concurrency", 6))
    args = ap.parse_args()


    # Create directories if they do not exist
    out_path = Path(args.out)
    md_out_path = Path(args.md_out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    md_out_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        questions = load_questions(Path(args.paper))
    except FileNotFoundError as e:
        print(e)
        return 1

    if args.limit and args.limit > 0:
        questions = questions[: args.limit]

    done_ids = load_done_ids(out_path) if args.resume else set()
    if args.resume:
        questions = [q for q in questions if q.get("questionid") not in done_ids]

    delay = 60.0 / args.rpm if args.rpm > 0 else 0.0
    results = []
    if not args.dry_run and not args.resume:
        out_path.write_text("", encoding="utf-8")
        md_out_path.write_text("# 批量答案结果\n\n", encoding="utf-8")

    if args.dry_run:
        for idx, item in enumerate(questions, start=1):
            print(build_prompt(item))
            print("---")
        return 0

    total = len(questions)
    if total == 0:
        print("没有需要求解的题目 / No questions to solve.")
        return 0

    completed = 0
    write_lock = threading.Lock()
    item_by_id = {q.get("questionid"): q for q in questions}
    pending: dict[concurrent.futures.Future, dict[str, Any]] = {}

    def flush_done(done_futures):
        nonlocal completed
        for fut in done_futures:
            item = pending.pop(fut)
            result = fut.result()
            results.append(result)
            with write_lock:
                with open(out_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(result, ensure_ascii=False) + "\n")
                with open(md_out_path, "a", encoding="utf-8") as f:
                    f.write(to_markdown_block(item_by_id[result["questionid"]], result))
            completed += 1
            if result["final"]:
                print(
                    f"[{completed}/{total}] {result['questionid']} -> "
                    f"{result['final']} ({result['elapsed_sec']}s)"
                )
            else:
                print(
                    f"[{completed}/{total}] {result['questionid']} -> "
                    f"ERROR: {result['error']} ({result['elapsed_sec']}s)"
                )

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as executor:
        for idx, item in enumerate(questions, start=1):
            while len(pending) >= max(1, args.concurrency):
                done, _ = concurrent.futures.wait(
                    pending.keys(),
                    return_when=concurrent.futures.FIRST_COMPLETED,
                )
                flush_done(done)

            fut = executor.submit(
                solve_question,
                idx,
                item,
                base_url=args.base_url,
                api_key=args.api_key,
                model=args.model,
                max_retries=args.max_retries,
                retry_jitter=args.jitter,
            )
            pending[fut] = item

            if idx < total and delay > 0:
                sleep_for = max(0.0, delay + random.uniform(-args.jitter, args.jitter))
                time.sleep(sleep_for)

        while pending:
            done, _ = concurrent.futures.wait(
                pending.keys(),
                return_when=concurrent.futures.FIRST_COMPLETED,
            )
            flush_done(done)

    print(f"saved {len(results)} results to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
