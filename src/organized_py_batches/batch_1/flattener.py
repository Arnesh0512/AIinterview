import os
import shutil
from pathlib import Path

def process_python_files(source_dir, temp_output_dir, final_output_dir, files_per_folder=10):
    source_path = Path(source_dir).resolve()
    temp_dir = Path(temp_output_dir).resolve()
    final_dir = Path(final_output_dir).resolve()

    # Clear or create directories
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)

    if final_dir.exists():
        shutil.rmtree(final_dir)
    final_dir.mkdir(parents=True, exist_ok=True)

    print("Step 1: Walking directories and copying flattened .py files...")
    copied_files = []

    for root, dirs, files in os.walk(source_path):
        root_path = Path(root).resolve()

        # Skip if the current directory is the temp directory, final directory, or inside them
        if temp_dir == root_path or temp_dir in root_path.parents:
            continue
        if final_dir == root_path or final_dir in root_path.parents:
            continue

        # Modify dirs in-place to skip 'env' and any output directories from being traversed
        dirs[:] = [
            d for d in dirs 
            if d != "env" 
            and (root_path / d).resolve() != temp_dir 
            and (root_path / d).resolve() != final_dir
        ]

        for file in files:
            if file.endswith(".py"):
                file_path = Path(root) / file
                
                # Create a flattened filename using relative path parts
                relative_path = file_path.relative_to(source_path)
                flattened_name = "_".join(relative_path.parts)
                
                dest_path = temp_dir / flattened_name
                
                # Handle potential duplicate flattened names
                counter = 1
                while dest_path.exists():
                    stem = Path(flattened_name).stem
                    suffix = Path(flattened_name).suffix
                    dest_path = temp_dir / f"{stem}_{counter}{suffix}"
                    counter += 1

                shutil.copy2(file_path, dest_path)
                copied_files.append(dest_path)

    print(f"Successfully copied and flattened {len(copied_files)} Python files.")

    print(f"\nStep 2: Organizing files into folders (max {files_per_folder} files per folder)...")
    folder_counter = 1
    current_batch_dir = final_dir / f"batch_{folder_counter}"
    current_batch_dir.mkdir(parents=True, exist_ok=True)

    for index, file_path in enumerate(copied_files):
        if index > 0 and index % files_per_folder == 0:
            folder_counter += 1
            current_batch_dir = final_dir / f"batch_{folder_counter}"
            current_batch_dir.mkdir(parents=True, exist_ok=True)

        shutil.move(str(file_path), current_batch_dir / file_path.name)

    # Clean up temporary flattening folder
    shutil.rmtree(temp_dir)
    print(f"Done! All files organized into folders under '{final_dir.name}/'.")

if __name__ == "__main__":
    # Change these paths as required
    SOURCE_DIRECTORY = "."          # Current directory or path to your project
    TEMP_FLAT_DIRECTORY = "./temp_flat_py"
    FINAL_ORGANIZED_DIRECTORY = "./organized_py_batches"

    process_python_files(SOURCE_DIRECTORY, TEMP_FLAT_DIRECTORY, FINAL_ORGANIZED_DIRECTORY, files_per_folder=10)