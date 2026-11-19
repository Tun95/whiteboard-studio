"""Start Whiteboard Wave Studio: python run_studio.py

The packaged Windows app uses this same file. It also acts as the animator when the app calls itself
with --run-animator (a packaged .exe cannot use "python -m").
"""
import sys

def _use_bundled_ffmpeg():
    """In the packaged app, ffmpeg.exe and ffprobe.exe sit in an 'ffmpeg' folder next to the app."""
    if getattr(sys, "frozen", False):
        import os
        folder = os.path.join(os.path.dirname(sys.executable), "ffmpeg")
        if os.path.isdir(folder):
            os.environ["PATH"] = folder + os.pathsep + os.environ.get("PATH", "")

if __name__ == "__main__":
    _use_bundled_ffmpeg()
    if len(sys.argv) > 1 and sys.argv[1] == "--run-animator":
        from whiteboard_animator.cli import main
        sys.exit(main(sys.argv[2:]))
    if len(sys.argv) > 1 and sys.argv[1] in ("--run-manhwa", "--run-ad"):
        import runpy
        mod = "manhwa_panels" if sys.argv[1] == "--run-manhwa" else "app_ad"
        sys.argv = [mod + ".py", *sys.argv[2:]]
        runpy.run_module(mod, run_name="__main__")
        sys.exit(0)
    from studio.server import serve
    serve(open_browser="--no-browser" not in sys.argv)
