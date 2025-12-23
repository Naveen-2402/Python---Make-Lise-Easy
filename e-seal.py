import fitz  # PyMuPDF
from tkinter import Tk, Canvas, Scrollbar, Frame, Label
from PIL import Image, ImageTk
import os
import math

PDF_FILE = "sealed_Non-Disclosure Agreement (NDA) Form.pdf"
SEAL_FILE = "sign_transparent.png"

class PDFSealApp:
    def __init__(self, root):
        self.root = root
        self.doc = fitz.open(PDF_FILE)
        self.page_index = 0
        self.scale_factor = 2.0  # PDF render scale
        
        self.seal_img_orig = Image.open(SEAL_FILE).convert("RGBA")
        self.seal_scale = 1.0
        self.seal_added = False
        self.seal_pos = None
        self.seal_id = None
        self.bbox_id = None
        self.handles = []
        
        # Interaction state
        self.dragging = False
        self.resizing = False
        self.resize_handle = None
        self.last_mouse_pos = None
        
        # Status bar
        self.status_label = Label(root, text="Click to place seal | Drag to move | Use handles to resize | Arrow keys to move | Mouse wheel to scale | Press 's' to save & next", 
                                  bd=1, relief="sunken", anchor="w")
        self.status_label.pack(side="bottom", fill="x")
        
        frame = Frame(root)
        frame.pack(fill="both", expand=True)

        self.canvas = Canvas(frame, bg="grey")
        self.canvas.pack(side="left", fill="both", expand=True)

        v_scroll = Scrollbar(frame, orient="vertical", command=self.canvas.yview)
        v_scroll.pack(side="right", fill="y")

        h_scroll = Scrollbar(root, orient="horizontal", command=self.canvas.xview)
        h_scroll.pack(fill="x")

        self.canvas.configure(
            yscrollcommand=v_scroll.set,
            xscrollcommand=h_scroll.set
        )

        self.load_page()

        # Mouse bindings
        self.canvas.bind("<Button-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
        self.canvas.bind("<MouseWheel>", self.resize_seal_wheel)      # Windows
        self.canvas.bind("<Button-4>", self.resize_seal_wheel)        # Linux scroll up
        self.canvas.bind("<Button-5>", self.resize_seal_wheel)        # Linux scroll down
        
        # Keyboard bindings
        root.bind("s", self.next_page)
        root.bind("<Left>", lambda e: self.move_seal_keyboard(-10, 0))
        root.bind("<Right>", lambda e: self.move_seal_keyboard(10, 0))
        root.bind("<Up>", lambda e: self.move_seal_keyboard(0, -10))
        root.bind("<Down>", lambda e: self.move_seal_keyboard(0, 10))
        root.bind("<Shift-Left>", lambda e: self.move_seal_keyboard(-1, 0))
        root.bind("<Shift-Right>", lambda e: self.move_seal_keyboard(1, 0))
        root.bind("<Shift-Up>", lambda e: self.move_seal_keyboard(0, -1))
        root.bind("<Shift-Down>", lambda e: self.move_seal_keyboard(0, 1))
        root.bind("r", self.reset_seal)
        root.bind("<Delete>", self.delete_seal)

    def load_page(self):
        self.canvas.delete("all")

        page = self.doc[self.page_index]
        pix = page.get_pixmap(matrix=fitz.Matrix(self.scale_factor, self.scale_factor))
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        self.tk_img = ImageTk.PhotoImage(img)
        self.page_width = pix.width
        self.page_height = pix.height

        self.canvas.create_image(0, 0, anchor="nw", image=self.tk_img)
        self.canvas.config(scrollregion=(0, 0, img.width, img.height))

        self.seal_added = False
        self.seal_id = None
        self.bbox_id = None
        self.handles = []
        self.seal_scale = 1.0
        
        self.update_status(f"Page {self.page_index + 1}/{len(self.doc)} - Click to place seal")

    def update_status(self, text):
        self.status_label.config(text=text)

    def render_seal(self):
        if not self.seal_added or not self.seal_pos:
            return

        x, y = self.seal_pos
        w = int(self.seal_img_orig.width * self.seal_scale)
        h = int(self.seal_img_orig.height * self.seal_scale)

        # Resize seal image
        seal_resized = self.seal_img_orig.resize((w, h), Image.LANCZOS)
        self.tk_seal = ImageTk.PhotoImage(seal_resized)

        # Update or create seal image
        if self.seal_id:
            self.canvas.itemconfig(self.seal_id, image=self.tk_seal)
            self.canvas.coords(self.seal_id, x, y)
        else:
            self.seal_id = self.canvas.create_image(x, y, image=self.tk_seal, anchor="center")

        # Draw bounding box and handles
        self.draw_bbox_and_handles(x, y, w, h)

    def draw_bbox_and_handles(self, cx, cy, w, h):
        # Remove old bbox and handles
        if self.bbox_id:
            self.canvas.delete(self.bbox_id)
        for handle in self.handles:
            self.canvas.delete(handle)
        self.handles = []

        # Calculate corners
        x1, y1 = cx - w/2, cy - h/2
        x2, y2 = cx + w/2, cy + h/2

        # Draw bounding box
        self.bbox_id = self.canvas.create_rectangle(
            x1, y1, x2, y2,
            outline="blue", width=2, dash=(5, 3)
        )

        # Draw corner handles (8 points: 4 corners + 4 midpoints)
        handle_size = 8
        handle_positions = [
            (x1, y1, "nw"),      # Top-left
            (cx, y1, "n"),       # Top-mid
            (x2, y1, "ne"),      # Top-right
            (x2, cy, "e"),       # Right-mid
            (x2, y2, "se"),      # Bottom-right
            (cx, y2, "s"),       # Bottom-mid
            (x1, y2, "sw"),      # Bottom-left
            (x1, cy, "w"),       # Left-mid
        ]

        for hx, hy, tag in handle_positions:
            handle = self.canvas.create_rectangle(
                hx - handle_size/2, hy - handle_size/2,
                hx + handle_size/2, hy + handle_size/2,
                fill="white", outline="blue", width=2, tags=tag
            )
            self.handles.append(handle)

    def get_handle_at_pos(self, x, y):
        """Check if mouse is over a resize handle"""
        for handle in self.handles:
            coords = self.canvas.coords(handle)
            if coords[0] <= x <= coords[2] and coords[1] <= y <= coords[3]:
                tags = self.canvas.gettags(handle)
                return tags[0] if tags else None
        return None

    def is_inside_seal(self, x, y):
        """Check if point is inside seal bounds"""
        if not self.seal_pos:
            return False
        
        cx, cy = self.seal_pos
        w = self.seal_img_orig.width * self.seal_scale
        h = self.seal_img_orig.height * self.seal_scale
        
        return (cx - w/2 <= x <= cx + w/2) and (cy - h/2 <= y <= cy + h/2)

    def on_mouse_down(self, event):
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)

        if self.seal_added:
            # Check if clicking on a handle
            handle = self.get_handle_at_pos(x, y)
            if handle:
                self.resizing = True
                self.resize_handle = handle
                self.last_mouse_pos = (x, y)
                self.update_status(f"Resizing from {handle} corner")
                return
            
            # Check if clicking inside seal
            if self.is_inside_seal(x, y):
                self.dragging = True
                self.last_mouse_pos = (x, y)
                self.update_status("Dragging seal")
                return

        # Place new seal
        self.place_seal(x, y)

    def on_mouse_drag(self, event):
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)

        if self.dragging and self.last_mouse_pos:
            # Move seal
            dx = x - self.last_mouse_pos[0]
            dy = y - self.last_mouse_pos[1]
            new_x = self.seal_pos[0] + dx
            new_y = self.seal_pos[1] + dy
            self.seal_pos = (new_x, new_y)
            self.render_seal()
            self.last_mouse_pos = (x, y)

        elif self.resizing and self.last_mouse_pos and self.resize_handle:
            # Resize seal from handle
            self.resize_from_handle(x, y)
            self.last_mouse_pos = (x, y)

    def on_mouse_up(self, event):
        self.dragging = False
        self.resizing = False
        self.resize_handle = None
        self.last_mouse_pos = None
        if self.seal_added:
            self.update_status("Seal placed - Use arrow keys or drag to move, handles to resize")

    def resize_from_handle(self, x, y):
        """Resize seal by dragging a handle"""
        if not self.seal_pos or not self.last_mouse_pos:
            return

        cx, cy = self.seal_pos
        last_x, last_y = self.last_mouse_pos
        
        # Calculate distance change
        old_dist = math.sqrt((last_x - cx)**2 + (last_y - cy)**2)
        new_dist = math.sqrt((x - cx)**2 + (y - cy)**2)
        
        if old_dist > 0:
            scale_change = new_dist / old_dist
            self.seal_scale *= scale_change
            self.seal_scale = max(0.1, min(self.seal_scale, 5.0))
            self.render_seal()

    def place_seal(self, x, y):
        """Place seal at position"""
        self.seal_pos = (x, y)
        self.seal_scale = 1.0
        self.seal_added = True
        self.render_seal()
        self.update_status("Seal placed - Drag to move, use handles to resize, arrow keys for fine adjustment")

    def move_seal_keyboard(self, dx, dy):
        """Move seal using keyboard arrows"""
        if not self.seal_added or not self.seal_pos:
            return
        
        x, y = self.seal_pos
        self.seal_pos = (x + dx, y + dy)
        self.render_seal()

    def resize_seal_wheel(self, event):
        """Resize seal with mouse wheel"""
        if not self.seal_added:
            return

        # Determine scroll direction
        if event.num == 5 or event.delta < 0:
            self.seal_scale *= 0.95
        else:
            self.seal_scale *= 1.05

        self.seal_scale = max(0.1, min(self.seal_scale, 5.0))
        self.render_seal()
        self.update_status(f"Seal scale: {self.seal_scale:.2f}x")

    def reset_seal(self, event=None):
        """Reset seal to original size"""
        if not self.seal_added:
            return
        self.seal_scale = 1.0
        self.render_seal()
        self.update_status("Seal reset to original size")

    def delete_seal(self, event=None):
        """Delete the current seal"""
        if self.seal_id:
            self.canvas.delete(self.seal_id)
        if self.bbox_id:
            self.canvas.delete(self.bbox_id)
        for handle in self.handles:
            self.canvas.delete(handle)
        
        self.seal_added = False
        self.seal_id = None
        self.bbox_id = None
        self.handles = []
        self.seal_pos = None
        self.update_status("Seal deleted - Click to place new seal")

    def next_page(self, event=None):
        """Save seal to PDF and move to next page"""
        page = self.doc[self.page_index]

        if self.seal_added and self.seal_pos:
            # Convert canvas coordinates to PDF coordinates
            canvas_x, canvas_y = self.seal_pos
            
            # Account for scale factor
            pdf_x = canvas_x / self.scale_factor
            pdf_y = canvas_y / self.scale_factor
            
            # Calculate seal dimensions in PDF points
            w = (self.seal_img_orig.width * self.seal_scale) / self.scale_factor
            h = (self.seal_img_orig.height * self.seal_scale) / self.scale_factor
            
            # Create rectangle (PDF coordinates)
            rect = fitz.Rect(
                pdf_x - w / 2,
                pdf_y - h / 2,
                pdf_x + w / 2,
                pdf_y + h / 2
            )
            
            page.insert_image(rect, filename=SEAL_FILE)
            self.update_status(f"Seal saved to page {self.page_index + 1}")

        self.page_index += 1

        if self.page_index >= len(self.doc):
            output = f"sealed_{os.path.basename(PDF_FILE)}"
            self.doc.save(output)
            print(f"✓ Saved: {output}")
            self.update_status(f"Complete! Saved as {output}")
            self.root.after(1000, self.root.quit)
            return

        self.load_page()

root = Tk()
root.title("PDF Seal Placement Tool - Enhanced")
root.geometry("1200x800")
try:
    root.state("zoomed")
except:
    pass

app = PDFSealApp(root)
root.mainloop()