---
name: image-generator
description: Generate image assets through Poe model calls (with local mock fallback) and update manifest/usage artifacts.
---

# image_generator

## Purpose

根据分镜和关键帧约束生成静态图、封面图和参考图。分三个阶段执行：角色基准图 → 场景地点图 → 场景关键帧。**每个阶段之间必须有人工确认检查点，未经确认不得推进下一阶段。**

## 核心约束（必须严格遵守）

### 1. 禁止将图片/视频载入上下文

**任何时候，Claude 都不得将图片或视频文件内容读取到对话上下文中。**

- 生成结果只通过**文件路径**展示给用户
- 不使用 Read tool 读取图片/视频文件
- 不将图片/视频 URL 或 base64 传入 LLM 上下文
- 用户查看图片需自行打开文件路径

**违规示例（禁止）：**
```
Read("assets/images/scenes/scene-1a/scene-1a-kf-01.png")  # ❌ 禁止
```

**合规示例：**
```
生成完成，路径：assets/images/scenes/scene-1a/scene-1a-kf-01.png  # ✅ 只告知路径
```

### 2. 每场景关键帧数量：固定 4 张

所有场景时长统一为 5 秒（由 creative_design 阶段定死），因此每个场景固定生成 **4 张**关键帧：
- kf-01：起始帧（0s，衔接上一场景结尾）
- kf-02：中间帧 A（约 1.7s，动作/情绪推进）
- kf-03：中间帧 B（约 3.3s，动作/情绪推进）
- kf-04：结束帧（5s，供下一场景 kf-01 衔接用）

### 3. 场景起始帧必须衔接上一场景最后一帧

**每个场景的第一张图（kf-01）必须与上一个场景的最后一张图视觉衔接。**

- `scene-1b` 的 kf-01 → 在 prompt 中描述 scene-1a 最后一帧的视觉状态，并从该状态延续
- `scene-2a` 的 kf-01 → 在 prompt 中描述 scene-1b 最后一帧的视觉状态，并从该状态延续
- 第一个场景（scene-1a）的 kf-01 无需衔接，按正常 establishing shot 处理

**写入 asset-plan.json 时，scene kf-01 的 prompt 必须包含上一场景结尾描述。**
例如：`"（接续scene-Xa结尾：[上一场景最后状态描述]）[本帧内容]"`

### 4. 场景关键帧生成必须引用角色基准图

当场景中包含角色时（`char_refs` 不为空），生成场景关键帧时必须将对应角色的基准图路径作为参考（ref_images）传入模型，确保人物形象一致性。

- Phase 1 产生的角色基准图路径缓存在 `character-manifest.json`
- Phase 3 场景生成时读取 `character-manifest.json` 获取 ref_images
- 如果角色基准图不存在，停止并报错，不得跳过

---

## 执行流程（含人工确认检查点）

```
Phase 1: 生成角色基准图
    ↓
[CHECKPOINT-1: 人工确认角色基准图] ← 必须等待用户确认
    ↓
Phase 2: 生成场景地点参考图
    ↓
[CHECKPOINT-2: 人工确认地点图（可选快速确认）]
    ↓
Phase 3: 生成场景关键帧（每场景逐一生成，引用基准图）
    ↓
[CHECKPOINT-3: 每个场景生成后，展示路径，等待用户确认再继续下一场景]
```

### CHECKPOINT-1（角色基准图确认）

Phase 1 完成后，**停止执行**，向用户展示：

```
✅ 角色基准图生成完成，请检查后确认继续。

生成路径（请自行打开查看）：
- 大蛇 正面图：assets/images/characters/orochi/orochi-front.png
- 大蛇 面部特写：assets/images/characters/orochi/orochi-face.png
- ...

确认满意后回复「继续」；需要重新生成哪个角色请指出。
```

**必须等待用户回复后才能进入 Phase 2。**

### CHECKPOINT-2（地点图确认，快速）

Phase 2 完成后，展示路径，询问是否继续。若用户不回复则等待。

### CHECKPOINT-3（逐场景确认）

Phase 3 中，每个场景生成完毕后，展示该场景所有关键帧路径，询问：

```
✅ scene-Xa 生成完成（N 张图）：
- assets/images/scenes/scene-Xa/scene-Xa-kf-01.png
- assets/images/scenes/scene-Xa/scene-Xa-kf-02.png
...

回复「继续」进入下一场景；回复「重做」重新生成本场景。
```

---

## Planned Reads

- `projects/<project>/assets/asset-plan.json`（新主路径）
- `projects/<project>/prompts/prompts.json`（legacy fallback）
- `projects/<project>/input/input.json`
- `projects/<project>/assets/character-manifest.json`（角色基准图路径，Phase 3 引用）

## Planned Writes

- `projects/<project>/assets/images/characters/{char_id}/{view_id}.png`
- `projects/<project>/assets/images/locations/{loc_id}/establishing.png`
- `projects/<project>/assets/images/scenes/{scene_id}/{keyframe_id}.png`
- `projects/<project>/assets/manifest.json`
- `projects/<project>/assets/character-manifest.json`
- `projects/<project>/assets/image-usage.json`
- `projects/<project>/costs/poe-usage.jsonl`

## Runtime Expectations

- **任何阶段均不得将图片/视频文件内容读入上下文**
- 生成结果只通过文件路径展示
- 每阶段结束必须等待人工确认才能继续
- Phase 3 逐场景生成，每场景生成后单独确认
- 场景 kf-01 prompt 必须包含上一场景结尾视觉描述
- 场景有 char_refs 时必须传入角色 ref_images
- `assets/manifest.json` 的 `images` 字段必须可被后续阶段复用
