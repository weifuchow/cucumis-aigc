---
name: keyframe-planner
description: Generate keyframe anchors for each storyboard scene. Use before prompt engineering and image generation.
---

# keyframe_planner

## Purpose

为每个 scene 定义关键视觉锚点，作为后续图像与动态视频生成的统一视觉约束。

**keyframe 不是时间戳的机械提取，而是对画面内容的语义描述——告诉图像模型"这一帧应该画什么"。**

## Reads

- `projects/<project>/storyboard/storyboard.json`

## Writes

- `projects/<project>/keyframes/keyframes.json`

## 关键决策：visual_anchor 的内容质量

`visual_anchor` 是 `prompt_engineer` 阶段最重要的输入之一，直接影响图像生成质量。

**不要输出泛化描述（如"展示场景"、"表现情绪"），要输出具体的画面构成。**

### 好的 visual_anchor vs 差的 visual_anchor

| 差 | 好 |
|---|---|
| "克制的环境和静态信息呈现" | "灰色天空下的废弃工厂，前景是生锈的铁门，远景是烟囱" |
| "展现主角情绪" | "主角侧脸特写，眼神坚定，逆光剪影，背景虚化城市轮廓" |
| "高能量动作场景" | "龙爪落地瞬间，碎石飞溅，主角持剑跳起，背景是火焰爆炸" |

### 决策框架：从 storyboard 推导 visual_anchor

1. **主体**：场景里的核心主体是谁/什么（人物、物体、环境）
2. **动作/状态**：主体在做什么，处于什么状态
3. **构图**：特写/中景/全景，主体在画面哪个位置
4. **光线/氛围**：时间、天气、情绪色调（冷暖、明暗）
5. **背景元素**：背景里有什么增强叙事的元素

### camera_intent 选择

直接从 storyboard 的 `motion_intent` 映射，不要另行发明：
- `slow_pan` / `locked` → 保留原值
- `fast_push` / `whip_pan` / `handheld` → 保留原值，同时在 `visual_anchor` 里描述运动感

## Runtime Expectations

- 调用 `python scripts/run_keyframe_planner.py --project <name>` 生成初始 keyframes
- **脚本输出的 visual_anchor 是从 storyboard 字段直接提取的占位文本，Claude 应基于 storyboard 内容重写每个 visual_anchor 为具体的画面描述**
- 每个 scene 生成一个 keyframe，timestamp 取场景时间中点
- 输出 JSON 必须可解析并可被 `prompt_engineer` 直接消费
