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

# MAC SPECIFIC PATHS
POPPLER_PATH = None 

# ==========================================

def setup_directories():
    """Creates fresh temporary directories."""
    dirs = ['temp_extracted', 'temp_processed']
    for d in dirs:
        if os.path.exists(d):
            shutil.rmtree(d)
        os.makedirs(d)
    return dirs

def extract_zip(zip_path, extract_to):
    """Unzips the uploaded certificates."""
    print(f"📦 Extracting {zip_path}...")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_to)

def load_image_safely(filepath):
    """Safely loads TIFs and PDFs using Pillow/pdf2image to bypass OpenCV bugs."""
    ext = filepath.split('.')[-1].lower()
    
    try:
        if ext in ['tif', 'tiff']:
            # Use Pillow to open TIF, convert to standard RGB, then to OpenCV format
            pil_img = Image.open(filepath).convert('RGB')
            return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
            
        elif ext == 'pdf':
            # Convert PDF to PIL Image, then to OpenCV format
            pages = convert_from_path(filepath, dpi=200, poppler_path=POPPLER_PATH)
            return cv2.cvtColor(np.array(pages[0].convert('RGB')), cv2.COLOR_RGB2BGR)
    except Exception as e:
        print(f"⚠️ Warning: Could not read {filepath}. Error: {e}")
        return None
        
    return None

def get_first_image_for_cropping(folder_path):
    """Finds the first valid TIF or PDF, even if hidden in subfolders."""
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            filepath = os.path.join(root, file)
            ext = file.lower()
            if ext.endswith('.tif') or ext.endswith('.tiff') or ext.endswith('.pdf'):
                image = load_image_safely(filepath)
                if image is not None:
                    return image
    raise FileNotFoundError("No valid .tif or .pdf files could be read from the ZIP.")

def get_roi_from_user(image):
    """Opens an interactive window to draw the crop rectangle."""
    print("\n🎯 A window will open shortly.")
    print("👉 DRAW a box around the Examinee Number.")
    print("👉 Press ENTER or SPACE to confirm.")
    print("👉 Press 'c' to cancel.")
    
    screen_height = 800
    scale = screen_height / image.shape[0] if image.shape[0] > screen_height else 1.0
    
    if scale != 1.0:
        resized_img = cv2.resize(image, (int(image.shape[1] * scale), int(image.shape[0] * scale)))
    else:
        resized_img = image.copy()
    
    roi = cv2.selectROI("Select Examinee Number (Press ENTER when done)", resized_img, showCrosshair=True)
    cv2.destroyAllWindows()
    cv2.waitKey(1) 
    
    x, y, w, h = [int(val / scale) for val in roi]
    return x, y, w, h

def process_and_rename_files(input_folder, output_folder, x, y, w, h, prefix):
    """Loops through all files (and subfolders), crops, runs OCR, and renames them."""
    custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789'
    pattern = rf'\b({prefix}\d{{10}})\b'
    
    failed_count = 0
    success_count = 0

    for root, dirs, files in os.walk(input_folder):
        for filename in files:
            filepath = os.path.join(root, filename)
            
            # Skip hidden files
            if filename.startswith('.'):
                continue 

            image = load_image_safely(filepath)

            if image is not None:
                # 1. Crop
                cropped_zone = image[y:y+h, x:x+w]
                gray_zone = cv2.cvtColor(cropped_zone, cv2.COLOR_BGR2GRAY)

                # 2. OCR
                raw_text = pytesseract.image_to_string(gray_zone, config=custom_config)
                
                # 3. Clean and Validate
                clean_text = raw_text.strip().replace(" ", "")
                match = re.search(pattern, clean_text)
                
                ext = filename.split('.')[-1].lower()
                if match:
                    examinee_number = match.group(1)
                    new_filename = f"{examinee_number}.{ext}"
                    new_filepath = os.path.join(output_folder, new_filename)
                    
                    shutil.copy2(filepath, new_filepath)
                    print(f"✅ Success: {filename} -> {new_filename}")
                    success_count += 1
                else:
                    failed_count += 1
                    manual_filename = f"MANUAL_REVIEW_{failed_count}_{filename}"
                    shutil.copy2(filepath, os.path.join(output_folder, manual_filename))
                    print(f"❌ Failed: {filename} (OCR read: '{clean_text}') -> Tagged for manual review.")

    print(f"\n📊 Summary: {success_count} successful, {failed_count} need manual review.")

def create_output_zip(source_folder, output_zip_name):
    """Zips the processed files."""
    shutil.make_archive(output_zip_name.replace('.zip', ''), 'zip', source_folder)
    print(f"🎉 All done! Saved as: {output_zip_name}")

# ==========================================
# MAIN EXECUTION
# ==========================================
if __name__ == "__main__":
    try:
        extract_dir, process_dir = setup_directories()
        
        extract_zip(INPUT_ZIP, extract_dir)
        
        template_img = get_first_image_for_cropping(extract_dir)
        x, y, w, h = get_roi_from_user(template_img)
        
        if w == 0 or h == 0:
            print("⚠️ Selection was cancelled. Exiting.")
            exit()
            
        print(f"\n🔒 Coordinates locked. Processing remaining files...")
        process_and_rename_files(extract_dir, process_dir, x, y, w, h, YEAR_MONTH_PREFIX)
        
        create_output_zip(process_dir, OUTPUT_ZIP)

    finally:
        shutil.rmtree(extract_dir, ignore_errors=True)
        shutil.rmtree(process_dir, ignore_errors=True)