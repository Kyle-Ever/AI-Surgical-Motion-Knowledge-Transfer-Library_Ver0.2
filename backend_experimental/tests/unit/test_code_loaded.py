# -*- coding: utf-8 -*-
"""
Test if modified code is loaded
"""
import sys
import inspect

# Import sam2_tracker_video module
from app.ai_engine.processors.sam2_tracker_video import SAM2TrackerVideo

# Get source code of _extract_trajectories method
method = SAM2TrackerVideo._extract_trajectories
source = inspect.getsource(method)

# Check if fix is present
if "mask = mask[0]" in source:
    print("[OK] Modified code is loaded!")
    print("     Found: mask = mask[0]")

    # Check if old code still exists
    if "mask[:, :, 0]" in source:
        print("[ERROR] Old code (mask[:, :, 0]) still exists!")
    else:
        print("[OK] Old code (mask[:, :, 0]) removed")
else:
    print("[ERROR] Modified code NOT loaded!")
    print("        Expected: mask = mask[0]")

    if "mask[:, :, 0]" in source:
        print("        Found: mask[:, :, 0] (old code)")

# Show relevant lines
print("\n=== Normalization code ===")
for i, line in enumerate(source.split('\n')):
    if 'mask.ndim == 3' in line or 'mask[0]' in line or 'mask[:, :, 0]' in line:
        print(f"Line {i}: {line}")
