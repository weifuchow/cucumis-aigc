from __future__ import annotations

import pathlib
import shlex
import shutil
import subprocess
import tempfile
from typing import Any

from .base import MultimodalProvider


type RefImage = dict[str, str]


class CodexProvider(MultimodalProvider):
    """Image provider backed by the local Codex CLI image generation tool."""

    def __init__(
        self,
        *,
        codex_bin: str = "codex",
        working_directory: pathlib.Path | None = None,
        default_image_model: str = "image-2.0",
        timeout_seconds: int = 600,
    ) -> None:
        self.codex_bin = codex_bin
        self.working_directory = working_directory or pathlib.Path.cwd()
        self.default_image_model = default_image_model
        self.timeout_seconds = timeout_seconds

    def generate_image(
        self,
        model: str,
        prompts: list[dict[str, Any]],
        **opts: Any,
    ) -> dict[str, Any]:
        images: list[dict[str, Any]] = []
        commands: list[str] = []
        request_ids: list[str] = []

        for index, item in enumerate(prompts, start=1):
            scene_id = str(item.get("scene_id", f"scene-{index}"))
            prompt_id = str(item.get("prompt_id", scene_id))
            positive_prompt = str(item.get("positive_prompt", "")).strip()
            negative_prompt = str(item.get("negative_prompt", "")).strip()
            aspect_ratio = str(item.get("aspect_ratio", "1:1")).strip()
            ref_images = self._collect_ref_images(item.get("_ref_images"))

            local_path, command = self._run_codex_image_generation(
                model=model,
                scene_id=scene_id,
                prompt_id=prompt_id,
                positive_prompt=positive_prompt,
                negative_prompt=negative_prompt,
                aspect_ratio=aspect_ratio,
                ref_images=ref_images,
            )

            request_id = f"codex-{scene_id}-{prompt_id}"
            commands.append(command)
            request_ids.append(request_id)
            images.append(
                {
                    "scene_id": scene_id,
                    "prompt_id": prompt_id,
                    "url": local_path.as_uri(),
                    "style": item.get("style"),
                    "aspect_ratio": aspect_ratio,
                    "request_id": request_id,
                }
            )

        return {
            "mode": "live",
            "model": model,
            "request_id": request_ids[-1] if request_ids else "",
            "request_ids": request_ids,
            "images": images,
            "raw_response": {
                "provider": "codex",
                "command": commands[-1] if commands else "",
                "commands": commands,
            },
            "usage": {
                "cost_points": 0,
                "mode": "live",
                "note": "Codex app image generation usage is tracked by the local Codex session.",
            },
        }

    def generate_video(
        self,
        model: str,
        scenes: list[dict[str, Any]],
        aspect_ratio: str,
        **opts: Any,
    ) -> dict[str, Any]:
        raise NotImplementedError("CodexProvider does not support video generation")

    def generate_audio(
        self,
        model: str,
        prompt: str,
        duration_seconds: int,
        language: str,
        **opts: Any,
    ) -> dict[str, Any]:
        raise NotImplementedError("CodexProvider does not support audio generation")

    def _run_codex_image_generation(
        self,
        *,
        model: str,
        scene_id: str,
        prompt_id: str,
        positive_prompt: str,
        negative_prompt: str,
        aspect_ratio: str,
        ref_images: list[RefImage],
    ) -> tuple[pathlib.Path, str]:
        if shutil.which(self.codex_bin) is None:
            raise RuntimeError(f"Codex CLI not found on PATH: {self.codex_bin}")

        suffix = ".png"
        with tempfile.TemporaryDirectory(prefix="cucumis-codex-image-") as tmp:
            temp_dir = pathlib.Path(tmp)
            output_path = temp_dir / f"{scene_id}-{prompt_id}{suffix}"
            message_path = temp_dir / "codex-last-message.txt"

            prompt = self._build_prompt(
                model=model,
                output_path=output_path,
                positive_prompt=positive_prompt,
                negative_prompt=negative_prompt,
                aspect_ratio=aspect_ratio,
                ref_images=ref_images,
            )
            command = [
                self.codex_bin,
                "exec",
                "--sandbox",
                "workspace-write",
                "--cd",
                str(self.working_directory),
                "--ephemeral",
                *self._build_image_args(ref_images),
                "--output-last-message",
                str(message_path),
                prompt,
            ]
            completed = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )

            final_message = message_path.read_text(encoding="utf-8").strip() if message_path.is_file() else ""
            resolved_path = self._extract_output_path(final_message or completed.stdout or "", output_path)
            if not resolved_path.is_file():
                raise RuntimeError(
                    "Codex image generation did not produce the expected file. "
                    f"Expected something like {output_path}, got {resolved_path}."
                )

            with tempfile.NamedTemporaryFile(
                delete=False,
                prefix="cucumis-codex-out-",
                suffix=resolved_path.suffix,
            ) as handle:
                final_copy = pathlib.Path(handle.name)
            shutil.copy2(resolved_path, final_copy)
            return final_copy, " ".join(shlex.quote(part) for part in command)

    @staticmethod
    def _build_prompt(
        *,
        model: str,
        output_path: pathlib.Path,
        positive_prompt: str,
        negative_prompt: str,
        aspect_ratio: str,
        ref_images: list[RefImage],
    ) -> str:
        instructions = [
            "Use the image generation tool exactly once.",
            f"Target image model: {model}.",
            f"Aspect ratio: {aspect_ratio}.",
            f"Save the generated image to this exact absolute path: {output_path}.",
            "Return only that absolute file path in the final response.",
            f"Prompt: {positive_prompt}",
        ]
        if ref_images:
            instructions.append(
                "Reference images are attached. Use them to preserve subject identity, composition, or style where relevant."
            )
            instructions.extend(CodexProvider._reference_guidance_lines(ref_images))
            instructions.append("Reference images:")
            for index, ref in enumerate(ref_images, start=1):
                role = ref.get("role", "reference")
                path = ref.get("path", "")
                instructions.append(f"- ref_{index}: role={role}; path={path}")
        if negative_prompt:
            instructions.append(f"Avoid: {negative_prompt}")
        return "\n".join(instructions)

    @staticmethod
    def _extract_output_path(raw: str, fallback: pathlib.Path) -> pathlib.Path:
        for line in reversed(raw.splitlines()):
            candidate = line.strip().strip("`")
            if not candidate:
                continue
            if candidate.startswith("file://"):
                return pathlib.Path(candidate[7:])
            if candidate.startswith("/"):
                return pathlib.Path(candidate)
        return fallback

    @staticmethod
    def _collect_ref_images(raw_refs: Any) -> list[RefImage]:
        refs: list[RefImage] = []
        if not isinstance(raw_refs, list):
            return refs
        for ref in raw_refs:
            path_value = ""
            role_value = "reference"
            if isinstance(ref, dict):
                path_value = str(ref.get("path", "")).strip()
                role_value = str(ref.get("role", "reference")).strip() or "reference"
            elif isinstance(ref, str):
                path_value = ref.strip()
            if not path_value:
                continue
            path = pathlib.Path(path_value)
            if path.is_file():
                refs.append({"path": str(path), "role": role_value})
        return refs

    @staticmethod
    def _build_image_args(ref_images: list[RefImage]) -> list[str]:
        args: list[str] = []
        for ref in ref_images:
            args.extend(["--image", ref["path"]])
        return args

    @staticmethod
    def _reference_guidance_lines(ref_images: list[RefImage]) -> list[str]:
        role_guidance = {
            "character": "For role=character references, preserve the subject identity, face, silhouette, clothing, and key visual traits.",
            "style": "For role=style references, borrow the visual style, color language, materials, and rendering approach without copying unrelated content.",
            "location": "For role=location references, preserve the scene layout, environment cues, and spatial framing where appropriate.",
            "composition": "For role=composition references, follow the shot framing, camera angle, and overall visual balance.",
        }
        lines: list[str] = []
        seen: set[str] = set()
        for ref in ref_images:
            role = ref.get("role", "reference").strip().lower() or "reference"
            guidance = role_guidance.get(role)
            if guidance and guidance not in seen:
                seen.add(guidance)
                lines.append(guidance)
        if not lines:
            lines.append("Treat the attached references as guidance for identity, style, or composition as appropriate.")
        return lines


def make_codex_provider(
    env: dict[str, str] | None = None,
    env_path: pathlib.Path | None = None,
    **_ignored: object,
) -> CodexProvider:
    import os

    env_values: dict[str, str] = {}
    if env_path and env_path.is_file():
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            env_values[key.strip()] = value.strip().strip("'").strip('"')
    env_values.update(os.environ)
    if env:
        env_values.update(env)

    working_directory = pathlib.Path(env_values.get("CODEX_WORKING_DIRECTORY", pathlib.Path.cwd()))
    timeout_seconds = int(env_values.get("CODEX_IMAGE_TIMEOUT_SECONDS", "600"))
    default_image_model = env_values.get("CODEX_IMAGE_MODEL", "image-2.0")
    codex_bin = env_values.get("CODEX_BIN", "codex")

    return CodexProvider(
        codex_bin=codex_bin,
        working_directory=working_directory,
        default_image_model=default_image_model,
        timeout_seconds=timeout_seconds,
    )
