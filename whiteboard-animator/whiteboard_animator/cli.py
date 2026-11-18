"""Command line entry point: whiteboard-animate."""

from __future__ import annotations

import argparse
import asyncio
import logging
import math
import os
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, UnidentifiedImageError
from pydantic import ValidationError

from .regions import SnippetRegionPlan
from .render import Scene, render_video


def _load_plan(path: str | None) -> SnippetRegionPlan | None:
    if not path:
        return None
    try:
        return SnippetRegionPlan.model_validate_json(Path(path).read_text())
    except (ValidationError, UnicodeError) as exc:
        raise ValueError(f"invalid region plan '{path}': {exc}") from exc


def _validate_inputs(args: argparse.Namespace) -> None:
    if not args.audio and (not math.isfinite(args.duration) or args.duration <= 0):
        raise ValueError("--duration must be a finite number greater than zero")
    for path in [*args.images, *args.audio, *args.regions]:
        if not Path(path).is_file():
            raise ValueError(f"input file not found: {path}")
    for path in args.images:
        try:
            with Image.open(path) as image:
                image.verify()
        except (UnidentifiedImageError, OSError) as exc:
            raise ValueError(f"cannot read image '{path}'; use a valid PNG or JPEG image") from exc
    output = Path(args.output)
    if output.suffix.lower() != ".mp4":
        raise ValueError("--output must end in .mp4")
    if not output.parent.is_dir():
        raise ValueError(f"output directory does not exist: {output.parent}; create it first")
    if output.is_dir():
        raise ValueError(f"output path is a directory: {output}")
    if output.resolve() in {Path(p).resolve() for p in [*args.images, *args.audio, *args.regions]}:
        raise ValueError("--output must be different from every input file")
    required = ["ffmpeg"] + (["ffprobe"] if args.audio else [])
    missing = [name for name in required if shutil.which(name) is None]
    if missing:
        raise ValueError(
            f"{', '.join(missing)} not found on PATH. Install FFmpeg "
            "(macOS: brew install ffmpeg; Ubuntu/Debian: sudo apt install ffmpeg; "
            "Windows: https://ffmpeg.org/download.html), then reopen your terminal."
        )


def _detect_plan(image: Path, narration: str, model: str | None) -> SnippetRegionPlan:
    try:
        from google import genai
    except ImportError as exc:
        raise SystemExit(
            "--detect-regions needs the gemini extra: pip install 'whiteboard-animator[gemini]'"
        ) from exc
    from .detect_regions import DEFAULT_MODEL, detect_region_plan

    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise SystemExit("--detect-regions needs GOOGLE_API_KEY in the environment")
    client = genai.Client(api_key=api_key)
    return asyncio.run(detect_region_plan(
        google_client=client,
        image_path=image,
        transcript_text=narration,
        model=model or DEFAULT_MODEL,
    ))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="whiteboard-animate",
        description="Animate whiteboard-style images as hand-drawn reveal videos.",
    )
    parser.add_argument("images", nargs="+", help="scene images in order")
    parser.add_argument("-o", "--output", required=True, help="output MP4")
    parser.add_argument("--audio", nargs="*", default=[],
                        help="one narration file per image, in the same order")
    parser.add_argument("--duration", type=float, default=8.0,
                        help="seconds per scene when there is no audio (default 8)")
    parser.add_argument("--quality", choices=["low", "medium", "high"], default="medium")
    parser.add_argument("--regions", nargs="*", default=[],
                        help="one region plan JSON per image, in the same order")
    parser.add_argument("--detect-regions", action="store_true",
                        help="ask Gemini for a region plan per image (needs GOOGLE_API_KEY)")
    parser.add_argument("--narration", nargs="*", default=[],
                        help="narration text per image, used by --detect-regions")
    parser.add_argument("--gemini-model", default=None)
    parser.add_argument("--save-regions", action="store_true",
                        help="write detected plans next to the output as <output>.regions.<n>.json")
    parser.add_argument("--audio-lead", type=float, default=0.25, metavar="SEC",
                        help="delay the voice this many seconds so drawing starts first (default 0.25)")
    parser.add_argument("--audio-tail", type=float, default=0.15, metavar="SEC",
                        help="trim trailing silence from the audio and keep this much (default 0.15; -1 = leave audio untouched)")
    parser.add_argument("--draw-ratio", type=float, default=0.7, metavar="R",
                        help="drawing finishes at this fraction of the clip length (default 0.7)")
    parser.add_argument("--start-lead", type=float, default=0.15, metavar="SEC",
                        help="first visible ink appears after this many seconds; 0 = off (default 0.15)")
    parser.add_argument("--clean-bg", action=argparse.BooleanOptionalAction, default=True,
                        help="turn a cream/off-white paper background into pure white (default on)")
    parser.add_argument("--text-sync", action=argparse.BooleanOptionalAction, default=True,
                        help="write the headline in step with the voice, then draw the pictures (default on)")
    parser.add_argument("--text-share", type=float, default=0.6, metavar="R",
                        help="headline is finished after this fraction of the speech (default 0.6)")
    parser.add_argument("--camera", default=None, metavar="auto|smart|off|FILE.json",
                        help="virtual camera: 'auto' follows the pen, 'smart' = IMAGE.camera.json if present else auto, a JSON file gives exact keyframes, "
                             "'off' disables. Default: use IMAGE.camera.json next to each image if present")
    parser.add_argument("--camera-zoom", type=float, default=1.3, metavar="Z",
                        help="zoom used by --camera auto (default 1.3)")
    parser.add_argument("--effects", default=None, metavar="off|FILE.json",
                        help="make parts of the picture move (sway, bounce, pulse, wave...). Default: use IMAGE.effects.json next to each image if present; 'off' disables")
    parser.add_argument("--effects-preview", action="store_true",
                        help="also save OUTPUT.effects-preview.png showing the effect boxes")
    parser.add_argument("--max-dim", type=int, default=None, metavar="PX",
                        help="longest side of the video in pixels (default 1280; images smaller than this are not enlarged)")
    parser.add_argument("--hand", action=argparse.BooleanOptionalAction, default=True,
                        help="show a drawing hand following the pen (default on; --no-hand turns it off)")
    parser.add_argument("--hand-style", default="doodle",
                        help="doodle (default), brown, dark or light, or the path to your own PNG hand")
    parser.add_argument("--hand-tip", default=None, metavar="X,Y",
                        help="pen-tip pixel inside a custom hand PNG, e.g. 35,35")
    parser.add_argument("--hand-scale", type=float, default=1.0,
                        help="hand size multiplier (default 1.0 = 26%% of frame width)")
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser


def _run(args: argparse.Namespace) -> int:
    n = len(args.images)
    if args.audio and len(args.audio) != n:
        raise SystemExit(f"expected {n} audio files, got {len(args.audio)}")
    if args.regions and len(args.regions) != n:
        raise SystemExit(f"expected {n} region plans, got {len(args.regions)}")
    if args.regions and args.detect_regions:
        raise SystemExit("use --regions or --detect-regions, not both")
    if args.narration and len(args.narration) != n:
        raise SystemExit(f"expected {n} narration strings, got {len(args.narration)}")

    _validate_inputs(args)
    scenes = []
    for index, image in enumerate(args.images):
        plan = _load_plan(args.regions[index]) if args.regions else None
        if args.detect_regions:
            narration = args.narration[index] if args.narration else ""
            plan = _detect_plan(Path(image), narration, args.gemini_model)
            if args.save_regions:
                plan_path = f"{args.output}.regions.{index}.json"
                Path(plan_path).write_text(plan.model_dump_json(indent=2))
                print(f"wrote {plan_path}", file=sys.stderr)
        scenes.append(Scene(
            camera=_make_camera(args, image),
            effects=_make_effects(args, image),
            image=image,
            audio=args.audio[index] if args.audio else None,
            duration=None if args.audio else args.duration,
            region_plan=plan,
        ))

    if args.max_dim:
        from . import animator as _animator
        _animator.MAX_DIM = args.max_dim
    hand = None
    if args.hand:
        from .hand import Hand
        tip = tuple(float(v) for v in args.hand_tip.split(",")) if args.hand_tip else None
        hand = Hand(args.hand_style, tip=tip, scale=args.hand_scale)
    durations = render_video(
        scenes, args.output, quality=args.quality, hand=hand,
        audio_lead=args.audio_lead,
        audio_tail=None if args.audio_tail < 0 else args.audio_tail,
        draw_ratio=args.draw_ratio, start_lead=args.start_lead, clean_bg=args.clean_bg,
        text_sync=args.text_sync, text_share=args.text_share,
    )
    print(f"wrote {args.output} ({sum(durations):.1f}s, {len(durations)} scene(s))", file=sys.stderr)
    return 0


def _make_effects(args, image):
    from .effects import Effects
    if args.effects == "off":
        return None
    path = Path(args.effects) if args.effects else Path(image).with_suffix(".effects.json")
    if not path.exists():
        if args.effects:
            raise SystemExit(f"effects file not found: {path}")
        return None
    print(f"effects: {Path(image).name}: using {path}", file=sys.stderr)
    fx = Effects.from_file(path)
    if args.effects_preview:
        fx.preview_path = f"{args.output}.effects-preview.png"
    return fx


def _make_camera(args, image):
    from .camera import Camera
    mode = args.camera
    name = Path(image).name
    if mode == "off":
        return None
    if mode == "auto":
        print(f"camera: {name}: auto (follows the pen)", file=sys.stderr)
        return Camera.auto(args.camera_zoom)
    if mode and mode != "smart":
        print(f"camera: {name}: using {mode}", file=sys.stderr)
        return Camera.from_file(mode)
    sidecar = Path(image).with_suffix(".camera.json")
    if sidecar.exists():
        print(f"camera: {name}: using {sidecar}", file=sys.stderr)
        return Camera.from_file(sidecar)
    if mode == "smart":
        print(f"camera: {name}: no {sidecar.name} found, using auto", file=sys.stderr)
        return Camera.auto(args.camera_zoom)
    print(f"camera: {name}: off (no {sidecar.name} next to the image; use --camera auto or --camera smart)",
          file=sys.stderr)
    return None


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )
    try:
        return _run(args)
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr or ""
        if isinstance(detail, bytes):
            detail = detail.decode(errors="replace")
        message = f"{Path(exc.cmd[0]).name} failed: {detail.strip() or exc}"
    except (OSError, ValueError, RuntimeError) as exc:
        message = str(exc)
    print(f"whiteboard-animate: error: {message}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
