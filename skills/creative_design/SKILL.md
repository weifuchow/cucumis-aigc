---
name: creative-design
description: 创意需求定稿阶段。需求引导→3个方案选择→成本档位确认→输出 input.json，作为主链第一步。
---

# creative_design

## Purpose

在一个阶段内完成：需求澄清 → 创意方案生成 → 用户选择 → 成本档位确认 → 写入 `input.json`。

**未经用户确认方案和成本档位，不得推进到后续生产阶段。**

## Reads

- `projects/<project>/request.md`

## Writes

- `projects/<project>/brief/intake.json`（解析后的需求字段）
- `projects/<project>/brief/proposals.json`（3 个方案）
- `projects/<project>/brief/selected-concept.json`（用户选定的方案 + 成本档位）
- `projects/<project>/input/input.json`（流水线统一输入，含模型配置）

---

## 执行流程（Claude 驱动）

### Step 1：需求澄清

读取 `request.md`，如果信息不完整，按优先级追问：

1. **必须明确**：主题、时长、平台/画幅
2. **建议明确**：情绪走向、旁白要求、视觉风格偏好
3. 信息足够后直接进入方案生成，不要过度追问

### Step 2：生成 3 个创意方案

基于需求生成 **3 个真实差异化的方向**，用清晰格式呈现：

```
方案 A：「标题」
开场白："第一句可朗读的台词"
情绪弧线：疑问 → 冲击 → 落地
视觉风格：关键词1、关键词2

方案 B：...

方案 C：...
```

3 个方案的差异维度（选其中几个）：
- 叙事角度：问题驱动 vs 故事代入 vs 直接揭示
- 情绪弧线：平稳递进 vs 强对比反转 vs 压抑爆发
- 开场钩子：数据冲击 vs 场景代入 vs 反常识问题

### Step 3：用户选择方案

用户可以：选 A/B/C、要求修改某个维度、混合多个方案元素。确认后继续。

### Step 4：成本档位选择

**在方案确认后，询问用户选择成本档位：**

---
**省钱模式（全图片）**
所有场景用图片合成，不调视频模型。图片：Grok-Imagine-Image。成本最低。
适合：信息类、叙述类、预算有限的项目。

**标准模式（最多2次视频）**
最多2个场景调视频模型，其余用图片合成。视频：Pixverse-v5.6。
适合：大多数项目，在成本和效果之间平衡。

**不限制**
所有需要动态效果的场景均调视频模型。
适合：高质量输出、不在意成本的项目。
---

### Step 5：写入产物

用户确认后：
1. 写 `brief/selected-concept.json`（含 `cost_tier` 字段）
2. 调用脚本生成 `input/input.json`：
   `python scripts/run_creative_design.py --project <name>`
   脚本检测到 `selected-concept.json` 已存在，直接读取并生成 `input.json`

---

## 成本档位对 input.json 的影响

| 档位 | `cost_tier` | `max_video_calls` | `image_model` | `video_model` |
|---|---|---|---|---|
| 省钱模式 | `economy` | `0` | `grok-imagine-image` | `pixverse-v5.6` |
| 标准模式 | `standard` | `2` | `grok-imagine-image` | `pixverse-v5.6` |
| 不限制 | `unlimited` | `999` | `grok-imagine-image` | `pixverse-v5.6` |

`max_video_calls` 会被 `constrained_video_generator` 读取，控制实际视频模型调用次数。

---

## 脚本模式（自动化 fallback）

```bash
python scripts/run_creative_design.py --project <name> [--tier standard] [--concept A]
```

自动完成所有步骤，不与用户交互。`--tier` 指定成本档位，`--concept` 指定自动选择的方案。

---

## 子脚本说明

`run_creative_brief_intake.py`、`run_creative_proposal.py`、`run_input_parser.py` 仍保留，
仅用于**单步调试或局部重跑**，正常流程不需要单独调用。
