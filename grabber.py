import sys
import os
import customtkinter as ctk
from tkinter import messagebox, filedialog
import requests
from io import BytesIO
from PIL import Image

def resource_path(relative_path):
    """ EXE manifestation for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# --- Set the Modern Theme ---
ctk.set_appearance_mode("Dark")  # Options: "System" (standard), "Dark", "Light"
ctk.set_default_color_theme("blue")  # Options: "blue", "green", "dark-blue"

def fetch_image():
    url = url_entry.get()
    
    if not url:
        messagebox.showwarning("Hold your finger", "You need to give me a URL first")
        return

    try:
        response = requests.get(url)
        response.raise_for_status()

        # Capture the pristine beast
        original_img = Image.open(BytesIO(response.content))
        image_label.original_image = original_img

        # CustomTkinter handles the resizing for us beautifully!
        # We just tell it what size we want the UI element to be.
        ctk_img = ctk.CTkImage(light_image=original_img, size=(400, 400))

        image_label.configure(image=ctk_img, text="") # Clear the placeholder text
        image_label.image = ctk_img 
        
        # Unhide the save button
        save_btn.pack(pady=10)

    except requests.exceptions.RequestException as e:
        messagebox.showerror("upsies", f"Couldn't reach the image! The web says: {e}")
    except Exception as e:
        messagebox.showerror("for god sake...", f"Something went horribly wrong: {e}")

def save_image():
    if not hasattr(image_label, 'original_image'):
        messagebox.showerror("What???", "Give the link first for me to show you...")
        return

    file_path = filedialog.asksaveasfilename(
        defaultextension=".png",
        filetypes=[("PNG files", "*.png"), ("JPEG files", "*.jpg"), ("All files", "*.*")],
        title="Where this will be put?"
    )

    if file_path:
        try:
            image_label.original_image.save(file_path)
            messagebox.showinfo("Success!", "The deed is done. Your image is saved.")
        except Exception as e:
            messagebox.showerror("A disaster!", f"Failed to save it! The runes read: {e}")

# --- Building the Modern UI ---

# Notice we use ctk.CTk() now instead of tk.Tk()
root = ctk.CTk()
root.title("Image Skecer")
root.geometry("550x700")
root.iconbitmap(resource_path("sil.ico")) 

# The instructions (Now with CTkLabel)
instruction = ctk.CTkLabel(root, text="Drop The Link Below:", font=("Helvetica", 16))
instruction.pack(pady=(20, 10))

# The text box (Now a sleek CTkEntry)
url_entry = ctk.CTkEntry(root, width=450, font=("Helvetica", 12), placeholder_text="Paste your URL here...")
url_entry.pack(pady=10)

# The button (A gorgeous CTkButton with rounded corners!)
fetch_btn = ctk.CTkButton(root, text="Grab image", command=fetch_image, font=("Helvetica", 14, "bold"), corner_radius=8)
fetch_btn.pack(pady=15)

# The empty frame (CTkLabel can also hold images)
image_label = ctk.CTkLabel(root, text="[ Your image will appear here ]", width=400, height=400, fg_color=("gray75", "gray25"), corner_radius=10)
image_label.pack(pady=10)

# The save button (Hidden until needed)
save_btn = ctk.CTkButton(root, text="Save the image", command=save_image, font=("Helvetica", 14, "bold"), fg_color="#28a745", hover_color="#218838", corner_radius=8)

root.mainloop()