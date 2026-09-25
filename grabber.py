import sys
import os
import customtkinter as ctk
from tkinter import messagebox, filedialog
import requests
from io import BytesIO
from PIL import Image
import threading  # Our background worker magic!

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# Holds whatever info we need to actually perform the download once the
# user confirms via the "Download Video" button.
pending_video = {
    "kind": None,   # "direct" or "social"
    "url": None,
}


def fetch_media():
    url = url_entry.get()

    if not url:
        messagebox.showwarning("Hold Your finger!", "I need the URL!")
        return

    # Reset any previous pending video and hide video-related buttons
    pending_video["kind"] = None
    pending_video["url"] = None
    download_video_btn.pack_forget()
    save_btn.pack_forget()

    try:
        # A HEAD request is enough to learn the content type without
        # pulling the whole file down.
        response = requests.head(url, allow_redirects=True, timeout=10)
        content_type = response.headers.get('Content-Type', '')

        if 'image' in content_type:
            # It's an image! Fetch it fully now since images are small
            # and we want to show it anyway.
            img_response = requests.get(url, timeout=15)
            img_response.raise_for_status()
            original_img = Image.open(BytesIO(img_response.content))
            image_label.original_image = original_img

            ctk_img = ctk.CTkImage(light_image=original_img, size=(400, 400))
            image_label.configure(image=ctk_img, text="")
            image_label.image = ctk_img

            save_btn.pack(pady=10)  # Show the save button

        elif 'video' in content_type:
            # It's a direct video file. Show a preview card with what we
            # know about it, but DON'T download until the user asks.
            content_length = response.headers.get('Content-Length')
            size_txt = f"{int(content_length) / (1024 * 1024):.1f} MB" if content_length else "unknown size"

            image_label.configure(
                image="",
                text=f"🎬 Direct video file found\n\nType: {content_type}\nSize: {size_txt}\n\nClick 'Download Video' to save it."
            )
            pending_video["kind"] = "direct"
            pending_video["url"] = url
            download_video_btn.pack(pady=10)

        else:
            # It's neither a raw image nor a raw video file. That usually means
            # it's a webpage (X/Twitter, Instagram, TikTok, YouTube, etc.) with
            # a video embedded inside it. Ask yt-dlp for a PREVIEW first.
            preview_social_media_link(url)

    except requests.exceptions.RequestException as e:
        messagebox.showerror("Blast it!", f"Couldn't reach the link! The web says: {e}")
    except Exception as e:
        messagebox.showerror("Well, that's gone pear-shaped", f"Error: {e}")


def preview_social_media_link(url):
    """ Asks yt-dlp for the video's metadata/thumbnail WITHOUT downloading
    it, then shows that as a preview. The actual file only gets pulled
    down when the user clicks 'Download Video'. """
    try:
        import yt_dlp
    except ImportError:
        messagebox.showerror(
            "Missing piece!",
            "This link needs the 'yt-dlp' package to grab the video.\n\n"
            "Install it with:\n    pip install yt-dlp"
        )
        return

    image_label.configure(image="", text="Loading preview...")
    root.update()

    threading.Thread(target=_fetch_social_preview, args=(url,)).start()


def _fetch_social_preview(url):
    import yt_dlp

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,  # <-- the key bit: metadata only, no file
        'noplaylist': True,     # don't resolve an entire playlist by accident
        'socket_timeout': 15,   # don't hang forever on a stalled connection
        'extractor_retries': 1,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if 'entries' in info:
                # Some URLs (e.g. a playlist link) resolve to a list even
                # with noplaylist; just take the first real video.
                info = info['entries'][0]

        title = info.get('title', 'Untitled')
        duration = info.get('duration')
        duration_txt = f"{int(duration // 60)}:{int(duration % 60):02d}" if duration else "unknown"
        thumbnail_url = info.get('thumbnail')

        thumb_img = None
        if thumbnail_url:
            try:
                thumb_resp = requests.get(thumbnail_url, timeout=10)
                thumb_resp.raise_for_status()
                thumb_img = Image.open(BytesIO(thumb_resp.content))
            except Exception:
                thumb_img = None  # fall back to text-only preview

        # Hand off to the main thread to actually touch the UI
        root.after(0, lambda: _show_social_preview(url, title, duration_txt, thumb_img))

    except Exception as e:
        err_msg = str(e)
        print(f"[yt-dlp preview error] {err_msg}")  # check your terminal for the full trace
        root.after(0, lambda: image_label.configure(text=f"Couldn't load preview!\n{err_msg[:200]}"))


def _show_social_preview(url, title, duration_txt, thumb_img):
    if thumb_img is not None:
        ctk_img = ctk.CTkImage(light_image=thumb_img, size=(400, 225))
        image_label.configure(image=ctk_img, text=f"{title}\nDuration: {duration_txt}", compound="top")
        image_label.image = ctk_img
    else:
        image_label.configure(image="", text=f"🎬 {title}\nDuration: {duration_txt}\n\n(No thumbnail available)")

    pending_video["kind"] = "social"
    pending_video["url"] = url
    download_video_btn.pack(pady=10)


def start_video_download():
    """ Triggered by the 'Download Video' button, once the user has seen
    the preview and actually wants the file. """
    if not pending_video["kind"]:
        return

    file_path = filedialog.asksaveasfilename(
        defaultextension=".mp4",
        filetypes=[("MP4 Video", "*.mp4"), ("All files", "*.*")],
        title="Where to save the file?"
    )

    if not file_path:
        return

    image_label.configure(text="Downloading Video... Please wait.")
    download_video_btn.configure(state="disabled")

    if pending_video["kind"] == "direct":
        threading.Thread(target=download_direct_video, args=(pending_video["url"], file_path)).start()
    else:
        threading.Thread(target=download_social_video, args=(pending_video["url"], file_path)).start()


def download_direct_video(url, file_path):
    """ Streams a direct video URL to disk in the background. """
    try:
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        image_label.configure(text="Video Download Complete! Check your folder.")
    except Exception as e:
        image_label.configure(text=f"Download failed! {e}")
    finally:
        download_video_btn.configure(state="normal")


def download_social_video(url, file_path):
    """ Runs in the background: asks yt-dlp to find and download the real
    video file from a social media page, then saves it to file_path. """
    import yt_dlp

    base, ext = os.path.splitext(file_path)
    outtmpl = base + ".%(ext)s"

    ydl_opts = {
        'outtmpl': outtmpl,
        'format': 'bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/best',
        'merge_output_format': 'mp4',
        'quiet': True,
        'no_warnings': True,
        'noprogress': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            downloaded_path = ydl.prepare_filename(info)
            if ydl_opts.get('merge_output_format'):
                merged = base + "." + ydl_opts['merge_output_format']
                if os.path.exists(merged):
                    downloaded_path = merged

        if os.path.exists(downloaded_path) and downloaded_path != file_path:
            if os.path.exists(file_path):
                os.remove(file_path)
            os.rename(downloaded_path, file_path)

        image_label.configure(text="Video Download Complete! Check your folder.")
    except Exception as e:
        image_label.configure(text=f"Download failed! {e}")
    finally:
        download_video_btn.configure(state="normal")


def save_image():
    if not hasattr(image_label, 'original_image'):
        return

    file_path = filedialog.asksaveasfilename(
        defaultextension=".png",
        filetypes=[("PNG files", "*.png"), ("JPEG files", "*.jpg"), ("All files", "*.*")],
        title="Where to save the pic?"
    )

    if file_path:
        try:
            image_label.original_image.save(file_path)
            messagebox.showinfo("Success!", "Image has been saved.")
        except Exception as e:
            messagebox.showerror("A disaster!", f"Failed to save it! {e}")

# --- Building the UI ---

root = ctk.CTk()
root.title("URL Content Grabber")
root.geometry("550x700")
root.iconbitmap(resource_path("sil.ico"))  # Make sure you put quotes around your filename with spaces!

instruction = ctk.CTkLabel(root, text="Paste the URL below:", font=("Helvetica", 16))
instruction.pack(pady=(20, 10))

url_entry = ctk.CTkEntry(root, width=450, font=("Helvetica", 12), placeholder_text="Paste your direct URL here...")
url_entry.pack(pady=10)

fetch_btn = ctk.CTkButton(root, text="Fetch Media!", command=fetch_media, font=("Helvetica", 14, "bold"), corner_radius=8)
fetch_btn.pack(pady=15)

image_label = ctk.CTkLabel(root, text="[ Your media will appear here ]", width=400, height=400, fg_color=("gray75", "gray25"), corner_radius=10)
image_label.pack(pady=10)

save_btn = ctk.CTkButton(root, text="Save!", command=save_image, font=("Helvetica", 14, "bold"), fg_color="#28a745", hover_color="#218838", corner_radius=8)

download_video_btn = ctk.CTkButton(root, text="Download Video", command=start_video_download, font=("Helvetica", 14, "bold"), fg_color="#28a745", hover_color="#218838", corner_radius=8)

root.mainloop()