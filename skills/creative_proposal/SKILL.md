---
name: creative-proposal
description: Generate multiple creative concept proposals from brief and let user select before proceeding. Use after creative_brief_intake and before input_parser.
---

# creative_proposal

## Purpose

基于 Creative Brief 生成 3 个差异化的创意方向，呈现给用户选择，确认后再进入生产流水线。

**这是人在环的关键节点。未经用户确认，不得推进到 input_parser 及后续阶段。**

## Reads

- `projects/<project>/brief/intake.json`
- `projects/<project>/brief/creative-brief.md`

## Writes

- `projects/<project>/brief/proposals.json`（3 个方案）
- `projects/<project>/brief/selected-concept.json`（用户选定的方案）

## 方案生成原则

3 个方案必须代表**真实不同的创意方向**，不是同一角度的微调。

差异维度可以是：
- **叙事角度**：问题驱动 vs 案例驱动 vs 情感驱动
- **情绪弧线**：平稳递进 vs 强对比反转 vs 压抑爆发
- **视觉风格**：纪实克制 vs 戏剧张力 vs 沉浸叙事
- **开场钩子**：数据冲击 vs 反常识问题 vs 场景代入

## 每个方案包含的字段

```json
{
  "concept_id": "A",
  "title": "方案标题（3-6字）",
  "angle": "一句话说清楚这个方向的核心切入点",
  "emotional_arc": "情绪走向描述，例如：克制→积累→爆发",
  "opening_line": "第一句旁白台词（可直接朗读）",
  "visual_direction": "视觉风格关键词，2-3个",
  "music_direction": "音乐情绪关键词",
  "why_this_works": "这个方向为什么适合本项目（1-2句）"
}
```

## 呈现格式

向用户展示时使用清晰的对比格式，例如：

---
**方案 A：「反常识切入」**
开场白：「99% 的人以为失败是因为努力不够——但数据说的是另一回事。」
情绪弧线：疑问 → 数据冲击 → 洞察落地
视觉风格：冷色调、数字特写、慢推镜头

**方案 B：「场景代入」**
开场白：「那天他盯着账单看了三分钟，一句话没说。」
情绪弧线：沉浸 → 共鸣 → 转折升华
视觉风格：暖色调、人物特写、手持跟拍

**方案 C：「直接揭示」**
开场白：「选址决定了 80% 的餐饮命运。」
情绪弧线：直白 → 论证 → 行动号召
视觉风格：信息图、俯视全景、平稳运镜
---

## 用户确认流程

1. 展示 3 个方案后，询问用户：选择哪个？或是否需要调整？
2. 用户可以：
   - 选择某个方案（A/B/C）
   - 要求修改某个方案的某个维度
   - 要求重新生成方向
   - 将多个方案的元素混合（Claude 融合后再次确认）
3. **只有用户明确说"确认"或"就用这个"后，才写入 `selected-concept.json`**
4. 写入后告知用户可以继续下一步

## selected-concept.json 格式

```json
{
  "selected_at": "2026-03-15T12:00:00",
  "concept_id": "A",
  "title": "...",
  "angle": "...",
  "emotional_arc": "...",
  "opening_line": "...",
  "visual_direction": "...",
  "music_direction": "...",
  "user_notes": "用户在选择时补充的任何备注"
}
```

## Runtime Expectations

- 本阶段**主要由 Claude 驱动**，脚本仅用于生成占位方案（自动化场景）
- 脚本模式：`python scripts/run_creative_proposal.py --project <name>`（生成模板方案，跳过用户选择）
- 脚本模式下默认选择方案 A，写入 `selected-concept.json`，并标注 `auto_selected: true`
- 下游阶段（input_parser、script_writer）会读取 `selected-concept.json` 来获取创意方向
