import os
import cv2
import zipfile
import shutil
import re
import pytesseract
import numpy as np
from PIL import Image
from pdf2image import convert_from_path

# ==========================================
# CONFIGURATION
# ==========================================
INPUT_ZIP = "certificates.zip"          
OUTPUT_ZIP = "renamed_certificates.zip" 
YEAR_MONTH_PREFIX = "2605"              
MAX_ATTEMPTS = 3 # How many times it will automatically retry failed files

# MAC SPECIFIC PATHS
POPPLER_PATH = None 

# ==========================================

def setup_directories():
    """Creates isolated folders for the processing conveyor belt."""
    dirs = ['temp_pending', 'temp_success', 'temp_failed']
    for d in dirs:
        if os.path.exists(d):
            shutil.rmtree(d)
        os.makedirs(d)
    return dirs

def extract_zip(zip_path, extract_to):
    """Unzips the uploaded certificates into the pending folder."""
    print(f"📦 Extracting {zip_path}...")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_to)

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
                
                # 2. MAGIC ENHANCEMENT: Grayscale, Scale up 2x, and Threshold to pure black/white
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
                    new_filename = f"{examinee_number}.{ext}"
                    new_filepath = os.path.join(success_dir, new_filename)
                    
                    shutil.move(filepath, new_filepath)
                    print(f"✅ Success: {original_clean_name} -> {new_filename}")
                    success_count += 1
                else:
                    new_failed_name = f"Failed_Attempt_{attempt}_{original_clean_name}"
                    new_failed_path = os.path.join(failed_dir, new_failed_name)
                    
                    shutil.move(filepath, new_failed_path)
                    print(f"❌ Failed: {original_clean_name} (OCR read: '{clean_text}')")
                    fail_count += 1

    return success_count, fail_count

def create_output_zip(source_folder, output_zip_name):
    """Zips the final processed files."""
    shutil.make_archive(output_zip_name.replace('.zip', ''), 'zip', source_folder)
    print(f"\n🎉 All done! Saved as: {output_zip_name}")

# ==========================================
# MAIN EXECUTION
# ==========================================
if __name__ == "__main__":
    try:
        pending_dir, success_dir, failed_dir = setup_directories()
        extract_zip(INPUT_ZIP, pending_dir)
        
        attempt = 1
        total_success = 0

        while attempt <= MAX_ATTEMPTS:
            # 1. Grab a template image from the current pending folder
            template_img = get_first_image_for_cropping(pending_dir)
            if template_img is None:
                break # No files left to process

            # 2. Get user coordinates
            x, y, w, h = get_roi_from_user(template_img, attempt)
            if w == 0 or h == 0:
                print("⚠️ Selection cancelled.")
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
                    print(f"❌ Max attempts reached. Remaining {f_count} files will be zipped with 'Failed_Attempt' names.")
                    break
                    
        # Package everything up
        create_output_zip(success_dir, OUTPUT_ZIP)

    finally:
        # Cleanup temporary folders
        shutil.rmtree(pending_dir, ignore_errors=True)
        shutil.rmtree(success_dir, ignore_errors=True)
        shutil.rmtree(failed_dir, ignore_errors=True)