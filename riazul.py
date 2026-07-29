import os
import cv2
import zipfile
import shutil
import re
import pytesseract
import numpy as np
import tkinter as tk
from tkinter import filedialog
from PIL import Image
from pdf2image import convert_from_path

# ==========================================
# CONFIGURATION
# ==========================================
YEAR_MONTH_PREFIX = "2606"              
MAX_ATTEMPTS = 5

# WINDOWS SPECIFIC PATHS
# Point this to the 'bin' folder inside the Poppler folder you extracted
POPPLER_PATH = r"C:\poppler\Library\bin" 

# Point this to where Tesseract was installed
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# ==========================================

def setup_directories():
    """Creates isolated folders for the processing conveyor belt."""
    dirs = ['temp_pending', 'temp_success', 'temp_failed']
    for d in dirs:
        if os.path.exists(d):
            shutil.rmtree(d)
        os.makedirs(d)
    return dirs

def prepare_input_files(source_path, target_dir):
    """Extracts a ZIP or securely copies a folder into the pending directory."""
    if os.path.isfile(source_path) and source_path.lower().endswith('.zip'):
        print(f"📦 Extracting {source_path}...")
        with zipfile.ZipFile(source_path, 'r') as zip_ref:
            zip_ref.extractall(target_dir)
    elif os.path.isdir(source_path):
        print(f"📂 Copying files from folder '{source_path}'...")
        for root, dirs, files in os.walk(source_path):
            for file in files:
                if file.startswith('.'): continue
                src_path = os.path.join(root, file)
                # Maintain any subfolder structures inside the target directory
                rel_dir = os.path.relpath(root, source_path)
                dst_dir = os.path.join(target_dir, rel_dir) if rel_dir != '.' else target_dir
                os.makedirs(dst_dir, exist_ok=True)
                shutil.copy2(src_path, os.path.join(dst_dir, file))
    else:
        print(f"❌ Error: Could not find '{source_path}'. Please check if the folder or zip exists.")
        exit(1)

def load_image_safely(filepath):
    """Safely loads TIFs and PDFs using Pillow/pdf2image to bypass OpenCV bugs."""
    ext = filepath.split('.')[-1].lower()
    try:
        if ext in ['tif', 'tiff']:
            pil_img = Image.open(filepath).convert('RGB')
            return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        elif ext == 'pdf':
            pages = convert_from_path(filepath, dpi=200, poppler_path=POPPLER_PATH)
            return cv2.cvtColor(np.array(pages[0].convert('RGB')), cv2.COLOR_RGB2BGR)
    except Exception as e:
        return None
    return None

def get_first_image_for_cropping(folder_path):
    """Finds the first valid image in the folder to use as a template."""
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            if file.startswith('.'): continue
            filepath = os.path.join(root, file)
            ext = file.lower()
            if ext.endswith('.tif') or ext.endswith('.tiff') or ext.endswith('.pdf'):
                image = load_image_safely(filepath)
                if image is not None:
                    return image
    return None

def get_roi_from_user(image, attempt_num):
    """Opens an interactive window to draw the crop rectangle."""
    print(f"\n🎯 [ATTEMPT {attempt_num}/{MAX_ATTEMPTS}] A window will open shortly.")
    print("👉 DRAW a box strictly around the 14-digit Examinee Number.")
    print("👉 Press ENTER or SPACE to confirm.")
    print("👉 Press 'c' to cancel.")
    
    screen_height = 800
    scale = screen_height / image.shape[0] if image.shape[0] > screen_height else 1.0
    
    if scale != 1.0:
        resized_img = cv2.resize(image, (int(image.shape[1] * scale), int(image.shape[0] * scale)))
    else:
        resized_img = image.copy()
    
    window_title = f"Select Examinee Number (Attempt {attempt_num})"
    roi = cv2.selectROI(window_title, resized_img, showCrosshair=True)
    cv2.destroyAllWindows()
    cv2.waitKey(1)
    
    x, y, w, h = [int(val / scale) for val in roi]
    return x, y, w, h

def clean_filename(filename):
    """Removes previous attempt tags so they don't stack up."""
    return re.sub(r'^Failed_Attempt_\d+_', '', filename)

def process_files_pass(pending_dir, success_dir, failed_dir, x, y, w, h, prefix, attempt):
    """Processes all files currently in the pending folder."""
    custom_config = r'--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789'
    pattern = rf'\b({prefix}\d{{10}})\b'
    
    success_count = 0
    fail_count = 0

    for root, dirs, files in os.walk(pending_dir):
        for filename in files:
            if filename.startswith('.'): continue 

            filepath = os.path.join(root, filename)
            image = load_image_safely(filepath)
            ext = filename.split('.')[-1].lower()
            original_clean_name = clean_filename(filename)

            if image is not None:
                # 1. Crop
                cropped_zone = image[y:y+h, x:x+w]
                
                # 2. MAGIC ENHANCEMENT
                gray_zone = cv2.cvtColor(cropped_zone, cv2.COLOR_BGR2GRAY)
                enlarged_zone = cv2.resize(gray_zone, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
                _, thresh_zone = cv2.threshold(enlarged_zone, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)

                # 3. OCR
                raw_text = pytesseract.image_to_string(thresh_zone, config=custom_config)
                
                # 4. Clean and Validate
                clean_text = raw_text.strip().replace(" ", "")
                match = re.search(pattern, clean_text)
                
                if match:
                    examinee_number = match.group(1)
                    
                    # Setup path variables for checking collisions
                    standard_name = f"{examinee_number}.{ext}"
                    standard_path = os.path.join(success_dir, standard_name)
                    
                    duplicate_base_name = f"Duplicate_{examinee_number}.{ext}"
                    duplicate_base_path = os.path.join(success_dir, duplicate_base_name)

                    # Check if this number is already taken in the success folder
                    has_standard_collision = os.path.exists(standard_path)
                    has_duplicate_collision = os.path.exists(duplicate_base_path)
                    
                    if has_standard_collision or has_duplicate_collision:
                        if attempt < MAX_ATTEMPTS:
                            # --- RETRY LOGIC (Attempts 1 to 4) ---
                            if has_standard_collision:
                                # Yank the existing file back into the failed queue
                                existing_failed_name = f"Failed_Attempt_{attempt}_Yanked_{examinee_number}.{ext}"
                                shutil.move(standard_path, os.path.join(failed_dir, existing_failed_name))
                                success_count -= 1  # Remove from success tally
                                fail_count += 1     # Add to failed tally
                                
                            # Put the current file into the failed queue too
                            current_failed_name = f"Failed_Attempt_{attempt}_{original_clean_name}"
                            shutil.move(filepath, os.path.join(failed_dir, current_failed_name))
                            fail_count += 1
                            print(f"⚠️ Collision on {examinee_number}! Both sent to Attempt {attempt + 1}.")
                            
                        else:
                            # --- FINAL ATTEMPT LOGIC ---
                            if has_standard_collision:
                                # Rename the first file to Duplicate_...
                                shutil.move(standard_path, duplicate_base_path)
                                
                            # Find the next available Duplicate_..._X name for the current file
                            counter = 1
                            while True:
                                dup_name = f"Duplicate_{examinee_number}_{counter}.{ext}"
                                dup_path = os.path.join(success_dir, dup_name)
                                if not os.path.exists(dup_path):
                                    shutil.move(filepath, dup_path)
                                    break
                                counter += 1
                                
                            print(f"⚠️ Unresolved Duplicate saved as {dup_name}")
                            success_count += 1
                    else:
                        # --- NORMAL SUCCESS ---
                        shutil.move(filepath, standard_path)
                        print(f"✅ Success: {original_clean_name} -> {standard_name}")
                        success_count += 1
                else:
                    new_failed_name = f"Failed_Attempt_{attempt}_{original_clean_name}"
                    new_failed_path = os.path.join(failed_dir, new_failed_name)
                    
                    shutil.move(filepath, new_failed_path)
                    print(f"❌ Failed: {original_clean_name} (OCR read: '{clean_text}')")
                    fail_count += 1
            else:
                print(f"⚠️ Error: Could not read {original_clean_name}. Moving to failed.")
                new_failed_name = f"Unreadable_{original_clean_name}"
                new_failed_path = os.path.join(failed_dir, new_failed_name)
                shutil.move(filepath, new_failed_path)
                fail_count += 1

    return success_count, fail_count
def save_output_folder(source_folder, output_folder_name):
    """Moves the final processed files into the chosen output folder."""
    os.makedirs(output_folder_name, exist_ok=True)
    for item in os.listdir(source_folder):
        shutil.move(os.path.join(source_folder, item), os.path.join(output_folder_name, item))

# ==========================================
# MAIN EXECUTION
# ==========================================
if __name__ == "__main__":
    print("\n=== Certificate Renamer Setup ===")
    
    # 1. UI Folder Selection (Skipping ZIP prompt)
    root = tk.Tk()
    root.withdraw() # Hide the main tk window
    root.attributes('-topmost', True) # Force popup to the front on Mac
    
    print("\n⏳ Opening file browser... Please select your Certificates Folder.")
    input_path = filedialog.askdirectory(
        title="Select Certificates Folder"
    )
    root.destroy()
        
    if not input_path:
        print("❌ Selection cancelled. Exiting.")
        exit(1)
        
    print(f"✅ Target Locked: {input_path}")
    
    # 2. Output Folder Naming
    output_folder_name = input("\nEnter the desired name for your final output folder (leave blank to auto-name): ").strip()
    if not output_folder_name:
        # Extract the base name of the input file/folder and remove extension if any
        input_base_name = os.path.splitext(os.path.basename(input_path))[0]
        output_folder_name = f"renamed_{input_base_name}"
        
    try:
        pending_dir, success_dir, failed_dir = setup_directories()
        
        # Now uses the dynamic selected input path
        prepare_input_files(input_path, pending_dir)
        
        attempt = 1
        total_success = 0
        f_count = 0

        while attempt <= MAX_ATTEMPTS:
            # 1. Grab a template image from the current pending folder
            template_img = get_first_image_for_cropping(pending_dir)
            if template_img is None:
                break # No files left to process

            # 2. Get user coordinates
            x, y, w, h = get_roi_from_user(template_img, attempt)
            if w == 0 or h == 0:
                print("⚠️ Selection cancelled. Saving remaining files...")
                # FIX: If cancelled, rescue any files remaining in pending so they aren't deleted
                for file in os.listdir(pending_dir):
                    shutil.move(os.path.join(pending_dir, file), os.path.join(success_dir, file))
                break
                
            print(f"\n🔒 Coordinates locked for Attempt {attempt}. Processing...")
            
            # 3. Process the pass
            s_count, f_count = process_files_pass(pending_dir, success_dir, failed_dir, x, y, w, h, YEAR_MONTH_PREFIX, attempt)
            total_success += s_count
            
            # 4. Evaluate Results
            if f_count == 0:
                print(f"\n🌟 PERFECT PASS! All files successfully renamed.")
                break
            else:
                print(f"\n⚠️ Attempt {attempt} Complete. {s_count} succeeded, {f_count} failed.")
                
                if attempt < MAX_ATTEMPTS:
                    print(f"🔄 Automatically moving to Attempt {attempt + 1} for the {f_count} failed files...")
                    # Move failed files back into the pending queue for the next loop
                    for file in os.listdir(failed_dir):
                        shutil.move(os.path.join(failed_dir, file), os.path.join(pending_dir, file))
                    attempt += 1
                else:
                    # Final attempt reached. Move the final failed files into the success folder so they aren't lost
                    for file in os.listdir(failed_dir):
                        shutil.move(os.path.join(failed_dir, file), os.path.join(success_dir, file))
                    print(f"❌ Max attempts reached. Remaining {f_count} files will be saved with 'Failed_Attempt' names.")
                    break
                    
        # Move everything into the final chosen folder
        save_output_folder(success_dir, output_folder_name)
        
        # --- NEW FINAL SUMMARY REPORT ---
        print("\n" + "=" * 45)
        print("📊 FINAL SCAN & RENAME REPORT")
        print("=" * 45)
        print(f"✅ Successfully Renamed : {total_success} files")
        print(f"❌ Failed to Rename     : {f_count} files")
        print(f"🔄 Total Attempts Used  : {min(attempt, MAX_ATTEMPTS)}")
        print(f"🎉 Saved Final Folder As: {output_folder_name}")
        print("=" * 45 + "\n")

    finally:
        # Cleanup temporary folders
        shutil.rmtree(pending_dir, ignore_errors=True)
        shutil.rmtree(success_dir, ignore_errors=True)
        shutil.rmtree(failed_dir, ignore_errors=True)
