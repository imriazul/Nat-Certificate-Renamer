# 📄 Certificate Batch Renamer (OCR Pipeline)

An automated, human-in-the-loop Python tool that bulk-renames scanned certificates (PDFs and TIFs) by extracting specific ID numbers using Optical Character Recognition (OCR). 

Instead of typing hundreds of filenames by hand, this script allows you to visually draw a box around the target number on the first document, and then automatically crops, reads, and renames the rest of the batch in seconds.

## ✨ Features
* **Native UI File Picker:** Easily select folders or ZIP files using your system's native file browser.
* **Interactive Targeting:** Draw a single bounding box on a template image to set the crop coordinates for the entire batch.
* **Smart Image Enhancement:** Automatically upscales and applies Otsu's thresholding to scanned documents for near-100% OCR accuracy.
* **Intelligent Retry Loop:** If a scan is blurry and fails, the script isolates it and allows you to re-crop specifically for the failed files up to 3 times.
* **Cross-Format Support:** Seamlessly handles both multi-page PDFs and TIF image sequences.

---

## 🛠️ Prerequisites (Crucial Step)

Because this tool processes complex PDFs and uses advanced OCR, you **must** install two system engines on your computer before running the Python code.

### 1. Tesseract OCR & Poppler
**🍎 macOS:**
Open your terminal and install via [Homebrew](https://brew.sh/):
```bash
brew install tesseract poppler
