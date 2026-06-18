# 快速开始指南 / Quick Start Guide

通过本工具，您可以一站式完成从**优学院爬取题目**、**去重解析**、**LLM 自动作答与解析**、**知识点标签提取**，到最终生成**现代交互式 HTML 题库阅读器**的完整流水线。

---

## 🚀 一键运行流水线 / Run Pipeline in One Command

### 第一步：生成基本配置
1. 打开优学院练习页面，按 `F12` 打开开发者工具，切换到 **Console (控制台)**。
2. 复制 [generate_config.js](generate_config.js) 的全部内容粘贴并运行。
3. 在页面中点击“开始做题”或“下一题”触发网络请求，随后在控制台输入 `showConfig()`。
4. 复制生成的 JSON 并保存为项目根目录的 `config.json` 文件（可参考 `config.example.json`）。

### 第二步：运行流水线
您可以使用 `pipeline.py` 主控脚本一键或按步骤运行完整流水线：

```bash
# 运行全部步骤 (1 到 6)
python pipeline.py --step all

# 或者启动交互式菜单进行选择
python pipeline.py
```

---

## 📂 流水线详细步骤 / Detailed Pipeline Steps

如果您想手动控制或调试，可以分步运行以下脚本：

### 1️⃣ 下载试卷 / Download
```bash
python src/downloader.py
```
- **输入**：`config.json` (Authorization, paper_range 等)
- **输出**：`papers_json/` 目录下的多套试卷 JSON 数据

### 2️⃣ 解析并去重 / Parse & Deduplicate
```bash
python src/analyzer.py
```
- **输入**：`papers_json/`
- **输出**：`question_bank.json` (去重后的所有题目 JSON) 与 `question_bank.md` (原始 Markdown 格式)

### 3️⃣ LLM 自动作答与分析 / Batch Solve
```bash
python src/solver.py
```
- **输入**：`question_bank.json`，`config.json` 中的 `openai` LLM 配置
- **输出**：`batch_results.jsonl` (包含每道题的推理、分析与答案) 以及 `batch_results.md`

### 4️⃣ LLM 提取知识点标签 / Tag Generation
```bash
python src/tag_generator.py
```
- **输入**：`question_bank.json` 与 `batch_results.jsonl`
- **输出**：`title_tags.jsonl` (抽取出的原始知识点标签)

### 5️⃣ 标签清洗与对齐 / Tag Normalization
```bash
python src/tag_normalizer.py
```
- **输入**：`title_tags.jsonl`
- **输出**：更新 `title_tags.jsonl` (进行别名合并、过滤泛词，对齐标签)

### 6️⃣ 网页构建器 / Build Interactive HTML
```bash
python src/viewer_builder.py
```
- **输入**：`question_bank.json`、`batch_results.jsonl`、`title_tags.jsonl` 及主观题复习数据 `subjective.json` (可选)
- **输出**：`final_answers.html` (精美、现代的单网页题库阅读器)

---

## 📋 配置示例 / Configuration Example (`config.json`)

```json
{
  "authorization": "B4A14C9AFE31529ACF246285BB33CBB7",
  "examId": "148939",
  "examUserId": "39283460",
  "traceId": "39283460",
  "paper_range": {
    "start_id": 3415820,
    "end_id": 3415919
  },
  "rate_limiting": {
    "delay_seconds": 1.0
  },
  "openai": {
    "base_url": "http://127.0.0.1:8081/v1",
    "api_key": "sk-your-key-here",
    "model": "gemini-flash-lite",
    "rpm": 30,
    "concurrency": 6
  }
}
```

---

## 💡 示例数据 / Demo Dataset

如果您不想下载任何题目，只想快速预览或重新构建示例网页，可以直接通过 `--config` 指定示例配置文件运行，这**不会影响或覆盖**您根目录的 `config.json`：

1. 运行网页构建步骤：
   ```bash
   python pipeline.py --config examples/modern-history/config.json --step 6
   ```
2. 打开 `examples/modern-history/final_answers.html` 即可体验包含答题记录、知识点过滤、主观题讲义以及深色模式的现代题库查看器！

