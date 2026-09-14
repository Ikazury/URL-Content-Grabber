# Image Fetcher

A simple desktop app, built with `customtkinter`, that lets you paste an image URL, preview the image, and save it locally. Packaged to run standalone via PyInstaller.

## What it does

1. You paste an image URL into a text box.
2. The app downloads the image and displays a preview in the window.
3. You can click **Save** to write the full-resolution original image to disk via a native "Save As" dialog.

## Dependencies

| Package | Purpose |
|---|---|
| `customtkinter` | Builds the GUI — windows, buttons, input fields, styled widgets |
| `requests` | Downloads the image data from the provided URL |
| `Pillow` (PIL) | Decodes the raw downloaded bytes into an actual image and resizes it for display |
| `io` (`BytesIO`, built-in) | Wraps the raw downloaded bytes so PIL can treat them like a file |
| `sys`, `os` (built-in) | Used for locating files/resources, including inside a packaged `.exe` |

Install the third-party dependencies with:

```bash
pip install customtkinter requests Pillow
```

## How it works

### 1. Imports
The script pulls in its toolkit at the top:
- `sys` / `os` — help Python locate files and folders, including special paths used by a packaged executable.
- `customtkinter (ctk)` — draws the modern-looking window, buttons, and input boxes.
- `requests` — fetches raw data from a URL over the internet.
- `BytesIO` and `PIL.Image` — convert the raw bytes returned by `requests` into an actual displayable/savable image. `BytesIO` wraps the bytes so they behave like a file, and `PIL` decodes that "file" into an image object.

### 2. Resource Path Helper — `resource_path(relative_path)`
When the app is compiled into a `.exe` with PyInstaller, it unpacks itself into a hidden temporary folder (`_MEIPASS`) at runtime. This function checks whether the app is running as a bundled executable or as a normal script, and returns the correct path to bundled resources (like an icon) either way. Without it, the packaged `.exe` would crash trying to find its own icon.

### 3. Fetching the Image
This is the core logic:
- `url = url_entry.get()` — reads whatever URL was typed into the text box. An empty URL triggers a warning popup instead of proceeding.
- `requests.get(url)` — sends the actual HTTP request to download the image.
- `response.raise_for_status()` — raises an error immediately if the request failed (broken link, blocked request, etc.) instead of letting the app hang or silently fail.
- `Image.open(BytesIO(response.content))` — turns the raw downloaded bytes into a proper image object.
- The original (full-resolution) image is stashed on the label widget (`image_label.original_image = original_img`) so it's available later for saving.
- A resized `CTkImage` copy is created to fit neatly in the 400x400 preview area.
- The resized image is also attached to the label (`image_label.image = ctk_img`) — this is necessary because Python's garbage collector will otherwise delete the image from memory the instant the function ends, leaving a blank preview.

### 4. Saving the Image — `save_image()`
- First checks that an image has actually been fetched (`hasattr(...)`) — there's nothing to save otherwise.
- Opens the native "Save As" file dialog (`filedialog.asksaveasfilename`) so the user can choose a name and location.
- If a path was chosen, the original (unresized) image is written to disk. Cancelling the dialog simply does nothing.

### 5. Building the Interface
- `ctk.CTk()` creates the main window.
- `root.geometry("550x700")` sets its size.
- Widgets (`CTkLabel`, `CTkEntry`, `CTkButton`) are declared for the UI elements.
- `.pack(pady=...)` places each widget into the window, stacking them top-to-bottom with vertical spacing between them.
- `root.mainloop()` keeps the window open and responsive to clicks/input until it's closed.

## Notes

- Make sure to install `Pillow`, not a package literally named `pil` — `PIL` is just the import name.
- If bundling with PyInstaller, remember to include any icon/resource files alongside the `.exe` and reference them through `resource_path()`.