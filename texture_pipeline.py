#!/usr/bin/env python
"""
Texture Processing Pipeline
Converts DDS -> PNG -> Upscale with Real-ESRGAN -> DDS

Usage:
    python texture_pipeline.py <stage> [options]

Stages:
    extract   - Convert t_pic_chr*.dds files to PNG
    upscale   - Upscale PNGs with Real-ESRGAN
    repack    - Convert upscaled PNGs back to DDS
    all       - Run all stages sequentially

Examples:
    python texture_pipeline.py extract --input ./game_textures --output ./01_extracted
    python texture_pipeline.py upscale --input ./01_extracted --output ./02_upscaled --scale 2
    python texture_pipeline.py repack --input ./02_upscaled --output ./03_repacked
    python texture_pipeline.py all --input ./game_textures --scale 2
"""

import argparse
import subprocess
import sys
from pathlib import Path


def run_command(cmd: list[str], description: str) -> bool:
    """Run a command and return success status."""
    print(f"  {description}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"    Error: {result.stderr}")
            return False
        return True
    except FileNotFoundError as e:
        print(f"    Error: Command not found - {e}")
        return False


def extract_dds_to_png(input_dir: Path, output_dir: Path) -> int:
    """Convert all DDS files to PNG using texconv."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    dds_files = list(input_dir.glob("*.dds"))
    
    if not dds_files:
        print(f"No DDS files found in {input_dir}")
        return 0
    
    print(f"Found {len(dds_files)} DDS files to extract")
    
    success_count = 0
    for dds_file in dds_files:
        filename = Path(dds_file).stem
        if run_command(
            ["texconv", "-ft", "png", "-y", "-nologo", "-o", str(output_dir), dds_file],
            f"Converting {filename}.dds -> {filename}.png"
        ):
            success_count += 1
    
    print(f"Extracted {success_count}/{len(dds_files)} files")
    return success_count


def upscale_pngs(input_dir: Path, output_dir: Path, scale: int, realesrgan_path: Path, tile: int) -> int:
    """Upscale PNG files using Real-ESRGAN."""
    import time
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Find all PNG files
    png_files = list(input_dir.glob("*.png"))
    
    if not png_files:
        print(f"No PNG files found in {input_dir}")
        return 0
    
    total = len(png_files)
    print(f"Found {total} PNG files to upscale")
    
    # Verify Real-ESRGAN paths
    inference_script = realesrgan_path / "inference_realesrgan.py"
    venv_python = realesrgan_path / "venv" / "Scripts" / "python.exe"
    
    if not inference_script.exists():
        print(f"Error: Could not find inference_realesrgan.py at {inference_script}")
        return 0
    
    if not venv_python.exists():
        print(f"Error: Could not find venv Python at {venv_python}")
        return 0
    
    print(f"Upscaling with {scale}x output scale, tile size {tile}...")
    print(f"Processing all {total} files in single batch (model loads once)...")
    
    start_time = time.time()
    
    cmd = [
        str(venv_python),
        str(inference_script),
        "-n", "RealESRGAN_x4plus_anime_6B",
        "-i", str(input_dir),
        "-o", str(output_dir),
        "--outscale", str(scale),
        "--tile", str(tile),
        "--suffix", ""
    ]
    
    # Run with live output
    result = subprocess.run(cmd)
    
    elapsed = time.time() - start_time
    
    if result.returncode != 0:
        print("Error running Real-ESRGAN")
        return 0
    
    # Count output files
    output_files = list(output_dir.glob("*.png"))
    success_count = len(output_files)
    
    avg_per_image = elapsed / success_count if success_count > 0 else 0
    print(f"Upscaled {success_count}/{total} files in {elapsed:.1f}s ({avg_per_image:.2f}s/image)")
    return success_count


def downscale_pngs(input_dir: Path, output_dir: Path, scale_percent: int = 50, workers: int = 8) -> int:
    """Downscale PNG files using ImageMagick Lanczos."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import time
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    png_files = list(input_dir.glob("*.png"))
    
    if not png_files:
        print(f"No PNG files found in {input_dir}")
        return 0
    
    total = len(png_files)
    print(f"Found {total} PNG files to downscale to {scale_percent}% (using {workers} workers)")
    
    def convert_single(png_file: Path) -> bool:
        output_file = output_dir / png_file.name
        cmd = ["magick", str(png_file), "-filter", "Lanczos", "-resize", f"{scale_percent}%", str(output_file)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode == 0
    
    start_time = time.time()
    success_count = 0
    completed = 0
    
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(convert_single, f): f for f in png_files}
        
        for future in as_completed(futures):
            completed += 1
            if future.result():
                success_count += 1
            
            if completed % 50 == 0 or completed == total:
                elapsed = time.time() - start_time
                rate = completed / elapsed
                eta = (total - completed) / rate if rate > 0 else 0
                print(f"  [{completed}/{total}] {rate:.1f} files/sec - ETA: {eta:.0f}s")
    
    elapsed = time.time() - start_time
    print(f"Downscaled {success_count}/{total} files in {elapsed:.1f}s ({elapsed/total:.2f}s/image)")
    return success_count


def repack_png_to_dds(input_dir: Path, output_dir: Path) -> int:
    """Convert PNG files back to DDS using texconv (GPU-accelerated)."""
    import time
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Find all PNG files
    png_files = list(input_dir.glob("*.png"))
    
    if not png_files:
        print(f"No PNG files found in {input_dir}")
        return 0
    
    total = len(png_files)
    print(f"Found {total} PNG files to repack")
    
    start_time = time.time()
    success_count = 0
    
    for i, png_file in enumerate(png_files):
        cmd = ["texconv", "-ft", "dds", "-f", "BC7_UNORM", "-m", "1", "-dx10", "-y", "-nologo", "-o", str(output_dir), str(png_file)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            success_count += 1
        
        if (i + 1) % 50 == 0 or (i + 1) == total:
            elapsed = time.time() - start_time
            rate = (i + 1) / elapsed
            eta = (total - (i + 1)) / rate if rate > 0 else 0
            print(f"  [{i + 1}/{total}] {rate:.1f} files/sec - ETA: {eta:.0f}s")
    
    elapsed = time.time() - start_time
    print(f"Repacked {success_count}/{total} files in {elapsed:.1f}s ({elapsed/total:.2f}s/image)")
    return success_count


def main():
    parser = argparse.ArgumentParser(
        description="Texture processing pipeline for DDS upscaling",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument("stage", choices=["extract", "upscale", "downscale", "repack", "all"],
                        help="Pipeline stage to run")
    parser.add_argument("--input", "-i", type=Path, required=True,
                        help="Input directory")
    parser.add_argument("--output", "-o", type=Path,
                        help="Output directory (auto-generated for 'all' stage)")
    parser.add_argument("--scale", "-s", type=int, default=4,
                        help="Upscale factor (default: 4)")
    parser.add_argument("--downscale", "-d", type=int, default=50,
                        help="Downscale percentage (default: 50)")
    parser.add_argument("--tile", "-t", type=int, default=1024,
                        help="Tile size for processing (default: 1024, use 0 to disable)")
    parser.add_argument("--workers", "-w", type=int, default=8,
                        help="Number of parallel workers for downscale (default: 8)")
    parser.add_argument("--realesrgan-path", type=Path, default=Path("D:/dev/Real-ESRGAN"),
                        help="Path to Real-ESRGAN directory")
    
    args = parser.parse_args()
    
    if args.stage == "all":
        # Run all stages with auto-generated folder names
        base_dir = args.input.parent
        
        extracted_dir = base_dir / "01_extracted_png"
        upscaled_dir = base_dir / "02_upscaled_png"
        downscaled_dir = base_dir / "03_downscaled_png"
        repacked_dir = base_dir / "04_repacked_dds"
        
        print("=" * 50)
        print("STAGE 1: Extract DDS -> PNG")
        print("=" * 50)
        extract_dds_to_png(args.input, extracted_dir)
        
        print()
        print("=" * 50)
        print("STAGE 2: Upscale PNGs")
        print("=" * 50)
        upscale_pngs(extracted_dir, upscaled_dir, args.scale, args.realesrgan_path, args.tile)
        
        print()
        print("=" * 50)
        print("STAGE 3: Downscale PNGs")
        print("=" * 50)
        downscale_pngs(upscaled_dir, downscaled_dir, args.downscale, args.workers)
        
        print()
        print("=" * 50)
        print("STAGE 4: Repack PNG -> DDS")
        print("=" * 50)
        repack_png_to_dds(downscaled_dir, repacked_dir)
        
        print()
        print("=" * 50)
        print("Pipeline complete!")
        print(f"  Extracted PNGs:  {extracted_dir}")
        print(f"  Upscaled PNGs:   {upscaled_dir}")
        print(f"  Downscaled PNGs: {downscaled_dir}")
        print(f"  Final DDS:       {repacked_dir}")
        print("=" * 50)
        
    elif args.stage == "extract":
        if not args.output:
            print("Error: --output required for extract stage")
            sys.exit(1)
        extract_dds_to_png(args.input, args.output)
        
    elif args.stage == "upscale":
        if not args.output:
            print("Error: --output required for upscale stage")
            sys.exit(1)
        upscale_pngs(args.input, args.output, args.scale, args.realesrgan_path, args.tile)
        
    elif args.stage == "downscale":
        if not args.output:
            print("Error: --output required for downscale stage")
            sys.exit(1)
        downscale_pngs(args.input, args.output, args.downscale, args.workers)
        
    elif args.stage == "repack":
        if not args.output:
            print("Error: --output required for repack stage")
            sys.exit(1)
        repack_png_to_dds(args.input, args.output)


if __name__ == "__main__":
    main()