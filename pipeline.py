#!/usr/bin/env python3
import argparse
import os
import subprocess
import sys

# Define steps
STEPS = {
    1: {"name": "downloader", "script": "src/downloader.py", "desc": "下载优学院试卷 (Download raw papers)"},
    2: {"name": "analyzer", "script": "src/analyzer.py", "desc": "提取并去重题目 (Extract & deduplicate questions)"},
    3: {"name": "solver", "script": "src/solver.py", "desc": "使用 LLM 求解题目 (Batch solve questions with LLM)"},
    4: {"name": "tag_generator", "script": "src/tag_generator.py", "desc": "抽取知识点标签 (Extract knowledge tags with LLM)"},
    5: {"name": "tag_normalizer", "script": "src/tag_normalizer.py", "desc": "清洗与对齐标签 (Normalize and align extracted tags)"},
    6: {"name": "viewer_builder", "script": "src/viewer_builder.py", "desc": "构建网页交互版题库 (Build HTML interactive viewer)"},
}


def run_subprocess(script_path, config_path, extra_args):
    # Pass --config to the child scripts
    cmd = [sys.executable, script_path, "--config", config_path] + extra_args
    print(f"\n>>> 正在执行: {' '.join(cmd)}")
    try:
        res = subprocess.run(cmd, check=True)
        return res.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"[-] 执行失败: {script_path} 返回了错误码 {e.returncode}")
        return False
    except Exception as e:
        print(f"[-] 执行发生异常: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Ulearning 题库获取与处理一站式流水线 / Ulearning Qbank Pipeline")
    parser.add_argument(
        "--step",
        help="要运行的步骤编号 (如 1, 2) 或 'all' 运行全部, 'solve-only' 运行 3-6 步骤",
        default=None,
    )
    parser.add_argument(
        "--config",
        help="配置文件路径 (Path to config file)",
        default="config.json",
    )
    parser.add_argument(
        "--extra",
        help="传递给子脚本的额外参数，例如 '--extra=\"--limit 10\"'",
        default="",
    )
    args, unknown = parser.parse_known_args()

    # If --step is not specified, show an interactive menu
    step_input = args.step
    config_path = args.config
    extra_args = []
    if args.extra:
        import shlex
        extra_args = shlex.split(args.extra)
    if unknown:
        # Filter out if --config was already parsed from unknown
        filtered_unknown = []
        skip_next = False
        for i, val in enumerate(unknown):
            if skip_next:
                skip_next = False
                continue
            if val == "--config":
                skip_next = True
                continue
            filtered_unknown.append(val)
        extra_args.extend(filtered_unknown)

    if not step_input:
        print("=========================================================")
        print("   优学院题库流水线控制台 / Ulearning Qbank Pipeline Menu ")
        print("=========================================================")
        print(f"  当前配置文件: {config_path}")
        print("---------------------------------------------------------")
        for num, info in STEPS.items():
            print(f"  [{num}] {info['name']:<15} - {info['desc']}")
        print("  [all] 运行所有步骤 (1 到 6)")
        print("  [solve-only] 仅运行构建步骤 (3 到 6)")
        print("  [q] 退出")
        print("=========================================================")
        try:
            step_input = input("请输入要执行的步骤: ").strip()
        except KeyboardInterrupt:
            print("\n已退出。")
            return 0

    if step_input.lower() == "q":
        return 0

    if step_input.lower() == "all":
        steps_to_run = [1, 2, 3, 4, 5, 6]
    elif step_input.lower() == "solve-only":
        steps_to_run = [3, 4, 5, 6]
    else:
        try:
            steps_to_run = [int(step_input)]
        except ValueError:
            print(f"错误: 无效的输入 '{step_input}'")
            return 1

    for s in steps_to_run:
        if s not in STEPS:
            print(f"错误: 不存在步骤 {s}")
            return 1

    print(f"\n将依次执行步骤: {', '.join(str(s) for s in steps_to_run)}")

    for s in steps_to_run:
        info = STEPS[s]
        print(f"\n=========================================")
        print(f"  步骤 {s}: {info['desc']}")
        print(f"=========================================")
        success = run_subprocess(info["script"], config_path, extra_args)
        if not success:
            print(f"\n[-] 流水线在步骤 {s} 中断。")
            return 1

    print("\n[+] 流水线全部步骤执行完毕！")
    return 0




if __name__ == "__main__":
    sys.exit(main())
