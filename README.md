# YouTube Sound On Video

Put the sound of any YouTube video onto a video file of your own, in one window:
paste the YouTube link, pick your video, press **Combine**. You get a new MP4 next to
your video with your picture and the YouTube audio.

## Download (Windows)

Grab `YouTubeSoundOnVideo.exe` from the [Releases](../../releases) page and run it.
Nothing to install: the downloader (yt-dlp) and the encoder (ffmpeg) are inside the exe.

Windows SmartScreen may warn once because the exe is not code-signed: click
**More info → Run anyway**.

## How to use

1. Paste the YouTube link.
2. **Pick video…** and choose your clip (mp4, mov, mkv, webm, avi…).
3. Press **Combine**. The result lands beside your video as `<name>_ytsound.mp4`.

**More options** (folded by default):

| Option | What it does |
|---|---|
| Start offset (s) | Start the YouTube audio this many seconds in |
| Volume (%) | Loudness of the YouTube audio |
| Keep original sound (%) | Mix this much of your video's own sound back in (0 = replace it) |
| Repeat the sound | Loop the audio when it is shorter than the video |

The output is cut to the length of your video.

## If YouTube says "Sign in to confirm you're not a bot"

YouTube sometimes blocks downloads from a new machine. The app then tries to read
your browser's YouTube cookies (Firefox, then Edge, then Chrome; Chrome and Edge lock
their cookies while they are open, so close them first). If that is not enough, export
your YouTube cookies with a browser extension such as "Get cookies.txt LOCALLY" and
save the file as `youtube_cookies.txt` next to the exe (or in your Downloads folder).

## Command line

```
yt_sound_on_video.py <youtube link> <video> [--offset 0] [--volume 100] [--keep 0] [--loop] [--out file.mp4] [--browser auto|none|firefox|edge|chrome]
```

## Run from source

```
pip install -r requirements.txt
python yt_sound_on_video.py
```

Needs Python 3.11+. ffmpeg is found on PATH, or from the `imageio-ffmpeg` package.

## Build the exe

```
pip install pyinstaller yt-dlp imageio-ffmpeg
pyinstaller --onefile --windowed --name YouTubeSoundOnVideo --collect-all yt_dlp --collect-all imageio_ffmpeg yt_sound_on_video.py
```

The exe appears in `dist/`.

## Notes

- Only download what you have the right to use; this tool is for your own videos and
  audio you are allowed to use.
- Built on [yt-dlp](https://github.com/yt-dlp/yt-dlp) and [ffmpeg](https://ffmpeg.org/).

MIT licence.
