"""生成八神庵写实风格图片 + 参考生视频，下载到 outputs/iori/"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from vidu_web.session import ViduWebSession
from vidu_web import api

COOKIES = Path("~/.config/cucumis/vidu_web_session.json").expanduser()
OUTPUT_DIR = Path(__file__).parent.parent / "outputs" / "iori"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

IMAGE_PROMPTS = [
    "八神庵写实版，拳皇KOF经典角色，日本男性，红色长发，黑色皮夹克，紫色火焰缠绕双手，升龙拳起跳瞬间，正面视角，电影级光影，超写实人像摄影",
    "八神庵写实版，拳皇KOF，红发男性，黑色长袍，升龙拳腾空姿态，侧面45度视角，紫焰特效，夜晚城市背景，写实摄影风格，超高清",
    "八神庵写实版，拳皇KOF，红色凌乱长发，白色运动裤，升龙拳全程动作，俯视视角，紫色焰气特效，霓虹灯街道，电影感画质",
    "八神庵写实版，拳皇KOF，特写半身像，红发遮眼，黑色夹克，双手紫火，升龙预备蓄力姿势，低角度仰拍，强烈阴影对比，超写实风格",
]

VIDEO_PROMPT = "八神庵，升龙拳连续动作，紫色火焰爆发，头发飘动，电影慢动作特效，暗黑格斗场景"

with ViduWebSession(headless=True, cookies_path=COOKIES) as session:
    page = session.page
    page.goto("https://www.vidu.cn", wait_until="domcontentloaded", timeout=60_000)

    # ── 第一步：生成4张图片 ──────────────────────────────────────────
    image_paths = []
    for i, prompt in enumerate(IMAGE_PROMPTS, 1):
        print(f"\n[gen_iori] 生成图片 {i}/4 …")
        settings = {"model_version": "3.1", "resolution": "1080p", "aspect_ratio": "9:16"}
        task_id = api.create_task(page, "text2image", prompt, settings)
        print(f"[gen_iori]   task_id={task_id}, 等待中 …")
        result = api.poll_task(page, task_id, poll_interval=5.0, max_wait=300.0)
        url = api.extract_media_url(result)
        if url:
            dest = OUTPUT_DIR / f"iori_{i}_{task_id}.png"
            api.download_media(url, dest)
            image_paths.append(dest)
            print(f"[gen_iori]   已保存 → {dest}")
        else:
            print(f"[gen_iori]   警告：图片 {i} 无下载链接")

    print(f"\n[gen_iori] 图片生成完成，共 {len(image_paths)} 张")

    # ── 第二步：参考生视频 ───────────────────────────────────────────
    if not image_paths:
        print("[gen_iori] 无可用图片，跳过视频生成")
        sys.exit(1)

    print(f"\n[gen_iori] 上传 {len(image_paths)} 张图片生成视频 …")
    ref_uris = []
    for p in image_paths:
        print(f"[gen_iori]   上传 {p.name} …")
        uri = api.upload_image(page, p)
        ref_uris.append(uri)

    vid_settings = {
        "model_version": "3.1_pro",
        "resolution": "1080p",
        "aspect_ratio": "9:16",
        "duration": 4,
    }
    task_id = api.create_task(
        page, "character2video", VIDEO_PROMPT, vid_settings, ref_image_uris=ref_uris
    )
    print(f"[gen_iori]   video task_id={task_id}, 等待中 …")
    result = api.poll_task(page, task_id, poll_interval=10.0, max_wait=600.0)
    video_url = api.extract_media_url(result)
    if video_url:
        dest = OUTPUT_DIR / f"iori_video_{task_id}.mp4"
        api.download_media(video_url, dest)
        print(f"\n[gen_iori] ✓ 视频已保存 → {dest}")
    else:
        print("[gen_iori] 警告：视频无下载链接")
