# 中国近现代史纲要 示例数据 / Modern History Example Dataset

本目录包含一份已经爬取并使用 LLM 完成求解、标注、整合的**完整题库示例数据**（科目：中国近现代史纲要）。

This directory contains a complete, already-built question bank dataset for "Chinese Modern History Review".

## 📂 文件清单 / File List

- `question_bank.json`: 经过去重和 HTML 实体解码后的原始题库数据（含选项、题型，未解出答案前的数据）。
- `batch_results.jsonl`: LLM 批量求解后的数据（包含 `<think>`、`<analysis>` 和 `<final>` 提取的答案）。
- `title_tags.jsonl`: LLM 提取并经过清洗、对齐后的知识点标签。
- `subjective.json`: 本科目整理的主观题与复习讲义大纲（对应原 `qbank_2.json`）。
- `final_answers.html`: 最终编译生成的单文件交互式题库网页阅读器。
- `config.json`: 本地测试该示例数据专用的路径配置文件。

## 🚀 快速测试 / How to Test

您可以利用本示例数据快速验证流水线的网页编译步骤（步骤 6）：

1. 直接在项目根目录下运行流水线编译步骤，并指定本目录的配置文件：
   ```bash
   python pipeline.py --config examples/modern-history/config.json --step 6
   ```
2. 执行成功后，会重新在 `examples/modern-history/final_answers.html` 路径下生成网页。您可以双击用浏览器打开查看效果。

