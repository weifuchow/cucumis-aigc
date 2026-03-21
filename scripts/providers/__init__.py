"""Multimodal provider abstraction layer.

Usage::

    from scripts.providers.factory import load_provider

    provider = load_provider()          # reads MEDIA_PROVIDER from .env
    result = provider.generate_image(model, prompts)
    result = provider.generate_video(model, scenes, aspect_ratio)
    result = provider.generate_audio(model, prompt, duration_seconds, language)
"""
