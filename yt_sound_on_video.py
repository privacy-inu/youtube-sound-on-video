#!/usr/bin/env python3
"""YouTube sound on your video: paste a YouTube link, pick a video, press Combine.

The link's audio is downloaded and laid over the video (replacing its sound); the new file is written
next to the video as <name>_with_sound.mp4. The picture is copied as is, so it takes seconds.

Window:   python yt_sound_on_video.py            (or double-click the exe)
Command:  python yt_sound_on_video.py <youtube link> <video file> [--offset 12.5] [--volume 100]
          [--keep 0] [--loop] [--out result.mp4] [--browser auto|chrome|edge|firefox|none]

If YouTube answers "Sign in to confirm you're not a bot", the download is retried with the YouTube
login of a browser on this PC (Firefox, Edge, Chrome, in that order; --browser picks one).

Needs: Python 3 with the yt-dlp module (pip install yt-dlp) and ffmpeg on PATH or the imageio-ffmpeg
module. The exe build carries both.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
import threading
import traceback
from pathlib import Path

BROWSERS = ("firefox", "edge", "chrome")


# ─── the work ───────────────────────────────────────────────────────────────

def ffmpeg_path() -> str:
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg  # type: ignore

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as e:  # noqa: BLE001
        raise RuntimeError("ffmpeg not found: install it (winget install Gyan.FFmpeg) or pip install imageio-ffmpeg") from e


def cookies_file() -> Path | None:
    """A `youtube_cookies.txt` (Netscape format, exported from a browser with a cookies extension)
    beside the app or in the home folder: used for every download when present."""
    here = Path(getattr(sys, "_MEIPASS", "")) if getattr(sys, "frozen", False) else Path(__file__).parent
    exe_dir = Path(sys.executable).parent if getattr(sys, "frozen", False) else here
    for folder in (exe_dir, here, Path.home(), Path.home() / "Downloads"):
        p = folder / "youtube_cookies.txt"
        if p.is_file():
            return p
    return None


def _download(link: str, into: Path, log, browser: str | None) -> Path:
    import yt_dlp  # type: ignore

    def hook(d):
        if d.get("status") == "downloading":
            log(f"downloading {d.get('_percent_str', '').strip()} {d.get('_speed_str', '').strip()}")
        elif d.get("status") == "finished":
            log("download done")

    for old in into.glob("yt_audio.*"):
        old.unlink()
    opts = {
        "format": "bestaudio/best",
        "outtmpl": str(into / "yt_audio.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [hook],
    }
    cookies = cookies_file()
    if cookies and browser is None:
        opts["cookiefile"] = str(cookies)
    elif browser:
        opts["cookiesfrombrowser"] = (browser,)
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(link, download=True)
        if info.get("title"):
            log(f"title: {info['title']}")
    files = sorted(into.glob("yt_audio.*"), key=lambda p: p.stat().st_size, reverse=True)
    if not files:
        raise RuntimeError("yt-dlp downloaded nothing")
    return files[0]


def download_audio(link: str, into: Path, log, browser: str = "auto") -> Path:
    """The best audio stream of `link`, downloaded into `into`; its path. On YouTube's "sign in to
    confirm you're not a bot" the download is retried with a browser's YouTube login."""
    first = None if browser in ("auto", "none") else browser
    try:
        return _download(link, into, log, first)
    except Exception as e:  # noqa: BLE001
        text = str(e)
        if browser != "auto" or "sign in" not in text.lower():
            raise
        log("YouTube asked for a sign-in; trying the YouTube login of a browser on this PC")
        last = e
        for name in BROWSERS:
            try:
                log(f"trying {name}")
                return _download(link, into, log, name)
            except Exception as e2:  # noqa: BLE001
                last = e2
        raise RuntimeError(
            "YouTube asked this PC to sign in (\"confirm you're not a bot\") and the app could not borrow a "
            "browser's YouTube login: Chrome and Edge keep their cookies locked while they are open. "
            "Close Chrome/Edge (every window) and press Combine again, or sign in to YouTube in Firefox, "
            "or export your YouTube cookies with a 'Get cookies.txt' browser extension to a file named "
            "youtube_cookies.txt next to this app."
        ) from last


def has_audio(ffmpeg: str, video: Path) -> bool:
    probe = shutil.which("ffprobe") or str(Path(ffmpeg).with_name("ffprobe" + Path(ffmpeg).suffix))
    if not Path(probe).exists():
        return True
    r = subprocess.run(
        [probe, "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", str(video)],
        capture_output=True,
        text=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    return bool(r.stdout.strip())


def mux(ffmpeg: str, video: Path, audio: Path, out: Path, offset: float, volume: float, keep: float, loop: bool, log) -> Path:
    """`video`'s picture + `audio` (from `offset` s, at `volume` %), the original sound kept at `keep` %;
    cut to the video's length; written to `out`."""
    cmd = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", str(video)]
    if loop:
        cmd += ["-stream_loop", "-1"]
    cmd += ["-ss", f"{max(0.0, offset):.3f}", "-i", str(audio)]
    yt_gain = max(0.0, volume) / 100.0
    keep_gain = max(0.0, keep) / 100.0
    if keep_gain > 0 and has_audio(ffmpeg, video):
        filt = (
            f"[0:a]volume={keep_gain:.3f}[orig];[1:a]volume={yt_gain:.3f}[yt];"
            f"[orig][yt]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[a]"
        )
    else:
        filt = f"[1:a]volume={yt_gain:.3f}[a]"
    cmd += ["-filter_complex", filt, "-map", "0:v:0", "-map", "[a]"]
    cmd += ["-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(out)]
    log("combining")
    r = subprocess.run(cmd, capture_output=True, text=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if r.returncode != 0:
        raise RuntimeError("ffmpeg failed:\n" + (r.stderr or "").strip()[-1500:])
    return out


def make(
    link: str,
    video: str,
    out: str | None = None,
    offset: float = 0.0,
    volume: float = 100.0,
    keep: float = 0.0,
    loop: bool = False,
    browser: str = "auto",
    log=print,
) -> Path:
    video_path = Path(video).expanduser()
    if not video_path.is_file():
        raise FileNotFoundError(f"video not found: {video_path}")
    if not link.strip():
        raise ValueError("paste a YouTube link")
    ffmpeg = ffmpeg_path()
    out_path = Path(out).expanduser() if out else video_path.with_name(video_path.stem + "_with_sound.mp4")
    with tempfile.TemporaryDirectory(prefix="ytsound_") as tmp:
        audio = download_audio(link.strip(), Path(tmp), log, browser)
        mux(ffmpeg, video_path, audio, out_path, offset, volume, keep, loop, log)
    log(f"done: {out_path}")
    return out_path


# ─── the window ─────────────────────────────────────────────────────────────

def window() -> None:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    root = tk.Tk()
    root.title("YouTube sound on your video")
    root.minsize(560, 300)
    root.resizable(True, False)

    link = tk.StringVar()
    video = tk.StringVar()
    offset = tk.StringVar(value="0")
    volume = tk.StringVar(value="100")
    keep = tk.StringVar(value="0")
    loop = tk.BooleanVar(value=False)
    status = tk.StringVar(value="1. paste the link   2. pick the video   3. Combine")

    frm = ttk.Frame(root, padding=14)
    frm.pack(fill="both", expand=True)
    frm.columnconfigure(0, weight=1)

    ttk.Label(frm, text="YouTube link", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w")
    ttk.Entry(frm, textvariable=link, font=("Segoe UI", 11)).grid(row=1, column=0, columnspan=2, sticky="ew", pady=(2, 12))

    ttk.Label(frm, text="Your video", font=("Segoe UI", 10, "bold")).grid(row=2, column=0, sticky="w")
    ttk.Entry(frm, textvariable=video, font=("Segoe UI", 11)).grid(row=3, column=0, sticky="ew", pady=(2, 12))

    def browse():
        f = filedialog.askopenfilename(
            title="Pick the video",
            filetypes=[("Video", "*.mp4 *.mov *.mkv *.webm *.avi *.m4v"), ("All files", "*.*")],
        )
        if f:
            video.set(f)

    ttk.Button(frm, text="Pick video…", command=browse).grid(row=3, column=1, sticky="ew", padx=(8, 0), pady=(2, 12))

    combine = ttk.Button(frm, text="Combine")
    combine.grid(row=4, column=0, columnspan=2, sticky="ew", ipady=6)
    bar = ttk.Progressbar(frm, mode="indeterminate")
    bar.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(10, 2))
    ttk.Label(frm, textvariable=status, wraplength=520).grid(row=6, column=0, columnspan=2, sticky="w")

    # The options, folded away.
    more = ttk.Frame(frm)
    shown = tk.BooleanVar(value=False)

    def toggle():
        if shown.get():
            more.grid_remove()
            shown.set(False)
            more_btn.configure(text="More options ▸")
        else:
            more.grid(row=8, column=0, columnspan=2, sticky="ew", pady=(6, 0))
            shown.set(True)
            more_btn.configure(text="More options ▾")

    more_btn = ttk.Button(frm, text="More options ▸", command=toggle, style="Toolbutton")
    more_btn.grid(row=7, column=0, sticky="w", pady=(10, 0))
    for c in range(4):
        more.columnconfigure(c, weight=1)
    ttk.Label(more, text="Start the sound at (seconds)").grid(row=0, column=0, sticky="w", padx=(0, 6), pady=2)
    ttk.Entry(more, textvariable=offset, width=8).grid(row=0, column=1, sticky="w", pady=2)
    ttk.Label(more, text="Sound volume (%)").grid(row=0, column=2, sticky="w", padx=(12, 6), pady=2)
    ttk.Entry(more, textvariable=volume, width=8).grid(row=0, column=3, sticky="w", pady=2)
    ttk.Label(more, text="Keep the video's own sound (%)").grid(row=1, column=0, sticky="w", padx=(0, 6), pady=2)
    ttk.Entry(more, textvariable=keep, width=8).grid(row=1, column=1, sticky="w", pady=2)
    ttk.Checkbutton(more, text="Repeat the sound if it is shorter than the video", variable=loop).grid(
        row=2, column=0, columnspan=4, sticky="w", pady=2
    )

    def say(line: str) -> None:
        root.after(0, lambda: status.set(line[:160]))

    def run():
        try:
            o = float(offset.get() or 0)
            v = float(volume.get() or 100)
            k = float(keep.get() or 0)
        except ValueError:
            messagebox.showerror("Check the options", "Start, volume and keep must be numbers.")
            return
        if not link.get().strip():
            messagebox.showerror("Missing", "Paste a YouTube link first.")
            return
        if not video.get().strip():
            messagebox.showerror("Missing", "Pick your video first.")
            return
        combine.configure(state="disabled")
        bar.start(12)
        say("starting")

        def work():
            try:
                result = make(link.get(), video.get(), None, o, v, k, loop.get(), "auto", say)
                root.after(0, lambda: messagebox.showinfo("Done", f"Saved next to your video:\n{result}"))
            except Exception as e:  # noqa: BLE001
                msg = str(e) or traceback.format_exc()
                say("error: " + msg)
                root.after(0, lambda: messagebox.showerror("Could not combine", msg[:1200]))
            finally:
                root.after(0, bar.stop)
                root.after(0, lambda: combine.configure(state="normal"))

        threading.Thread(target=work, daemon=True).start()

    combine.configure(command=run)
    root.mainloop()


# ─── entry ──────────────────────────────────────────────────────────────────

def main(argv: list[str]) -> int:
    if not argv:
        window()
        return 0
    ap = argparse.ArgumentParser(description="put a YouTube link's sound on your video")
    ap.add_argument("link")
    ap.add_argument("video")
    ap.add_argument("--offset", type=float, default=0.0)
    ap.add_argument("--volume", type=float, default=100.0)
    ap.add_argument("--keep", type=float, default=0.0)
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--out", default=None)
    ap.add_argument("--browser", default="auto", choices=["auto", "none", *BROWSERS])
    a = ap.parse_args(argv)
    try:
        make(a.link, a.video, a.out, a.offset, a.volume, a.keep, a.loop, a.browser)
    except Exception as e:  # noqa: BLE001
        print("error:", e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
