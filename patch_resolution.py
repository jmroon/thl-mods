#!/usr/bin/env python3
"""
Resolution Patch for The Hundred Line -Last Defense Academy-

This script patches the game executable to support higher resolutions
like 5120x2880 (5K) by modifying hardcoded resolution values.

BACKUP YOUR EXECUTABLE BEFORE RUNNING THIS!

Usage:
    python patch_resolution.py HUNDRED_LINE.exe [--dry-run]
"""

import struct
import argparse
import shutil
from pathlib import Path
from dataclasses import dataclass


@dataclass
class Patch:
    offset: int
    original: bytes
    replacement: bytes
    description: str


def create_patches(data: bytes, target_width: int, target_height: int) -> list[Patch]:
    """Create patches for resolution modification"""
    
    patches = []
    
    # Patch only the 3840x2160 entry in the resolution table
    print(f"\nPatching 3840x2160 -> {target_width}x{target_height}")
    
    orig_width = struct.pack('<I', 3840)
    orig_height = struct.pack('<I', 2160)
    new_width = struct.pack('<I', target_width)
    new_height = struct.pack('<I', target_height)
    
    # Resolution table entry
    table_offset = 0xBDA4F0
    if data[table_offset:table_offset + 4] == orig_width:
        patches.append(Patch(table_offset, orig_width, new_width, 
            f"Resolution table: 3840 -> {target_width} (width)"))
    if data[table_offset + 4:table_offset + 8] == orig_height:
        patches.append(Patch(table_offset + 4, orig_height, new_height,
            f"Resolution table: 2160 -> {target_height} (height)"))
    
    # Code patches for resolution limits
    code_patches = [
        (0x054DF7, orig_width, new_width, "Width getter (mov eax, 3840)"),
        (0x4B4305, orig_width, new_width, "Resolution param width (mov edx, 3840)"),
        (0x054D37, orig_height, new_height, "Height getter (mov eax, 2160)"),
        (0x4B430B, orig_height, new_height, "Resolution param height (mov r8d, 2160)"),
    ]
    
    for offset, orig, new, desc in code_patches:
        if data[offset:offset + 4] == orig:
            patches.append(Patch(offset, orig, new, desc))
        else:
            print(f"WARNING: Mismatch at 0x{offset:X}, skipping: {desc}")
    
    return patches


def apply_patches(data: bytearray, patches: list[Patch], dry_run: bool = False) -> bytearray:
    """Apply patches to the executable data"""
    
    print("\n" + "=" * 60)
    print("PATCHES TO APPLY:" if not dry_run else "PATCHES (DRY RUN):")
    print("=" * 60)
    
    for patch in patches:
        orig_val = struct.unpack('<I', patch.original)[0]
        new_val = struct.unpack('<I', patch.replacement)[0]
        print(f"  0x{patch.offset:08X}: {orig_val} -> {new_val}")
        print(f"                   {patch.description}")
        
        if not dry_run:
            data[patch.offset:patch.offset + len(patch.replacement)] = patch.replacement
    
    print(f"\nTotal patches: {len(patches)}")
    return data


def main():
    parser = argparse.ArgumentParser(
        description="Patch The Hundred Line for higher resolution support",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python patch_resolution.py HUNDRED_LINE.exe --dry-run
    python patch_resolution.py HUNDRED_LINE.exe
    python patch_resolution.py HUNDRED_LINE.exe --width 7680 --height 4320
        """
    )
    parser.add_argument("exe_path", type=Path, help="Path to HUNDRED_LINE.exe")
    parser.add_argument("--dry-run", action="store_true", help="Analyze only, don't modify")
    parser.add_argument("--width", type=int, default=5120, help="Target width (default: 5120)")
    parser.add_argument("--height", type=int, default=2880, help="Target height (default: 2880)")
    parser.add_argument("--no-backup", action="store_true", help="Skip creating backup")
    
    args = parser.parse_args()
    
    if not args.exe_path.exists():
        print(f"Error: File not found: {args.exe_path}")
        return 1
    
    print(f"Resolution Patch for The Hundred Line")
    print(f"Target resolution: {args.width}x{args.height}")
    print("=" * 60)
    
    with open(args.exe_path, 'rb') as f:
        data = bytearray(f.read())
    
    print(f"File size: {len(data):,} bytes")
    
    patches = create_patches(bytes(data), args.width, args.height)
    
    if not patches:
        print("\nNo patches could be created. The executable may be different from expected.")
        return 1
    
    apply_patches(data, patches, args.dry_run)
    
    if args.dry_run:
        print("\n[DRY RUN] No changes made.")
        return 0
    
    if not args.no_backup:
        backup_path = args.exe_path.with_suffix('.exe.backup')
        if not backup_path.exists():
            print(f"\nCreating backup: {backup_path}")
            shutil.copy2(args.exe_path, backup_path)
        else:
            print(f"\nBackup already exists: {backup_path}")
    
    with open(args.exe_path, 'wb') as f:
        f.write(data)
    
    print("\n" + "=" * 60)
    print("DONE!")
    print("=" * 60)
    print(f"\nUpdate your userconfig.properties:")
    print(f'  "App.Window.W" : {args.width},')
    print(f'  "App.Window.H" : {args.height},')
    print(f"\nRestore from backup if needed:")
    print(f"  copy {args.exe_path.with_suffix('.exe.backup')} {args.exe_path}")
    
    return 0


if __name__ == "__main__":
    exit(main())