# Setup Guide for CLARA PDF PII Redactor

## Python 3.10 Environment Setup

This application requires Python 3.10 for optimal compatibility. Here are setup instructions for different platforms:

### Option 1: Using pyenv (Recommended)

If you have pyenv installed:
```bash
# Install Python 3.10
pyenv install 3.10.12

# Set Python 3.10 for this directory
cd clara-app
pyenv local 3.10.12

# Verify Python version
python --version  # Should show Python 3.10.12
```

### Option 2: Using conda/miniconda

```bash
# Create new environment with Python 3.10
conda create -n clara-app python=3.10

# Activate environment
conda activate clara-app

# Navigate to app directory
cd clara-app
```

### Option 3: Using venv (if you already have Python 3.10 system-wide)

```bash
cd clara-app

# Create virtual environment
python3.10 -m venv venv

# Activate virtual environment
source venv/bin/activate  # On macOS/Linux
# or
venv\Scripts\activate     # On Windows

# Verify Python version
python --version  # Should show Python 3.10.x
```

## Installation Steps

Once you have Python 3.10 active:

1. **Install dependencies:**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

2. **Install spaCy models:**
   ```bash
   python -m spacy download en_core_web_sm
   ```

3. **Optional - Install transformer model (larger, better accuracy):**
   ```bash
   python -m spacy download en_core_web_trf
   ```

4. **Test installation:**
   ```bash
   python test_integration.py
   ```

5. **Run the application:**
   ```bash
   streamlit run PDF_PII_redactor_v6.py
   ```

## Troubleshooting

### If pip install fails:
- Make sure you're using Python 3.10: `python --version`
- Upgrade pip: `pip install --upgrade pip`
- Try installing without cache: `pip install --no-cache-dir -r requirements.txt`

### If spaCy models fail to install:
- Install models individually:
  ```bash
  python -m spacy download en_core_web_sm --user
  ```

### If numpy build fails:
- Install numpy first separately:
  ```bash
  pip install numpy==1.24.4
  pip install -r requirements.txt
  ```

## Usage

1. Start the Streamlit app: `streamlit run PDF_PII_redactor_v6.py`
2. Upload a PDF document
3. Use "Auto Redact" to automatically detect PII
4. Use "Manual Highlights" → "Launch Edit and Review" for manual tagging
5. Download the redacted PDF

## Manual Tagging Interface

- **Text Selection**: Click and drag to select text
- **Keyboard Shortcuts**:
  - `B` = Tag as B4 (Trade Secret)
  - `P` = Tag as B6 (Patient Information) 
  - `O` = Tag as Other
  - `U` = Untag selection
  - `Esc` = Clear selection
- **Visual Feedback**: Real-time color coding and statistics
- **Port**: Manual tagging interface runs on http://localhost:5001

## File Structure

```
clara-app/
├── PDF_PII_redactor_v6.py      # Main Streamlit application
├── manual_pdf_tagger.py        # Flask-based manual tagging module
├── templates/                  # HTML templates for manual tagging
│   ├── manual_pdf_tagger.html
│   └── tagging_complete.html
├── requirements.txt            # Python dependencies
├── test_integration.py         # Integration tests
├── clara_logo.png             # Application logo
├── README.md                  # Documentation
└── SETUP.md                   # This setup guide