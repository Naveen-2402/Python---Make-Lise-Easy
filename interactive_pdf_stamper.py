import sys, os
import fitz  # PyMuPDF
from PIL import Image, ImageTk
import tkinter as tk

# -------- CONFIG --------
SIGN_IMAGE_PATH = "sign_transparent.png"  # Use your transparent PNG
SIG_WIDTH_PT = 100    # Initial signature width in PDF points
DISPLAY_ZOOM = 1.5      # Render scale for preview
TITLE_PREFIX = "Click to place, 'S' to confirm, ESC to skip"
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
try:
    with Image.open(SIGN_IMAGE_PATH) as sig_pil:
        sig_w_px, sig_h_px = sig_pil.width, sig_pil.height
        aspect = sig_h_px / sig_w_px if sig_w_px else 1.0
except Exception as e:
    print(f"Error loading signature image: {e}"); sys.exit(1)

# Calculate initial dimensions
sig_h_pt = SIG_WIDTH_PT * aspect
sig_w_disp = SIG_WIDTH_PT * DISPLAY_ZOOM
sig_h_disp = sig_h_pt * DISPLAY_ZOOM

# --- Store results here ---
# List of tuples: (page_object, fitz.Rect)
stamps_to_apply = []
# --------------------------

def render_page_to_pil(page, zoom):
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    return img

def show_page_and_get_placement(page, pil_img, sig_img_pil):
    root = tk.Tk()
    root.title(f"{TITLE_PREFIX} (Page {page.number + 1}/{len(doc)})")

    # --- Canvas with Scrollbars ---
    vbar = tk.Scrollbar(root, orient=tk.VERTICAL)
    hbar = tk.Scrollbar(root, orient=tk.HORIZONTAL)
    canvas = tk.Canvas(root, yscrollcommand=vbar.set, xscrollcommand=hbar.set, highlightthickness=0)
    vbar.config(command=canvas.yview)
    hbar.config(command=canvas.xview)
    vbar.pack(side=tk.RIGHT, fill=tk.Y)
    hbar.pack(side=tk.BOTTOM, fill=tk.X)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    # --- Page Image ---
    page_photo = ImageTk.PhotoImage(pil_img)
    canvas.create_image(0, 0, anchor="nw", image=page_photo)
    canvas.config(scrollregion=(0, 0, pil_img.width, pil_img.height))

    # --- Signature Image ---
    # Resize signature for display
    sig_disp_img = sig_img_pil.resize((int(sig_w_disp), int(sig_h_disp)), Image.LANCZOS)
    sig_photo = ImageTk.PhotoImage(sig_disp_img)
    
    # Keep a reference to images to prevent garbage collection
    root.images = [page_photo, sig_photo] 
    
    # This will be the ID of the signature on the canvas
    sig_item_id = None
    # This will store the *confirmed* PDF coordinates
    confirmed_rect = {"value": None} 

    # --- Event Handlers ---

    def on_click(event):
        nonlocal sig_item_id
        # Get click position relative to canvas (accounts for scroll)
        x_disp = canvas.canvasx(event.x)
        y_disp = canvas.canvasy(event.y)
        
        if sig_item_id is None:
            # First click: create the signature image
            sig_item_id = canvas.create_image(x_disp, y_disp, anchor="nw", image=sig_photo)
        else:
            # Subsequent clicks: move the signature
            canvas.coords(sig_item_id, x_disp, y_disp)

    def on_key_press(event):
        if event.keysym.lower() == 's':
            if sig_item_id:
                # Get the canvas coordinates [x1, y1, x2, y2]
                coords_disp = canvas.coords(sig_item_id)
                x_disp, y_disp = coords_disp[0], coords_disp[1]
                
                # Convert display pixels back to PDF points
                x_pt = x_disp / DISPLAY_ZOOM
                y_pt = y_disp / DISPLAY_ZOOM
                
                # Clamp inside page rect
                page_rect = page.rect
                x_pt = max(0, min(x_pt, page_rect.width - SIG_WIDTH_PT))
                y_pt = max(0, min(y_pt, page_rect.height - sig_h_pt))

                # Store the final PDF rect
                final_rect = fitz.Rect(x_pt, y_pt, x_pt + SIG_WIDTH_PT, y_pt + sig_h_pt)
                confirmed_rect["value"] = final_rect
                root.destroy()
            else:
                print("Please click to place the signature before pressing 'S'.")
        
        elif event.keysym == 'Escape':
            confirmed_rect["value"] = None
            root.destroy()

    # --- Mouse Wheel Scrolling ---
    def on_mousewheel(event):
        if event.state & 0x1:  # Shift held -> horizontal scroll
            canvas.xview_scroll(-1 * (event.delta // 120), "units")
        else:
            canvas.yview_scroll(-1 * (event.delta // 120), "units")

    def on_button4(_): canvas.yview_scroll(-3, "units")
    def on_button5(_): canvas.yview_scroll(3, "units")

    # --- Bindings ---
    canvas.bind("<Button-1>", on_click)
    root.bind("<Key>", on_key_press)
    root.bind_all("<MouseWheel>", on_mousewheel)      # Windows/macOS
    root.bind_all("<Shift-MouseWheel>", on_mousewheel)
    root.bind_all("<Button-4>", on_button4)          # Linux
    root.bind_all("<Button-5>", on_button5)

    root.geometry("1000x700")
    root.mainloop()
    
    return confirmed_rect["value"]

# --- Main Execution ---

print("\nInstructions:")
print("- A scrollable window opens for each page.")
print("- Click to place the signature. Click again to move it.")
print("- Press 'S' to confirm placement and go to the next page.")
print("- Press ESC to skip a page.\n")

# Load signature PIL image *once*
sig_pil_main = Image.open(SIGN_IMAGE_PATH)

for pno in range(len(doc)):
    page = doc[pno]
    pil_img = render_page_to_pil(page, DISPLAY_ZOOM)

    final_pdf_rect = show_page_and_get_placement(page, pil_img, sig_pil_main)

    if final_pdf_rect is None:
        print(f"Page {pno+1}/{len(doc)}: skipped.")
        continue
    
    # Store the placement action
    stamps_to_apply.append((page, final_pdf_rect))
    print(f"Page {pno+1}/{len(doc)}: staged for stamping.")

# --- Apply all stamps at the end ---
if not stamps_to_apply:
    print("No signatures were placed. Output file not saved.")
else:
    print(f"\nApplying {len(stamps_to_apply)} signatures...")
    for page, rect in stamps_to_apply:
        page.insert_image(rect, filename=SIGN_IMAGE_PATH, keep_proportion=True)
    
    doc.save(out_pdf, garbage=4, deflate=True)
    print(f"Saved: {out_pdf}")

doc.close()