#!/usr/bin/env python3
import os
import sys

# Test tile loading
images_dir = os.path.join(os.path.dirname(__file__), 'Images', 'tilemap')
print(f"Looking for tiles in: {images_dir}")
print(f"Path exists: {os.path.exists(images_dir)}")

if os.path.exists(images_dir):
    print("\nFiles found:")
    for f in os.listdir(images_dir):
        print(f"  - {f}")
else:
    print("ERROR: tilemap folder not found!")
