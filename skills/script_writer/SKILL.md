---
name: script-writer
description: Generate emotion tagged script content from structured input artifacts. Use before audio foundation stage.
---

# script_writer

## Purpose

基于结构化输入配置生成脚本，并完成情绪标注，形成后续音频基建阶段的核心叙事基础。

**这是整条链路中最需要创意推理的阶段。脚本质量直接决定配音、BGM 选择、分镜节奏的上限。**

## Reads

- `projects/<project>/input/input.json`
- `projects/<project>/brief/selected-concept.json`（必读：用户确认的创意方向）
- `projects/<project>/brief/creative-brief.md`（可选，获取更完整的创意上下文）

## Writes

- `projects/<project>/script/script.json`

## Required Output

`script.json` 至少应包含：

- `title`
- `summary`
- `audio_track`：实际旁白台词，每条是可直接朗读的完整句子
- `visual_track`：对应每条台词的画面描述，具体到主体、构图、光线
- `beats`：段落级节奏单元，带明确的 `purpose`
- `emotion_markers`：情绪标注点
- `turning_points`：叙事转折点

## 内容质量标准

### audio_track：写真实台词，不写占位描述

**差**（占位描述，无法朗读）：
```
"我们先从 X 的核心矛盾切入。"
"前半段情绪保持平稳。"
```

**好**（真实旁白，直接可朗读）：
```
"2023 年，中国有 470 万家餐饮门店倒闭。"
"但有一类店，存活率超过了 80%。"
"它们的秘密，不在菜单，在选址。"
"今天，我们来拆解这背后的逻辑。"
```

### visual_track：描述真实画面，不写抽象情绪

**差**：`"呈现克制的信息"`

**好**：`"俯视角，城市餐饮街道，店铺招牌密集，部分贴着'转让'告示"`

### beats：有叙事逻辑的段落划分

每个 beat 的 `purpose` 应反映叙事功能：
- `problem_setup`：提出问题/矛盾
- `evidence_build`：数据/案例支撑
- `insight_reveal`：核心洞察揭示
- `emotional_peak`：情绪爆发点
- `call_to_action`：行动号召

## 与 selected-concept.json 的对接

`selected-concept.json` 中的字段直接约束脚本内容：

| 字段 | 对脚本的影响 |
|---|---|
| `opening_line` | **第一条 audio_track 必须以此开头**，可以轻微调整措辞但不能改变方向 |
| `emotional_arc` | 整体情绪走向，决定台词语气如何变化 |
| `angle` | 叙事切入点，决定论证逻辑和举例方向 |
| `visual_direction` | 影响 visual_track 的构图和色调描述 |
| `music_direction` | 校验 input.json 中的 `music_emotion` 是否一致 |

## 决策框架：如何从 input.json 推导脚本

1. **台词数量** = `duration_seconds / 7`（每条台词约 7 秒，可根据节奏调整）
2. **情绪弧线** 由 `music_emotion` 驱动：前慢后快 → 台词密度前稀后密，语气前克制后坚定
3. **转折点位置** 由 `pacing_preference` 决定：均匀 → 中点转折；前慢后快 → 2/3 处转折
4. **visual_track** 的镜头密度应与 `visual_preferences` 的节奏描述一致
5. **行业/场景词汇** 从 `topic` 提取，台词应使用领域真实表达，避免泛化描述

## Runtime Expectations

- 调用 `python scripts/run_script_writer.py --project <name>` 生成结构骨架
- **脚本输出是模板占位内容，Claude 必须基于 `topic`、`content_structure`、`music_emotion` 重写真实台词和画面描述**
- 重写后覆盖写入 `script/script.json`
- 台词必须是可直接朗读的完整句子
- `visual_track` 条数必须与 `audio_track` 一致

## Failure Behavior

- 如果 `topic` 为空或过于模糊，停止并要求补充
- 不得输出半结构化或格式损坏的脚本文件
