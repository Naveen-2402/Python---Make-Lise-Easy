from PIL import Image
import os
import math

# --- Configuration ---
input_filename = 'sign.jpg'
output_filename = 'sign_transparent.png'

# This 'tolerance' value is the threshold you need to adjust.
# It controls how "close" a pixel's color must be to the 
# background color to be made transparent.
#
# - A low value (e.g., 20) is very strict.
# - A high value (e.g., 100) is more aggressive.
#
# Start with a value around 60 and adjust if needed.
tolerance = 60
# --- End Configuration ---

def color_distance(rgb1, rgb2):
    """
    Calculates the 'distance' between two RGB colors.
    This uses a simple "Manhattan distance" which is fast and effective.
    """
    r1, g1, b1 = rgb1
    r2, g2, b2 = rgb2
    return abs(r1 - r2) + abs(g1 - g2) + abs(g1 - g2)

# Check if the input file exists
if not os.path.exists(input_filename):
    print(f"Error: Input file '{input_filename}' not found.")
    print("Please upload your 'sign.jpg' file first.")
else:
    try:
        # Open the image
        img = Image.open(input_filename)
        
        # Ensure it's in RGB mode to get the background color
        img_rgb = img.convert("RGB")
        
        # Get the background color from the top-left corner (0,0)
        # This assumes the top-left pixel is a good sample of the background.
        bg_color = img_rgb.getpixel((0, 0))
        print(f"Detected background color from (0,0): {bg_color}")

        # Now convert the *original* image to RGBA for processing
        img_rgba = img.convert("RGBA")
        datas = img_rgba.getdata()
        
        newData = []
        
        for item in datas:
            # item is (R, G, B, A)
            # We compare its RGB values (item[:3]) to the detected bg_color
            
            # Calculate distance between current pixel's color and background color
            distance = color_distance(item[:3], bg_color)
            
            # If the distance is within the tolerance, make it transparent
            if distance < tolerance:
                newData.append((255, 255, 255, 0)) # Make transparent
            else:
                # This is part of the signature, keep it opaque
                newData.append(item)
                
        # Apply the new pixel data
        img_rgba.putdata(newData)
        
        # Save the new image
        img_rgba.save(output_filename, "PNG")
        
        print(f"Successfully processed image.")
        print(f"New image saved as: '{output_filename}'")
        print(f"---")
        print(f"If the result isn't perfect, edit the 'tolerance' value (currently {tolerance}) and re-run.")
        print(f"- If parts of your signature are missing, make 'tolerance' smaller (e.g., 40).")
        print(f"- If some background is still visible, make 'tolerance' larger (e.g., 80).")

    except Exception as e:
        print(f"An error occurred: {e}")