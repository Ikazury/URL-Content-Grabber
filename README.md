# URL Content Grabber

A simple desktop app (built with `customtkinter`) that grabs media from a pasted URL — images, direct video files, and now videos from social media pages like X (Twitter), Instagram, TikTok, and YouTube.

## Features

- **Direct image links** — preview the image in the app, then save it as PNG/JPEG wherever you like.
- **Direct video links** — downloads the video file straight to disk with a progress-free "please wait" status (streamed in chunks so the UI never freezes).
- **Social media links (new)** — paste a page URL from X, Instagram, TikTok, YouTube, etc., and the app will extract and download the actual video behind the page, saving it as an MP4.
- Runs downloads on a background thread, so the window stays responsive while a file is being saved.

## How it works

1. Paste a URL into the box and click **Fetch Media!**
2. The app checks what kind of content the link actually points to:
   - `image/...` → shown in the preview box, with a **Save!** button.
   - `video/...` → straight to a save dialog, then downloaded in the background.
   - Anything else (typically an HTML page, which is what social media links are) → handed off to `yt-dlp`, which finds the real video and downloads it the same way.
3. Once finished, the status text updates to let you know the file is ready.

## Requirements

Install dependencies with:

```bash
pip install -r requirements.txt
```

This includes:

- `customtkinter` — the UI framework
- `requests` — for fetching direct media links
- `Pillow` — for handling/previewing images
- `yt-dlp` — for extracting videos from social media/webpage links

## Running

```bash
python grabber.py
```

Make sure `sil.ico` (the app icon) is in the same folder as the script, or bundled alongside it if you're packaging with PyInstaller — the app looks for it via `resource_path()`.

## Notes on social media links

- Some content (private accounts, age-restricted videos, etc.) requires being logged in. `yt-dlp` supports passing browser cookies for these cases — this isn't wired into the app yet, but can be added if you run into it.
- Supported sites are whatever `yt-dlp` supports, which covers most major platforms (X/Twitter, Instagram, TikTok, YouTube, Facebook, Reddit, and hundreds more). Some platforms occasionally break extraction when they change their internal APIs — keeping `yt-dlp` updated (`pip install -U yt-dlp`) usually fixes this.

## Packaging (optional)

If you bundle this with PyInstaller, make sure to include the icon file, e.g.:

```bash
pyinstaller --onefile --icon=sil.ico --add-data "sil.ico;." grabber.py
```

(On macOS/Linux, replace the `;` in `--add-data` with `:`.)

## Credits

This app is built on top of the following open-source projects — full credit to their authors and contributors:

- **[yt-dlp](https://github.com/yt-dlp/yt-dlp)** — does all the heavy lifting for extracting and downloading videos from social media and other websites. Licensed under [Unlicense](https://github.com/yt-dlp/yt-dlp/blob/master/LICENSE).
- **[CustomTkinter](https://github.com/TomSchimansky/CustomTkinter)** by Tom Schimansky — the modern-looking UI framework used for the whole interface. Licensed under [MIT](https://github.com/TomSchimansky/CustomTkinter/blob/master/LICENSE).
- **[Requests](https://github.com/psf/requests)** — handles HTTP requests for direct image/video links. Licensed under [Apache 2.0](https://github.com/psf/requests/blob/main/LICENSE).
- **[Pillow](https://github.com/python-pillow/Pillow)** — image loading, previewing, and saving. Licensed under the [MIT-CMU license](https://github.com/python-pillow/Pillow/blob/main/LICENSE).

If you redistribute this app (especially as a packaged .exe), it's good practice to keep this credits section or a similar notice, since these projects' licenses generally require attribution to be preserved.