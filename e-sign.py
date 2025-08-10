import sys, os
import fitz  # PyMuPDF
from PIL import Image, ImageTk
import tkinter as tk

# -------- CONFIG --------
SIGN_IMAGE_PATH = "sign.jpg"   # your signature file
SIG_WIDTH_PT = 100             # signature width in PDF points (1 pt ≈ 1/72 inch)
DISPLAY_ZOOM = 1.5             # render scale for preview; higher = larger image
TITLE = "Scroll & Click: place the signature (mouse wheel to scroll, click to place)"
# ------------------------

if len(sys.argv) < 3:
    print("Usage: python stamp_signature_scroll.py input.pdf output.pdf")
    sys.exit(1)

in_pdf, out_pdf = sys.argv[1], sys.argv[2]
if not os.path.exists(in_pdf):
    print(f"Input PDF not found: {in_pdf}"); sys.exit(1)
if not os.path.exists(SIGN_IMAGE_PATH):
    print(f"Signature image not found: {SIGN_IMAGE_PATH}"); sys.exit(1)

doc = fitz.open(in_pdf)

# Load signature to get aspect ratio
sig_pix = fitz.Pixmap(SIGN_IMAGE_PATH)
sig_w_px, sig_h_px = sig_pix.width, sig_pix.height
aspect = sig_h_px / sig_w_px if sig_w_px else 1.0
sig_h_pt = SIG_WIDTH_PT * aspect

def render_page_to_pil(page, zoom):
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    mode = "RGB" if pix.n < 4 else "RGBA"
    img = Image.frombytes(mode, (pix.width, pix.height), pix.samples)
    if mode == "RGBA":
        img = img.convert("RGB")
    return img

def place_on_page(page, x_disp, y_disp):
    # Convert display pixels to PDF points
    x_pt = x_disp / DISPLAY_ZOOM
    y_pt = y_disp / DISPLAY_ZOOM

    # Clamp inside page rect
    page_rect = page.rect
    x_pt = max(0, min(x_pt, page_rect.width - SIG_WIDTH_PT))
    y_pt = max(0, min(y_pt, page_rect.height - sig_h_pt))

    rect = fitz.Rect(x_pt, y_pt, x_pt + SIG_WIDTH_PT, y_pt + sig_h_pt)
    page.insert_image(rect, filename=SIGN_IMAGE_PATH, keep_proportion=True)
    print(f"Stamped at ({x_pt:.1f}, {y_pt:.1f}) pt.")

def show_page_and_get_click(pil_img):
    root = tk.Tk()
    root.title(TITLE)

    # Scrollbars + canvas
    vbar = tk.Scrollbar(root, orient=tk.VERTICAL)
    hbar = tk.Scrollbar(root, orient=tk.HORIZONTAL)
    canvas = tk.Canvas(root, yscrollcommand=vbar.set, xscrollcommand=hbar.set, highlightthickness=0)
    vbar.config(command=canvas.yview)
    hbar.config(command=canvas.xview)

    vbar.pack(side=tk.RIGHT, fill=tk.Y)
    hbar.pack(side=tk.BOTTOM, fill=tk.X)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    # Put image on canvas
    photo = ImageTk.PhotoImage(pil_img)
    img_item = canvas.create_image(0, 0, anchor="nw", image=photo)
    canvas.config(scrollregion=(0, 0, pil_img.width, pil_img.height))

    clicked_coords = {"x": None, "y": None}

    # Mouse wheel scrolling (Windows/Mac)
    def on_mousewheel(event):
        if event.state & 0x1:  # Shift held → horizontal scroll
            canvas.xview_scroll(-1 * (event.delta // 120), "units")
        else:
            canvas.yview_scroll(-1 * (event.delta // 120), "units")

    # Linux wheel events
    def on_button4(_): canvas.yview_scroll(-3, "units")
    def on_button5(_): canvas.yview_scroll(3, "units")

    def on_click(event):
        # Translate from window coords to image coords using canvas scroll
        x = canvas.canvasx(event.x)
        y = canvas.canvasy(event.y)
        clicked_coords["x"], clicked_coords["y"] = int(x), int(y)
        root.destroy()

    # Bindings
    canvas.bind("<Button-1>", on_click)
    canvas.bind_all("<MouseWheel>", on_mousewheel)     # Windows/macOS
    canvas.bind_all("<Shift-MouseWheel>", on_mousewheel)
    canvas.bind_all("<Button-4>", on_button4)         # Linux
    canvas.bind_all("<Button-5>", on_button5)

    # Allow dragging with middle mouse (optional)
    def start_drag(event): canvas.scan_mark(event.x, event.y)
    def drag(event): canvas.scan_dragto(event.x, event.y, gain=1)
    canvas.bind("<Button-2>", start_drag)
    canvas.bind("<B2-Motion>", drag)

    # ESC to skip page
    def skip_page(_):
        clicked_coords["x"], clicked_coords["y"] = None, None
        root.destroy()
    root.bind("<Escape>", skip_page)

    # Size and start
    root.geometry("1000x700")  # sensible default window size
    root.mainloop()

    return clicked_coords["x"], clicked_coords["y"]

print("\nInstructions:")
print("- A scrollable window opens for each page.")
print("- Use mouse wheel / scrollbars to move, Shift + wheel for horizontal scroll.")
print("- Click to place the TOP-LEFT corner of the signature.")
print("- Press ESC to skip a page.\n")

for pno in range(len(doc)):
    page = doc[pno]
    pil_img = render_page_to_pil(page, DISPLAY_ZOOM)

    x_disp, y_disp = show_page_and_get_click(pil_img)

    if x_disp is None:
        print(f"Page {pno+1}/{len(doc)}: skipped.")
        continue

    place_on_page(page, x_disp, y_disp)
    print(f"Page {pno+1}/{len(doc)}: done.")

doc.save(out_pdf)
doc.close()
print(f"\nSaved: {out_pdf}")
