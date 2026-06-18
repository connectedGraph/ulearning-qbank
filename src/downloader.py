import urllib.request
import urllib.parse
import json
import time
import ssl
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.utils import load_config, get_path

ssl_context = ssl._create_unverified_context()

def main():
    print("=== Ulearning 题库下载工具 / Question Bank Downloader ===\n")

    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.json", help="Path to config file")
    args = parser.parse_known_args()[0]

    try:
        config = load_config(args.config)
    except (FileNotFoundError, ValueError) as e:

        print(str(e))
        return

    auth_token = config["authorization"]
    exam_id = config["examId"]
    exam_user_id = config["examUserId"]
    trace_id = config["traceId"]
    start_id = config["paper_range"]["start_id"]
    end_id = config["paper_range"]["end_id"]
    delay = config["rate_limiting"]["delay_seconds"]

    headers = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh",
        "Authorization": auth_token,
        "Connection": "keep-alive",
        "Origin": "https://utest.ulearning.cn",
        "Referer": "https://utest.ulearning.cn/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    base_url = "https://utestapi.ulearning.cn/exams/user/study/getPaperForStudent"
    output_dir = get_path(config, "papers_dir", "papers_json")
    os.makedirs(output_dir, exist_ok=True)


    total = end_id - start_id + 1
    print(f"开始下载 / Starting download: Paper IDs {start_id} to {end_id} ({total} papers)\n")

    success_count = 0
    fail_count = 0

    for paper_id in range(start_id, end_id + 1):
        query_params = {
            "paperId": str(paper_id),
            "examId": exam_id,
            "examUserId": exam_user_id,
            "traceId": trace_id
        }

        url = f"{base_url}?{urllib.parse.urlencode(query_params)}"
        req = urllib.request.Request(url, headers=headers)

        try:
            with urllib.request.urlopen(req, context=ssl_context, timeout=15) as response:
                body_str = response.read().decode('utf-8')
                body_json = json.loads(body_str)

                output_path = os.path.join(output_dir, f"{paper_id}.json")
                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(body_json, f, indent=2, ensure_ascii=False)

                if body_json.get("code") == 1 and body_json.get("result"):
                    print(f"[+] Paper {paper_id}: 下载成功 / Downloaded successfully")
                    success_count += 1
                else:
                    print(f"[-] Paper {paper_id}: 响应异常 / Abnormal response (code={body_json.get('code')})")
                    fail_count += 1
        except Exception as e:
            print(f"[-] Paper {paper_id}: 错误 / Error - {e}")
            fail_count += 1


        time.sleep(delay)

    print(f"\n完成 / Completed: 成功 {success_count}, 失败 {fail_count}")

if __name__ == "__main__":
    main()
