---
name: asset-planner
description: Analyze script and storyboard artifacts to produce assets/asset-plan.json for image planning. Use after storyboard exists and before image generation.
---

# Skill: asset_planner

## 职责

分析 `script.json` 和 `storyboard.json`，输出结构化图片生成方案 `assets/asset-plan.json`。

**这是一个 Claude Code 推理阶段**：Claude 读取文件、完成判断，然后将推理结果直接写入 JSON 文件。
`run_asset_planner.py` 只负责验证和规范化，不调用任何 LLM。

---

## 触发条件

- `storyboard/storyboard.json` 已存在
- `assets/asset-plan.json` 尚未存在，或需要强制刷新

---

## 输入文件（必须先读）

| 文件 | 用途 |
|------|------|
| `input/input.json` | 获取 `aspect_ratio`、`style`、`language` |
| `script/script.json` | 分析人物、情感、叙事结构 |
| `storyboard/storyboard.json` | 分析场景时长、画面描述、运镜意图 |

---

## Claude 推理步骤

### 第一步：判断是否需要角色基准图

**需要 `has_characters: true`**：脚本中有具体人物且多场景需要外貌一致性
**设为 `has_characters: false`**：纯风景、抽象动效、产品展示、无具体人物

若需要角色，分析每个角色需要哪些视角（不要固定输出 5 个）：
- 对话/情感戏 → 重点 `closeup`、`three_quarter`
- 动作戏 → 重点 `full_body`、`side`
- 只有远景 → `full_body` 即可（最少 1 个）
- 全类型 → `front + side + three_quarter + closeup + full_body`

### 第二步：判断是否需要场景建立图

**需要 `has_locations: true`**：有具体环境场景且需要视觉一致性
**设为 `has_locations: false`**：完全抽象内容、纯文字动效

### 第三步：规划每个场景的关键帧数量（3~7）

根据场景时长和内容复杂度：
- `< 3s` 或纯环境：**3 个**关键帧
- `3~6s` 标准叙事：**4~5 个**关键帧
- `> 6s` 或多动作：**6~7 个**关键帧

### 第四步：写出 asset-plan.json

---

## 输出文件

`assets/asset-plan.json` — 符合 `schemas/asset-plan.schema.json` 的完整 JSON：

```json
{
  "decisions": {
    "has_characters": true,
    "character_reason": "脚本中出现主角少年，多场景需要人物外貌一致性",
    "has_locations": true,
    "location_reason": "场景涉及废墟、王座厅等具体环境，需要建立镜头参考"
  },
  "characters": [
    {
      "char_id": "char-hero",
      "name": "屠龙少年",
      "description": "17岁少年，短黑发，银色铠甲，左手持龙纹剑",
      "style_lock": "anime style, consistent face, silver armor, dragon sword",
      "negative_lock": "different face, inconsistent costume, extra limbs",
      "views": [
        {
          "view_id": "char-hero-front",
          "view_type": "front",
          "prompt": "young hero, front view, silver armor, short black hair, dragon sword, anime style, consistent face",
          "negative_prompt": "blurry, inconsistent face, extra limbs",
          "aspect_ratio": "1:1"
        }
      ]
    }
  ],
  "locations": [
    {
      "loc_id": "loc-ruins",
      "name": "废墟广场",
      "description": "战后废墟，破碎的石柱，燃烧的火焰",
      "atmosphere": "dark, smoky, dramatic",
      "prompt": "ruined plaza, broken stone pillars, burning flames, dramatic lighting, no characters, cinematic wide shot",
      "negative_prompt": "blurry, low detail, people, characters",
      "aspect_ratio": "9:16"
    }
  ],
  "scenes": [
    {
      "scene_id": "scene-01",
      "start_time": 0.0,
      "end_time": 5.0,
      "duration_seconds": 5.0,
      "char_refs": ["char-hero"],
      "loc_ref": "loc-ruins",
      "keyframes": [
        {
          "keyframe_id": "scene-01-kf-01",
          "timestamp": 0.0,
          "frame_type": "establishing",
          "description": "废墟广场全景，少年站在中央",
          "prompt": "ruined plaza establishing shot, young hero standing center, silver armor, dramatic lighting, anime style",
          "negative_prompt": "blurry, low detail",
          "aspect_ratio": "9:16"
        }
      ]
    }
  ]
}
```

---

## 硬性规则

1. `has_characters: false` → `characters` 必须是空数组 `[]`
2. `has_locations: false` → `locations` 必须是空数组 `[]`
3. `char_refs` 只引用 `characters` 中已定义的 `char_id`；无角色场景用 `[]`
4. `loc_ref` 只引用 `locations` 中已定义的 `loc_id`；无对应场景用 `""`
5. 同一角色在多个场景出现时，只在 `characters` 里定义一次
6. **所有 `prompt` 字段用英文**；`description`、`reason` 等描述字段用中文
7. ID 格式：英文小写连字符（如 `char-hero`、`loc-ruins`、`scene-01-kf-01`）
8. 每个 keyframe 的风格词必须与对应角色的 `style_lock` 保持一致
9. 不要在 JSON 外附加任何解释文字

---

## 执行命令

写完 `asset-plan.json` 后，调用 `run_asset_planner.py` 验证并规范化：

```bash
python scripts/run_asset_planner.py --project projects/<name>
```

成功输出示例：
```
[asset_planner] validated: 2 characters (needed=True), 3 locations (needed=True), 7 scenes
projects/<name>/assets/asset-plan.json
```

---

## 下一阶段

`asset_planner` 完成后，运行 `image_generator`：

```bash
python scripts/run_image_generator.py --project projects/<name>
```

图片生成器会读取 `asset-plan.json`，按三个阶段生成：
1. Phase 1：角色多视角基准图 → `assets/images/characters/{char_id}/`
2. Phase 2：场景建立图 → `assets/images/locations/{loc_id}/`
3. Phase 3：每场景关键帧图 → `assets/images/scenes/{scene_id}/`
