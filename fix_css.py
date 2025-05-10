#!/usr/bin/env python3
"""
Helper script to fix the theme CSS in the NokNok app.py file
by removing the duplicate CSS at the end of the file.
"""

# Open app.py and read its content
with open("app.py", "r") as f:
    content = f.read()

# Find where the redundant CSS starts
css_start_marker = "# Inject dark theme CSS overrides when in dark mode"
if css_start_marker in content:
    # Split at the marker
    parts = content.split(css_start_marker)
    
    # Keep only the first part (everything before the duplicate CSS)
    new_content = parts[0]
    
    # Write back the clean file
    with open("app.py", "w") as f:
        f.write(new_content)
    
    print("Successfully removed duplicate CSS from app.py")
else:
    print("Marker not found in app.py") 