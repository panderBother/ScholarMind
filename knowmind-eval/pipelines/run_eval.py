"""
最小评估入口（占位）：

1. 读取 `datasets/` 下 JSONL：question, ground_truth, contexts...
2. 调用 KnowMind API 或本地 Agent 批量生成答案
3. 使用 RAGAS 或自研指标打分，写入 `reports/`
"""

from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    datasets = root / "datasets"
    reports = root / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "latest.json").write_text('{"status":"stub","note":"install ragas extra to run"}', encoding="utf-8")
    _ = datasets
    print("eval stub wrote reports/latest.json")


if __name__ == "__main__":
    main()
