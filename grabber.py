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

def fetch_media():
    url = url_entry.get()
    
    if not url:
        messagebox.showwarning("Hold Your finger!", "I need the URL!")
        return

    try:
        # stream=True tells Python: "Only grab the header information for now, don't download the file yet!"
        response = requests.get(url, stream=True)
        response.raise_for_status()

        # Read the shipping label to see what we caught
        content_type = response.headers.get('Content-Type', '')

        if 'image' in content_type:
            # It's an image! Proceed as normal.
            original_img = Image.open(BytesIO(response.content))
            image_label.original_image = original_img

            ctk_img = ctk.CTkImage(light_image=original_img, size=(400, 400))
            image_label.configure(image=ctk_img, text="") 
            image_label.image = ctk_img 
            
            save_btn.pack(pady=10) # Show the save button

        elif 'video' in content_type:
            # It's a video! We won't try to display it.
            image_label.configure(image="", text="Video... Ready to download.")
            save_btn.pack_forget() # Hide the save button since we are saving immediately
            
            # Ask where to save it right now
            file_path = filedialog.asksaveasfilename(
                defaultextension=".mp4",
                filetypes=[("MP4 Video", "*.mp4"), ("All files", "*.*")],
                title="Where to save the file?"
            )
            
            if file_path:
                image_label.configure(text="Downloading Video... Please wait.")
                root.update() # Force the UI to refresh its text
                
                # Summon a background thread to do the heavy lifting!
                threading.Thread(target=download_video, args=(response, file_path)).start()
            else:
                image_label.configure(text="Video download cancelled.")

        else:
            # It's neither a raw image nor a raw video file. That usually means
            # it's a webpage (X/Twitter, Instagram, TikTok, YouTube, etc.) with
            # a video embedded inside it. Let yt-dlp dig it out instead.
            response.close()  # We don't need this half-open connection anymore
            handle_social_media_link(url)

    except requests.exceptions.RequestException as e:
        messagebox.showerror("Blast it!", f"Couldn't reach the link! The web says: {e}")
    except Exception as e:
        messagebox.showerror("Well, that's gone pear-shaped", f"Error: {e}")

def handle_social_media_link(url):
    """ Handles pages like X/Twitter, Instagram, TikTok, YouTube etc. that
    wrap a video inside HTML instead of serving it directly. """
    try:
        import yt_dlp
    except ImportError:
        messagebox.showerror(
            "Missing piece!",
            "This link needs the 'yt-dlp' package to grab the video.\n\n"
            "Install it with:\n    pip install yt-dlp"
        )
        return

    image_label.configure(image="", text="Video... Ready to download.")
    save_btn.pack_forget()  # Hide the save button since we are saving immediately

    file_path = filedialog.asksaveasfilename(
        defaultextension=".mp4",
        filetypes=[("MP4 Video", "*.mp4"), ("All files", "*.*")],
        title="Where to save the file?"
    )

    if file_path:
        image_label.configure(text="Downloading Video... Please wait.")
        root.update()  # Force the UI to refresh its text

        # Summon a background thread to do the heavy lifting!
        threading.Thread(target=download_social_video, args=(url, file_path)).start()
    else:
        image_label.configure(text="Video download cancelled.")

def download_social_video(url, file_path):
    """ Runs in the background: asks yt-dlp to find and download the real
    video file from a social media page, then saves it to file_path. """
    import yt_dlp

    base, ext = os.path.splitext(file_path)
    # Let yt-dlp pick the right extension for whatever format it grabs,
    # then we'll rename the result to match what the user chose.
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
            # If merging happened, the real file often ends in .mp4 already
            if ydl_opts.get('merge_output_format'):
                merged = base + "." + ydl_opts['merge_output_format']
                if os.path.exists(merged):
                    downloaded_path = merged

        # Make sure the final file sits exactly where the user asked for it
        if os.path.exists(downloaded_path) and downloaded_path != file_path:
            if os.path.exists(file_path):
                os.remove(file_path)
            os.rename(downloaded_path, file_path)

        # When it's done, the download is done!
        image_label.configure(text="Video Download Complete! Check your folder.")
    except Exception as e:
        image_label.configure(text=f"Download failed! {e}")

def download_video(response, file_path):
    """ This function runs entirely in the background so the UI doesn't freeze """
    try:
        # Open the vault and stream the video chunk by chunk (8KB at a time)
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        # When the loop finishes, the download is done!
        image_label.configure(text="Video Download Complete! Check your folder.")
    except Exception as e:
        image_label.configure(text=f"Download failed! {e}")

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
root.iconbitmap(resource_path("sil.ico")) # Make sure you put quotes around your filename with spaces!

instruction = ctk.CTkLabel(root, text="Paste the URL below:", font=("Helvetica", 16))
instruction.pack(pady=(20, 10))

url_entry = ctk.CTkEntry(root, width=450, font=("Helvetica", 12), placeholder_text="Paste your direct URL here...")
url_entry.pack(pady=10)

fetch_btn = ctk.CTkButton(root, text="Fetch Media!", command=fetch_media, font=("Helvetica", 14, "bold"), corner_radius=8)
fetch_btn.pack(pady=15)

image_label = ctk.CTkLabel(root, text="[ Your media will appear here ]", width=400, height=400, fg_color=("gray75", "gray25"), corner_radius=10)
image_label.pack(pady=10)

save_btn = ctk.CTkButton(root, text="Save!", command=save_image, font=("Helvetica", 14, "bold"), fg_color="#28a745", hover_color="#218838", corner_radius=8)

root.mainloop()