"""Generate placeholder assets for LinkedIn image rendering."""

from PIL import Image, ImageDraw, ImageFont
import os

# Create template image (1080x1350 - LinkedIn portrait)
print("Creating template image...")
template_path = "assets/branding/linkedin_template.png"

# Create solid black background
img = Image.new("RGB", (1080, 1350), color=(0, 0, 0))

# Add a subtle gradient or accent (optional)
# For now, just a solid black background
img.save(template_path, "PNG", quality=95)
print(f"[OK] Template created: {template_path}")

# Try to create a simple font file
# Since we can't download, we'll update the code to handle missing fonts gracefully
font_path = "assets/fonts/Inter_18pt-SemiBold.ttf"

# Create a placeholder marker file
with open(font_path.replace(".ttf", ".txt"), "w") as f:
    f.write("""FONT SETUP REQUIRED

To use custom fonts, download one of these open-source fonts and save as assets/fonts/Inter_18pt-SemiBold.ttf:

Option 1: Inter Font (https://github.com/rsms/inter)
- Download Inter_18pt-SemiBold.ttf
- Place in: assets/fonts/

Option 2: Roboto Font (https://github.com/google/roboto)
- Download Roboto-Medium.ttf
- Rename to: Inter_18pt-SemiBold.ttf
- Place in: assets/fonts/

Option 3: Use system fonts (Segoe UI, Arial, etc.)
- Already available on Windows

If no font file is present, PIL will use its built-in bitmap font.
""")

print(f"[OK] Font placeholder created: {font_path.replace('.ttf', '.txt')}")
print("[OK] Asset setup complete!")
