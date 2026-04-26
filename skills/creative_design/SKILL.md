---
name: creative-design
description: 创意需求定稿阶段。需求引导→3个方案选择→成本档位确认→输出 input.json，作为主链第一步。
---

# creative_design

## Purpose

在一个阶段内完成：需求澄清 → 强制制作要素锁定 → 创意方案生成 → 用户选择 → **角色与场景设计确认** → 成本/素材档位确认 → 写入 `input.json`。

**未经用户确认方案、视觉/素材设计和成本档位，不得推进到后续生产阶段。**

本阶段必须主动问清或默认锁定“素材来源、是否允许 AI 生成、素材下载、BGM、环境声、字幕、音频供应商”等制作约束。不要等用户在后续阶段补充。

## Reads

- `projects/<project>/request.md`

## Writes

- `projects/<project>/brief/intake.json`（解析后的需求字段）
- `projects/<project>/input/intake-lock.json`（强制制作要素锁定，可选但推荐）
- `projects/<project>/brief/proposals.json`（3 个方案）
- `projects/<project>/brief/selected-concept.json`（用户选定的方案 + 成本档位）
- `projects/<project>/brief/character-prompts.json`（角色提示词设计，含多视角）
- `projects/<project>/brief/scene-prompts.json`（关键场景提示词设计草稿）
- `projects/<project>/input/input.json`（流水线统一输入，含模型配置）

---

## 执行流程（Claude 驱动）

### Step 0：场景时长规则（固定，不可更改）

**所有场景时长统一固定为 5 秒。** 这是整条流水线的刚性约束：

- 场景数量 = `ceil(total_duration / 5)`
- 每个场景恰好占用 5 秒时间槽
- 分镜规划、音频对齐、关键帧生成均基于此节拍
- **任何阶段不得修改场景时长**，如叙事需要更长停留，用多个连续 5s 场景表达

**节奏划分规则（在 Step 2 方案生成时输出场景节拍表）：**

根据总时长计算场景数，按叙事弧线分配节奏权重（以 60s/12 场景为参考）：

| 叙事段落 | 建议比重 | 作用 |
|---|---|---|
| 开场/世界建立 | 15% | 钩子、氛围铺垫 |
| 冲突/反派引入 | 25% | 张力建立 |
| 英雄/对峙登场 | 25% | 角色亮相、蓄力 |
| 情绪高潮/决战 | 25% | 核心爆发点 |
| 收尾/余韵 | 10% | 情绪落地 |

**方案确认后必须输出一张场景节拍表**，列出每个场景（5s 一格）的叙事目的和情绪标签，供用户确认节奏是否合理。

### Step 1：需求澄清

读取 `request.md`，如果信息不完整，按优先级追问：

1. **必须明确**：主题、时长、平台/画幅
2. **必须明确或默认锁定**：素材来源、AI 图片/视频是否允许、旁白供应商、BGM、环境声、字幕
3. **建议明确**：情绪走向、旁白要求、视觉风格偏好
4. 信息足够后直接进入方案生成，不要过度追问

#### 强制制作要素采集表

进入方案生成前，必须形成下列字段。用户已表达时直接采用；未表达但有合理默认时，告知默认值并继续；高风险或不可推断时追问。

| 字段 | 写入位置 | 默认/规则 |
|---|---|---|
| `duration_seconds` | `brief/intake.json`, `input/input.json` | 用户未给时追问 |
| `aspect_ratio` | 同上 | 短视频可默认 `9:16`，但需告知 |
| `source_mode` | 同上 | `generated` / `stock_materials` / `local_materials` / `hybrid_materials` |
| `material_cost_tier` | 同上 | 用户要求外部素材/不生成时默认 `0` |
| `ai_image_generation` | 同上 | 素材档位 0 默认 `false` |
| `ai_video_generation` | 同上 | 素材档位 0 默认 `false` |
| `audio_provider` | 同上 | 用户有 ElevenLabs key 时用 `elevenlabs` direct |
| `poe_enabled` | 同上 | 用户说禁用 Poe 时必须 `false` |
| `bgm.required` | 同上 | 情绪/风光/旁白短片默认 `true` |
| `ambience.required` | 同上 | 素材片默认 `true` |
| `subtitles.required` | 同上 | 竖屏旁白片默认 `true` |
| `subtitle_style` | 同上 | 大字、最多两行、自动换行、底部安全区 |

用户提到“外部素材 / stock / 下载素材 / 本地素材 / 不用 AI 生成”时，必须明确告诉用户后续会包含素材下载阶段：

```
我会按素材剪辑流程推进：旁白文案 → 分镜 → 按场景生成素材搜索清单 → 下载视频/BGM/环境声 → 粗剪 → 字幕 → 复审补素材。
```

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

### Step 4：角色与场景设计（必须确认）

**方案确认后，必须生成角色和场景设计并等待用户确认，才能继续。**

如果 `source_mode` 是 `stock_materials`、`local_materials` 或 `hybrid_materials`，本步骤输出的是 **素材搜索/选片 brief**，不是 AI 生成提示词；不得暗示会生成图片或视频。

#### 4a. 角色提示词设计

为每个主要角色生成多视角提示词，格式如下：

```
角色：[角色名]
视角一（全身正面）：[完整英文/中文提示词，含外貌、服装、能力特效、背景、渲染风格]
视角二（面部特写）：[完整提示词，重点刻画面部表情、眼神、细节]
视角三（动态/能力展示）：[完整提示词，展现角色标志性动作或能力]
反向提示词：[需要排除的内容]
```

**提示词要求：**
- 描述需具体到：发型发色、服装款式颜色、体型特征、标志性道具/能力
- 包含渲染风格：如"3D写实渲染、史诗级光影、超高清"
- 包含构图/视角说明
- 不得使用泛化描述（如"帅气男性"），必须有可供生成的视觉细节

#### 4a-stock. 角色/主体素材 brief（素材主导时使用）

素材主导项目改用以下格式：

```
主体：[人物/车辆/地点/物件]
素材关键词：[中英文搜索词]
画面要求：[年龄/动作/环境/情绪/构图]
排除：[不需要的风格、AI感、广告感、错误地点]
可替代方案：[若找不到精确素材，可接受的替代画面]
```

#### 4b. 关键场景提示词设计

为每个场景类型（开场/高潮/结尾至少各一个）生成场景提示词草稿：

```
场景：[场景名/目的]
提示词：[完整场景描述，含主体、背景、光效、构图、氛围]
连贯性说明：[与上一场景的视觉衔接点]
反向提示词：[需要排除的内容]
```

#### 4b-stock. 关键场景素材 brief（素材主导时使用）

素材主导项目改用以下格式：

```
场景：[场景名/目的]
素材类型：[stock_video / stock_image / local_material / bgm / ambience]
搜索关键词：[中英文关键词]
画面/声音要求：[主体、动作、地点、季节、情绪、节奏]
时长槽位：[5s scene 编号范围]
替代策略：[找不到精确素材时的替代镜头]
```

#### 4c. 人工确认

**展示上述提示词设计后，停止并等待用户确认：**

```
以上是角色和场景的提示词设计草稿，请检查：
1. 角色外貌描述是否符合预期？
2. 场景风格是否一致？
3. 是否有需要补充或修改的细节？

确认后回复「确认」；需修改请指出具体修改意见。
```

**必须等待用户明确确认后，才能进入 Step 5。**

### Step 5：成本档位选择

**在提示词设计确认后，询问用户选择成本档位：**

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

素材主导项目使用另一套档位，并优先展示它：

---
**全外部素材（0）**
图片、视频、BGM、环境声全部下载或导入；不调用 AI 图片/视频生成，只允许 TTS。
适合：用户明确要求不用 AI 生成、使用外部素材、0 成本素材剪辑。

**混合素材（1）**
大部分下载素材，少量关键画面可生成图片或视频；每个生成调用必须有理由。

**生成优先（2）**
多数关键动态镜头可生成；下载素材仍用于 BGM、环境声、参考和补镜头。
---

### Step 6：写入产物

用户确认后：
1. 写 `brief/character-prompts.json`（角色提示词，多视角）
2. 写 `brief/scene-prompts.json`（场景提示词草稿）
3. 写 `brief/selected-concept.json`（含 `cost_tier` 字段）
4. 调用脚本生成 `input/input.json`：
   `python scripts/run_creative_design.py --project <name>`
   脚本检测到 `selected-concept.json` 已存在，直接读取并生成 `input.json`

素材主导时还必须写入：

- `source_mode`
- `production_mode`
- `material_cost_tier`
- `ai_image_generation`
- `ai_video_generation`
- `audio_provider`
- `poe_enabled`
- `bgm.required`
- `ambience.required`
- `subtitles.required`
- `subtitle_style`

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
