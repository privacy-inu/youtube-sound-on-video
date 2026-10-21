# Builds dist\YouTubeSoundOnVideo.exe (Windows). Run from this folder.
python -m pip install --upgrade pyinstaller yt-dlp imageio-ffmpeg
python -m PyInstaller --onefile --windowed --name YouTubeSoundOnVideo --collect-all yt_dlp --collect-all imageio_ffmpeg yt_sound_on_video.py
