"""为 README 截图打码：遮盖姓名与个人敏感信息。"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ASSETS = Path(__file__).resolve().parents[1] / "assets"
SHOTS = Path(__file__).resolve().parents[1] / "docs" / "screenshots"

# (x1, y1, x2, y2) — 1024 宽 UI 截图
REDACTIONS: dict[str, list[tuple[int, int, int, int]]] = {
    "01-chat-research.png": [
        (204, 176, 396, 212),   # 会话标题
        (248, 452, 360, 476),   # 底部当前知识库名
    ],
    "02-knowledge-bases.png": [
        (262, 88, 390, 112),    # 卡片标题行 1
        (542, 88, 630, 112),
        (822, 88, 880, 112),
        (262, 238, 320, 262),   # 卡片标题行 2
        (542, 238, 610, 262),
    ],
    "03-documents-pdf.png": [
        (296, 88, 410, 112),    # 知识库下拉选中项
        (430, 168, 660, 192),   # 上传区提示语中的库名
    ],
    "04-documents-entries.png": [
        (34, 124, 440, 150),    # 条目 1 标题
        (34, 152, 990, 248),    # 条目 1 正文（姓名/电话/邮箱）
        (34, 252, 420, 278),    # 条目 2 标题
        (34, 280, 990, 332),    # 条目 2 正文
    ],
    "05-reports.png": [
        (34, 88, 300, 114),     # 报告标题
        (34, 118, 990, 232),    # 摘要全文
    ],
}


def redact_box(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> None:
    x1, y1, x2, y2 = box
    draw.rectangle(box, fill=(200, 200, 200))
    mid_y = (y1 + y2) // 2
    draw.line([(x1, mid_y), (x2, mid_y)], fill=(120, 120, 120), width=2)


def process(path: Path) -> None:
    regions = REDACTIONS.get(path.name)
    if not regions:
        return
    img = Image.open(path).convert("RGB")
    draw = ImageDraw.Draw(img)
    for box in regions:
        redact_box(draw, box)
    img.save(path, format="PNG", optimize=True)
    print(f"redacted: {path.name} ({len(regions)} regions)")


def main() -> None:
    for filename in REDACTIONS:
        process(ASSETS / filename)
    if SHOTS.is_dir():
        for filename in REDACTIONS:
            src = ASSETS / filename
            if src.exists():
                Image.open(src).save(SHOTS / filename, format="PNG")


if __name__ == "__main__":
    main()
