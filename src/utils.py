import json
import os
import html

def load_config(config_path="config.json", validate_crawler=True):
    if not os.path.exists(config_path):
        raise FileNotFoundError(
            f"错误 / ERROR: {config_path} not found\n"
            f"请将 config.example.json 复制为 config.json 并填写配置\n"
            f"Please copy config.example.json to config.json and fill in your configuration"
        )

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    if validate_crawler:
        validate_config(config)
    return config

def validate_config(config):
    errors = []

    auth = config.get("authorization", "")
    if not auth or auth == "":
        errors.append("Authorization token not configured")

    exam_id = config.get("examId", "")
    if not exam_id or exam_id == "":
        errors.append("examId not configured")

    user_id = config.get("examUserId", "")
    if not user_id or user_id == "":
        errors.append("examUserId not configured")

    start_id = config.get("paper_range", {}).get("start_id", 0)
    end_id = config.get("paper_range", {}).get("end_id", 0)
    if start_id == 0 or end_id == 0:
        errors.append("Paper ID range not configured (paper_range.start_id / end_id)")
    elif start_id > end_id:
        errors.append(f"Invalid paper range: start_id ({start_id}) > end_id ({end_id})")

    if errors:
        error_msg = "配置错误 / Configuration Errors:\n" + "\n".join(f"  - {e}" for e in errors)
        error_msg += "\n\n请运行浏览器JS代码生成配置 / Please run browser JS code to generate config"
        raise ValueError(error_msg)

def get_path(config, path_key, default_value):
    return config.get("paths", {}).get(path_key, default_value)

def decode_html_entities(text):
    if not text:
        return text
    return html.unescape(text)

