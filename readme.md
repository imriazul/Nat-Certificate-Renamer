# 📄 Certificate Renamer OCR by imriazul

An automated, human-in-the-loop Python tool that bulk-renames scanned certificates (**PDF** and **TIF/TIFF**) by extracting specific ID numbers using **Optical Character Recognition (OCR)**.

Instead of manually renaming hundreds of files, this script allows you to visually select the target ID area on the first document. It then automatically crops the same area from all remaining documents, extracts the text using OCR, and renames the files within seconds.

---

## ✨ Features

* 📁 **Native File Picker**
  Select folders or ZIP files using your operating system's native file browser.

* 🎯 **Interactive OCR Region Selection**
  Draw a single bounding box on a sample certificate to define the target area for the entire batch.

* 🔍 **Automatic Image Enhancement**
  Upscales images and applies Otsu's thresholding to improve OCR accuracy.

* 🔄 **Smart Retry System**
  Failed OCR files are isolated, allowing you to reselect a crop region specifically for difficult scans.

* 📄 **Cross-Format Support**
  Supports PDF, TIF, and TIFF certificate files.

---

# 🚀 Installation

## The Best Practice: Using a Virtual Environment

A virtual environment creates an isolated workspace for your project so that its Python packages do not interfere with your main system. This is the professional standard for Python development.

### 1. Create a Project Folder

```bash
mkdir certificate_project
cd certificate_project
```

### 2. Create a Virtual Environment

```bash
python -m venv env
```

### 3. Activate the Virtual Environment

#### 🪟 Windows (Command Prompt)

```cmd
env\Scripts\activate.bat
```

#### 🪟 Windows (PowerShell)

```powershell
env\Scripts\Activate.ps1
```

#### 🍎 macOS / 🐧 Linux

```bash
source env/bin/activate
```

Once activated, you will see something similar to this in your terminal:

```text
(env) C:\certificate_project>
```

### 4. Install Python Dependencies

Install the required Python packages safely inside the virtual environment:

```bash
pip install opencv-python pytesseract pdf2image
```

---

## ⚠️ Important: Install the Core Software

The `pip` command only installs the Python bindings that communicate with the actual software. You must also install the underlying OCR and PDF processing tools on your operating system.

### 🔎 Tesseract OCR Engine

#### 🪟 Windows

* Download and install the Tesseract OCR installer from the **UB-Mannheim GitHub release**.
* Note the installation path (commonly):

```text
C:\Program Files\Tesseract-OCR\tesseract.exe
```

* If required, configure the path inside your Python script:

```python
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
```

#### 🍎 macOS

```bash
brew install tesseract
```

#### 🐧 Ubuntu / Debian

```bash
sudo apt install tesseract-ocr
```

---

## 📄 Poppler (Required for PDF Processing)

### 🪟 Windows

1. Download the latest Poppler Windows binary.
2. Extract the archive.
3. Add the `bin` folder to your Windows **Environment PATH** variable.

Example:

```text
C:\poppler\Library\bin
```

#### 🍎 macOS

```bash
brew install poppler
```

#### 🐧 Ubuntu / Debian

```bash
sudo apt install poppler-utils
```

---

## 💻 Running the Application

After completing the installation:

1. Activate your virtual environment.
2. Navigate to the project folder.
3. Run the script:

```bash
python renamer.py
```

---

## 🧭 Workflow

### 1. Select Input

Choose whether your certificates are stored in a folder or ZIP archive.

### 2. Enter Output Folder Name

Provide a name for the directory where the renamed certificates will be saved.

### 3. Select the OCR Region

The first certificate will open in a window.

* Click and drag to draw a box around the target ID number.
* Press `ENTER` to confirm your selection.

### 4. Automatic Batch Processing

The program will:

* Crop the selected area from every certificate.
* Enhance the image for OCR.
* Extract the certificate number.
* Rename the files automatically.

If OCR fails for any documents, the program will isolate them and allow you to select a new crop region specifically for those files.

---

## 🛑 Troubleshooting

### `ModuleNotFoundError: No module named 'cv2'`

The Python packages are missing or the virtual environment is not activated.

Run:

```bash
pip install opencv-python pytesseract pdf2image
```

---

### `TesseractNotFoundError`

Tesseract OCR is not installed or Python cannot locate the executable.

* Verify that Tesseract is installed.
* Ensure the installation path is correctly configured.

---

### `PDFInfoNotInstalledError`

Poppler is missing or not available in your system PATH.

* Install Poppler.
* Confirm that the `bin` directory has been added to your PATH.

---

### Empty or Frozen Selection Window

Make sure:

* Your input folder contains supported `.pdf`, `.tif`, or `.tiff` files.
* Your operating system supports OpenCV GUI windows.

---

## 🧰 Built With

* Python
* OpenCV
* Tesseract OCR (PyTesseract)
* PDF2Image

---

## 📄 License

This project is released under the MIT License.
