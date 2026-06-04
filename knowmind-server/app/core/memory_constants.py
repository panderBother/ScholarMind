"""对话记忆默认参数，与 docs/KnowMind_设计技术方案.md §4.6 对齐；可通过 Settings 覆盖。"""

# 最近进入模型上下文的「消息条数」上限（user/assistant 各算一条）
MEMORY_RECENT_MESSAGE_COUNT = 8
# 最近原文合计 token 估算上限
MEMORY_RECENT_MAX_TOKENS = 4000
# 摘要触发：轮数或累计 token（自上次摘要清零后）
MEMORY_SUMMARY_TRIGGER_TURNS = 10
MEMORY_SUMMARY_TRIGGER_TOKENS = 8000
# 摘要冷却：自上次摘要后至少再积累
MEMORY_SUMMARY_COOLDOWN_TURNS = 6
MEMORY_SUMMARY_COOLDOWN_TOKENS = 4000
# 检索注入 prompt 的 token 预算
MEMORY_RETRIEVAL_MAX_TOKENS = 2000
MEMORY_RETRIEVAL_TOP_K = 10
# Redis 中保留的最近消息条数（略大于 K）
MEMORY_REDIS_RECENT_CAP = 32
# Redis TTL（秒），7 天
MEMORY_REDIS_TTL_SECONDS = 7 * 24 * 3600


def approx_token_count(text: str) -> int:
    """粗算 token（中英混合）：偏保守，用于预算控制。"""
    if not text:
        return 0
    n = len(text)
    return max(1, n // 2)
