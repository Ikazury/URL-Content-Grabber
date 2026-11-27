import sys
import os
import threading
from io import BytesIO
from typing import Any

import customtkinter as ctk
from tkinter import TclError, filedialog, messagebox
import requests
from PIL import Image

HEADERS = {"User-Agent": "Mozilla/5.0"}
PREVIEW_W, PREVIEW_H = 400, 400


def resource_path(relative_path):
    """Works both in normal Python and inside a PyInstaller exe."""
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# Info needed to perform the download once the user confirms.
pending_video: dict[str, str | None] = {"kind": None, "url": None}  # kind: "direct" or "social"


# ---------------------------------------------------------------------------
# Thread-safe UI helpers (tkinter must only be touched from the main thread)
# ---------------------------------------------------------------------------
def ui(fn):
    """Run fn on the main thread."""
    try:
        root.after(0, fn)
    except RuntimeError:
        pass  # window already closed


def set_status(text, image=None):
    def _do():
        image_label.configure(image=image, text=text, compound="top")
        image_label.image = image
    ui(_do)


def set_download_btn_state(state):
    ui(lambda: download_video_btn.configure(state=state))


def set_fetch_btn_state(state):
    ui(lambda: fetch_btn.configure(state=state))


def show_error(title, msg):
    ui(lambda: messagebox.showerror(title, msg))


def fit_size(w, h, max_w=PREVIEW_W, max_h=PREVIEW_H):
    scale = min(max_w / w, max_h / h)
    return max(1, int(w * scale)), max(1, int(h * scale))


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------
def fetch_media():
    url = url_entry.get().strip()

    if not url:
        messagebox.showwarning("Hold your horses!", "I need the URL!")
        return

    # Reset previous state and hide action buttons
    pending_video["kind"] = None
    pending_video["url"] = None
    download_video_btn.pack_forget()
    save_btn.pack_forget()
    if hasattr(image_label, "original_image"):
        del image_label.original_image

    set_status("Looking at the link...")
    fetch_btn.configure(state="disabled")

    threading.Thread(target=_fetch_worker, args=(url,), daemon=True).start()


def _fetch_worker(url):
    try:
        # HEAD is cheap, but plenty of servers reject it -> fall back to GET.
        response = requests.head(url, allow_redirects=True, timeout=10, headers=HEADERS)
        if response.status_code >= 400 or not response.headers.get("Content-Type"):
            response = requests.get(url, allow_redirects=True, stream=True,
                                    timeout=10, headers=HEADERS)
            response.close()

        content_type = response.headers.get("Content-Type", "").lower()

        if "image" in content_type:
            img_response = requests.get(url, timeout=20, headers=HEADERS)
            img_response.raise_for_status()
            original_img = Image.open(BytesIO(img_response.content))
            original_img.load()
            ui(lambda: _show_image(original_img))

        elif "video" in content_type:
            length = response.headers.get("Content-Length")
            size_txt = f"{int(length) / (1024 * 1024):.1f} MB" if length else "unknown size"
            pending_video["kind"] = "direct"
            pending_video["url"] = url
            set_status(
                f"🎬 Direct video file found\n\nType: {content_type}\n"
                f"Size: {size_txt}\n\nClick 'Download Video' to save it."
            )
            ui(lambda: download_video_btn.pack(pady=10))

        else:
            # Probably a webpage with an embedded video (X, Instagram, TikTok, YouTube...)
            _fetch_social_preview(url)
            return  # _fetch_social_preview re-enables the fetch button

    except requests.exceptions.RequestException as e:
        show_error("Blast it!", f"Couldn't reach the link! The web says: {e}")
        set_status("[ Your media will appear here ]")
    except Exception as e:  # noqa: BLE001 - last-resort UI boundary
        show_error("Well, that's gone pear-shaped", f"Error: {e}")
        set_status("[ Your media will appear here ]")

    set_fetch_btn_state("normal")


def _show_image(original_img):
    image_label.original_image = original_img
    size = fit_size(*original_img.size)
    ctk_img = ctk.CTkImage(light_image=original_img, size=size)
    image_label.configure(image=ctk_img, text="")
    image_label.image = ctk_img
    save_btn.pack(pady=10)


def _fetch_social_preview(url):
    """Runs in a worker thread: asks yt-dlp for metadata only (no download)."""
    try:
        import yt_dlp
    except ImportError:
        show_error(
            "Missing piece!",
            "This link needs the 'yt-dlp' package.\n\nInstall it with:\n    pip install yt-dlp",
        )
        set_status("[ Your media will appear here ]")
        set_fetch_btn_state("normal")
        return

    ydl_opts: Any = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "socket_timeout": 15,
        "extractor_retries": 1,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        if info.get("entries") is not None:
            entries = [e for e in (info.get("entries") or []) if e]
            if not entries:
                raise ValueError("No video found at that link")
            info = entries[0]

        title = info.get("title") or "Untitled"
        duration = info.get("duration")
        duration_txt = (
            f"{int(duration // 60)}:{int(duration % 60):02d}" if duration else "unknown"
        )

        thumb_img = None
        thumbnail_url = info.get("thumbnail")
        if thumbnail_url:
            try:
                r = requests.get(thumbnail_url, timeout=10, headers=HEADERS)
                r.raise_for_status()
                thumb_img = Image.open(BytesIO(r.content))
                thumb_img.load()
            except (requests.RequestException, OSError):
                thumb_img = None

        ui(lambda: _show_social_preview(url, title, duration_txt, thumb_img))

    except Exception as e:  # noqa: BLE001 - yt-dlp can raise many types
        err_msg = str(e)
        print(f"[yt-dlp preview error] {err_msg}")
        set_status(f"Couldn't load preview!\n{err_msg[:200]}")

    set_fetch_btn_state("normal")


def _show_social_preview(url, title, duration_txt, thumb_img):
    if thumb_img is not None:
        size = fit_size(*thumb_img.size, max_w=PREVIEW_W, max_h=PREVIEW_H - 60)
        ctk_img = ctk.CTkImage(light_image=thumb_img, size=size)
        image_label.configure(image=ctk_img, text=f"{title}\nDuration: {duration_txt}",
                              compound="top")
        image_label.image = ctk_img
    else:
        image_label.configure(
            image=None,
            text=f"🎬 {title}\nDuration: {duration_txt}\n\n(No thumbnail available)",
        )
        image_label.image = None

    pending_video["kind"] = "social"
    pending_video["url"] = url
    download_video_btn.pack(pady=10)


# ---------------------------------------------------------------------------
# Downloading
# ---------------------------------------------------------------------------
def start_video_download():
    if not pending_video["kind"]:
        return

    file_path = filedialog.asksaveasfilename(
        defaultextension=".mp4",
        filetypes=[("MP4 Video", "*.mp4"), ("All files", "*.*")],
        title="Where to save the file?",
    )
    if not file_path:
        return

    set_status("Downloading video... Please wait.")
    download_video_btn.configure(state="disabled")

    target = download_direct_video if pending_video["kind"] == "direct" else download_social_video
    threading.Thread(target=target, args=(pending_video["url"], file_path), daemon=True).start()


def download_direct_video(url, file_path):
    try:
        with requests.get(url, stream=True, timeout=30, headers=HEADERS) as response:
            response.raise_for_status()
            with open(file_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
        set_status("Video download complete! Check your folder.")
    except (requests.RequestException, OSError) as e:
        set_status(f"Download failed!\n{str(e)[:200]}")
    finally:
        set_download_btn_state("normal")


def download_social_video(url, file_path):
    try:
        import yt_dlp
    except ImportError:
        set_status("yt-dlp is not installed.")
        set_download_btn_state("normal")
        return

    base, _ = os.path.splitext(file_path)

    ydl_opts: Any = {
        "outtmpl": base + ".%(ext)s",
        # Single-file mp4 first (no ffmpeg needed), then merge, then anything.
        "format": "b[ext=mp4]/bv*[ext=mp4]+ba[ext=m4a]/bv*+ba/best",
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
    }

    # Use a bundled ffmpeg if one was shipped with the exe.
    bundled_ffmpeg = resource_path("ffmpeg.exe")
    if os.path.exists(bundled_ffmpeg):
        ydl_opts["ffmpeg_location"] = os.path.dirname(bundled_ffmpeg)

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            entries = info.get("entries")
            if entries:
                first = next((e for e in entries if e), None)
                if first is not None:
                    info = first

            downloaded_path = None
            requested = info.get("requested_downloads")
            if requested:
                downloaded_path = requested[0].get("filepath")
            if not downloaded_path:
                downloaded_path = ydl.prepare_filename(info)

        merged = base + ".mp4"
        if not (downloaded_path and os.path.exists(downloaded_path)) and os.path.exists(merged):
            downloaded_path = merged

        if (
            downloaded_path
            and os.path.exists(downloaded_path)
            and os.path.abspath(downloaded_path) != os.path.abspath(file_path)
        ):
            os.replace(downloaded_path, file_path)  # overwrites if it already exists

        set_status("Video download complete! Check your folder.")
    except Exception as e:  # noqa: BLE001 - yt-dlp can raise many types
        set_status(f"Download failed!\n{str(e)[:200]}")
    finally:
        set_download_btn_state("normal")


def save_image():
    img = getattr(image_label, "original_image", None)
    if img is None:
        return

    file_path = filedialog.asksaveasfilename(
        defaultextension=".png",
        filetypes=[("PNG files", "*.png"), ("JPEG files", "*.jpg"), ("All files", "*.*")],
        title="Where to save the pic?",
    )
    if not file_path:
        return

    try:
        if file_path.lower().endswith((".jpg", ".jpeg")) and img.mode not in ("RGB", "L"):
            img = img.convert("RGB")  # JPEG can't store transparency
        img.save(file_path)
        messagebox.showinfo("Success!", "Image has been saved.")
    except (OSError, ValueError) as e:
        messagebox.showerror("A disaster!", f"Failed to save it! {e}")


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------
root = ctk.CTk()
root.title("URL Content Grabber")
root.geometry("550x700")


def set_icon():
    try:
        root.iconbitmap(resource_path("sil.ico"))
    except TclError as e:
        print(f"[icon] could not load sil.ico: {e}")  # never crash over an icon


# CTk applies its own default icon shortly after startup; set ours after that.
root.after(250, set_icon)

instruction = ctk.CTkLabel(root, text="Paste the URL below:", font=("Helvetica", 16))
instruction.pack(pady=(20, 10))

url_entry = ctk.CTkEntry(root, width=450, font=("Helvetica", 12),
                         placeholder_text="Paste your direct URL here...")
url_entry.pack(pady=10)
url_entry.bind("<Return>", lambda e: fetch_media())

fetch_btn = ctk.CTkButton(root, text="Fetch Media!", command=fetch_media,
                          font=("Helvetica", 14, "bold"), corner_radius=8)
fetch_btn.pack(pady=15)

image_label = ctk.CTkLabel(root, text="[ Your media will appear here ]",
                           width=PREVIEW_W, height=PREVIEW_H,
                           fg_color=("gray75", "gray25"), corner_radius=10,
                           wraplength=PREVIEW_W - 20)
image_label.pack(pady=10)

save_btn = ctk.CTkButton(root, text="Save!", command=save_image,
                         font=("Helvetica", 14, "bold"),
                         fg_color="#28a745", hover_color="#218838", corner_radius=8)

download_video_btn = ctk.CTkButton(root, text="Download Video", command=start_video_download,
                                   font=("Helvetica", 14, "bold"),
                                   fg_color="#28a745", hover_color="#218838", corner_radius=8)

root.mainloop()
