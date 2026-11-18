"""File-level rendering: one image (plus optional audio) to an MP4, and
several such scenes concatenated into one video."""

from __future__ import annotations

import os
import math
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

from .animator import WhiteboardAnimator
from .regions import SnippetRegionPlan, build_narration_weighted_plan

QUALITY = {
    "low": {"fps": 20, "bitrate": "500k"},
    "medium": {"fps": 24, "bitrate": "1500k"},
    "high": {"fps": 24, "bitrate": "3000k"},
}


@dataclass
class Scene:
    image: str | Path
    audio: str | Path | None = None
    duration: float | None = None
    region_plan: SnippetRegionPlan | None = None
    camera: object | None = None
    effects: object | None = None


def probe_duration(media_path: str | Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(media_path)],
        check=True, capture_output=True, text=True,
    )
    try:
        duration = float(out.stdout.strip())
    except ValueError as exc:
        raise ValueError(f"cannot determine duration of audio '{media_path}'") from exc
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError(f"audio '{media_path}' must have a finite duration greater than zero")
    return duration


def render_scene(
    scene: Scene,
    output_path: str | Path,
    *,
    quality: str = "medium",
    animator: WhiteboardAnimator | None = None,
    hand=None,
    audio_lead: float = 0.0,
    audio_tail: float | None = None,
    draw_ratio: float = 0.7,
    start_lead: float = 0.0,
    clean_bg: bool = False,
    text_sync: bool = False,
    text_share: float = 0.6,
) -> float:
    """Render one scene to an MP4. Returns the scene duration in seconds.

    With audio, the drawing finishes inside the audio and the rest holds the
    finished frame. With a region plan, regions draw in narration-weighted
    windows; otherwise the whole image draws over 70% of the duration.
    """
    if scene.audio is None and scene.duration is None:
        raise ValueError("scene needs audio or duration")
    audio_file = scene.audio
    temp_audio = None
    if audio_file is not None and (audio_lead > 0 or audio_tail is not None):
        # Trim trailing silence, keep `audio_tail` seconds, and delay the voice
        # by `audio_lead` so the pen is already moving when the voice starts.
        temp_audio = str(output_path) + ".audio.wav"
        filt = []
        if audio_tail is not None:
            filt.append("areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse")
        if audio_lead > 0:
            filt.append(f"adelay={int(audio_lead * 1000)}:all=1")
        if audio_tail is not None and audio_tail > 0:
            filt.append(f"apad=pad_dur={audio_tail}")
        subprocess.run(["ffmpeg", "-y", "-i", str(scene.audio), "-af", ",".join(filt), temp_audio],
                       check=True, capture_output=True)
        audio_file = temp_audio
    duration = scene.duration if audio_file is None else probe_duration(audio_file)
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("scene duration must be a finite number greater than zero")

    element_plan = None
    if scene.region_plan is not None:
        element_plan = build_narration_weighted_plan(scene.region_plan, duration)
    if animator is None:
        animator = WhiteboardAnimator(fade_duration=0.06 if element_plan else 0.12)

    with Image.open(scene.image) as image:
        # Normalize palette, grayscale, and transparent images to ink on white.
        rgba = image.convert("RGBA")
        background = Image.new("RGBA", image.size, "white")
        img_array = np.array(Image.alpha_composite(background, rgba).convert("RGB"))
    if clean_bg:
        img_array = whiten_paper(img_array)
    settings = QUALITY.get(quality, QUALITY["medium"])
    output_path = str(output_path)
    sync = None
    if text_sync and audio_file is not None and element_plan is None:
        bounds = speech_bounds(audio_file)
        if bounds is not None and bounds[1] - bounds[0] > 1.0:
            sp_start, sp_end = bounds
            t_start = max(sp_start - 0.1, 0.05)
            t_end = t_start + text_share * (sp_end - t_start)
            d_end = max(t_end + 0.8, min(sp_end + 0.3, duration - 0.1))
            if scene.effects is not None:     # leave time at the end for the movements to play
                d_end = max(t_end + 1.2, min(d_end, duration - scene.effects.hold))
            sync = (t_start, t_end, min(d_end, duration - 0.05))

    if scene.audio is None:
        animator.render_to_file(
            img_array, duration * draw_ratio, duration, output_path,
            element_plan=element_plan, hand=hand, start_lead=start_lead, text_sync=sync, camera=scene.camera, effects=scene.effects, **settings,
        )
        return duration

    video_only = output_path + ".video_only.mp4"
    animator.render_to_file(
        img_array, duration * draw_ratio, duration, video_only,
        element_plan=element_plan, hand=hand, start_lead=start_lead, text_sync=sync, camera=scene.camera, effects=scene.effects, **settings,
    )
    del img_array
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", video_only, "-i", str(audio_file),
             "-c:v", "copy", "-c:a", "aac", output_path],
            check=True, capture_output=True,
        )
    finally:
        for leftover in (video_only, temp_audio):
            if leftover:
                try:
                    os.unlink(leftover)
                except OSError:
                    pass
    return duration


def whiten_paper(img_array: np.ndarray, tolerance: int = 28) -> np.ndarray:
    """Turn an off-white / cream / grey-ish paper background into pure white.

    AI images often come with a faint tint or JPEG noise that is not quite
    white.  The animator treats that as one huge fill and spends the first
    seconds sweeping it in, so nothing visible is drawn while the voice talks.
    """
    small = img_array[::4, ::4].reshape(-1, 3)
    keys = (small // 8).astype(np.int32)
    codes = keys[:, 0] * 1024 + keys[:, 1] * 32 + keys[:, 2]
    values, counts = np.unique(codes, return_counts=True)
    top = int(values[counts.argmax()])
    if counts.max() < 0.30 * len(codes):
        return img_array  # no dominant paper colour (full-bleed scene)
    paper = np.array([(top // 1024) * 8 + 4, ((top // 32) % 32) * 8 + 4, (top % 32) * 8 + 4])
    if paper.min() < 200 or (paper >= 252).all():
        return img_array  # already white, or a dark/coloured background
    dist = np.abs(img_array.astype(np.int16) - paper).max(axis=2)
    out = img_array.copy()
    out[dist <= tolerance] = 255
    return out


def speech_bounds(path: str) -> tuple[float, float] | None:
    """Return (start, end) seconds of audible speech in an audio file."""
    try:
        raw = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", str(path), "-f", "s16le", "-ac", "1", "-ar", "16000", "-"],
            check=True, capture_output=True).stdout
    except (subprocess.CalledProcessError, OSError):
        return None
    x = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    step = 320  # 20 ms
    n = len(x) // step
    if n < 5:
        return None
    rms = np.sqrt((x[: n * step].reshape(n, step) ** 2).mean(axis=1))
    thr = max(0.004, 0.04 * float(rms.max()))
    loud = np.where(rms > thr)[0]
    if loud.size == 0:
        return None
    return loud[0] * 0.02, (loud[-1] + 1) * 0.02


def concatenate(paths: list[str | Path], output_path: str | Path) -> None:
    """Join MP4 segments without re-encoding."""
    output_path = str(output_path)
    concat_list = output_path + ".concat.txt"
    try:
        with open(concat_list, "w") as f:
            for p in paths:
                f.write(f"file '{os.path.abspath(p)}'\n")
        subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
             "-i", concat_list, "-c", "copy", output_path],
            check=True, capture_output=True,
        )
    finally:
        if os.path.exists(concat_list):
            os.remove(concat_list)


def render_video(
    scenes: list[Scene],
    output_path: str | Path,
    *,
    quality: str = "medium",
    hand=None,
    **timing_opts,
) -> list[float]:
    """Render every scene and concatenate them. Returns per-scene durations.

    Every scene must have audio or none of them may, since ffmpeg concat
    needs matching streams.
    """
    if not scenes:
        raise ValueError("no scenes")
    with_audio = {scene.audio is not None for scene in scenes}
    if len(with_audio) > 1:
        raise ValueError("either every scene has audio or none does")
    if len(scenes) == 1:
        return [render_scene(scenes[0], output_path, quality=quality, hand=hand, **timing_opts)]

    animator = None
    durations = []
    with tempfile.TemporaryDirectory() as temp_dir:
        segments = []
        for index, scene in enumerate(scenes):
            plan = build_narration_weighted_plan(scene.region_plan, 1.0) if scene.region_plan else None
            if animator is None or (animator.fade_duration == 0.12) == bool(plan):
                animator = WhiteboardAnimator(fade_duration=0.06 if plan else 0.12)
            segment = os.path.join(temp_dir, f"segment_{index:03d}.mp4")
            durations.append(render_scene(scene, segment, quality=quality, animator=animator, hand=hand, **timing_opts))
            segments.append(segment)
        concatenate(segments, output_path)
    return durations
