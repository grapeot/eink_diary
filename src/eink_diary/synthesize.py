"""判断层：把一个时间窗的素材文件，提炼成一段"瞬间"画面描述（image prompt）。

设计（见 RFC D4/D5/D6）：
- 输入是 collector 产出的素材纯文本（一个时间窗的真实近况）。
- 任务不是概括，而是**挑一个最有张力的瞬间**，写成有鸭哥、有场景、有情绪的画面描述。
- 用 OpenAI SDK，base_url / model / api_key 全部从配置读 → provider 无关，
  同一套代码对接 GPT-5.5 / 远程 DeepSeek / 本地 DS-V4（openai-compatible）。
- 输出可单独 inspect / 重放（连同图归档）。
"""

from __future__ import annotations

import os
from dataclasses import dataclass


# 系统提示：把"挑瞬间 + 鸭哥主角 + 风格"的契约固化在这里。
SYSTEM_PROMPT = """\
你在为一块彩色电子纸"视觉日记"屏生成一幅画的英文 image prompt。

输入是某个两小时时间窗里，用户（鸭哥）真实经历的素材（微信里他说的话、和 AI 的讨论、邮件）。

你的任务不是总结这两小时干了什么，而是：
1. 从素材里挑【一个】最有张力、最具体、最有情绪或最有意思的瞬间，丢掉其余。
   （一句让他皱眉/会心的话、一个想通的时刻、一封信、一次受挫或释然、和孩子的片段……）
   注意：微信沉默不代表他在休息，可能正是深度工作——别把"没信号"当成"低能量"。
2. 把这个瞬间写成一个【单一场景】的画面描述，主角是"鸭哥"——一只拟人的鸭子。
3. 风格：柔和叙事插画 / 彩铅 storybook 风，温暖、亲密。
4. 约束写进 prompt：one single scene only (not a summary); vertical 3:4;
   6-color e-ink palette (black, warm red, golden yellow, blue, green on off-white);
   no text labels.

只输出最终的英文 image prompt 本身，不要解释、不要前后缀、不要 markdown。\
"""


@dataclass
class SynthConfig:
    base_url: str | None
    api_key: str
    model: str

    @classmethod
    def from_env(cls) -> "SynthConfig":
        return cls(
            base_url=os.environ.get("DIARY_LLM_BASE_URL") or None,
            api_key=os.environ.get("DIARY_LLM_API_KEY", "") or "not-needed",
            model=os.environ.get("DIARY_LLM_MODEL", "gpt-5.5"),
        )


def build_messages(context_text: str) -> list[dict]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": context_text},
    ]


def synthesize(context_text: str, config: SynthConfig | None = None, client=None) -> str:
    """素材文本 → 一段画面描述（image prompt）。

    client 可注入（测试用 mock）；不注入则按 config 用 openai SDK 建一个。
    """
    config = config or SynthConfig.from_env()
    if client is None:
        from openai import OpenAI

        client = OpenAI(base_url=config.base_url, api_key=config.api_key)

    resp = client.chat.completions.create(
        model=config.model,
        messages=build_messages(context_text),
    )
    return resp.choices[0].message.content.strip()
