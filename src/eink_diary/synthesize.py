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

这块屏的意义（决定你怎么写）：它不是又一块塞满信息、催人生产力的屏。恰恰相反，它是
在鸭哥高强度、多线程的工作里，故意引入的一点"反生产力"——让他抬头会心一笑，觉得
自己做的这些事被人看见、被 appreciate。同时它是给未来的资产：一个月后、一年后、甚至
"X 年前的今天"回看时，这幅画要有足够多的具体细节，能把他瞬间拉回此刻的感觉。
所以：**画面必须 specific、富含细节，而不是泛泛一只鸭子在工作。** 越具体越好。

你的任务不是总结这两小时干了什么，而是：
1. 从素材里挑【一个】最有张力、最具体、最有情绪或最有意思的瞬间，丢掉其余。
   （一句让他皱眉/会心的话、一个想通的时刻、一封信、一次受挫或释然、和孩子的片段……）
   注意：微信沉默不代表他在休息，可能正是深度工作——别把"没信号"当成"低能量"。
2. 把这个瞬间写成一个【单一场景】的画面描述，主角是"鸭哥"——一只拟人的鸭子。
3. 富细节（关键）：写进能唤起记忆的具体物件、环境、姿态、表情、光线——具体到这个瞬间，
   而不是任何一天都成立的泛泛场景。让一年后的他看到这些细节能想起"哦，那天是在干这个"。
   基调温暖、亲切、带一点幽默，能让人会心一笑。
4. 画风：**小羊肖恩 / Aardman 那种定格黏土动画风（Aardman Animations stop-motion
   claymation, in the style of Shaun the Sheep / Wallace & Gromit）**——手捏黏土质感、
   可见指纹与手作痕迹、圆润敦实的造型、大而有神的圆眼睛、英式温暖幽默。立体黏土实景，
   不是彩铅、不是平面插画。把 "Aardman" / "Shaun the Sheep style claymation" 写进 prompt。
5. 约束写进 prompt：one single scene only (not a summary); vertical 3:4;
   6-color e-ink palette (black, warm red, golden yellow, blue, green on off-white);
   no text labels.
6. 物件朝向（重要，常犯的错——用【相对关系】描述，不要用绝对方向）：
   鸭哥在工作时，他桌上的东西的正面是【朝着鸭哥的脸】的，跟着鸭哥的朝向走，而不是
   永远摆给观众看。关键是写成相对关系："the screen/notebook/keyboard faces the duck"
   （朝着鸭哥的脸），让模型按鸭哥在画面里的朝向自己推导该露正面还是背面。
   - 鸭哥正面朝我们 → 屏幕等物自然背面/侧面朝我们（因为它们朝鸭哥）。
   - 鸭哥背对我们 → 屏幕等物的正面朝我们（因为它们朝鸭哥的脸，而鸭哥朝里）。
     ★这种情况别让屏幕也背对我们，那样两个都背对就荒谬了。
   唯一例外：瞬间本身是"鸭哥主动向观众/听众展示某物"（指着屏给人看），那个被展示的物
   才特意朝向观众。默认一律"朝鸭哥的脸"。

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
