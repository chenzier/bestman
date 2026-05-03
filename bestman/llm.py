"""Re-export stub — see bestman.core.llm for the actual implementation."""
from bestman.core.llm import (  # noqa: F401
    COACH_SYSTEM_PROMPT,
    PLAN_GENERATOR_SYSTEM_PROMPT,
    LLMClient,
    chat_with_coach,
    generate_plan,
    generate_voyage_log,
    review_summary,
    weigh_comment,
)
