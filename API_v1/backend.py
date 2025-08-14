from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import shutil
import os
import uuid
import uvicorn
import pathlib

app = FastAPI()

# Add CORS middleware to allow frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for now
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Directory to store uploaded and processed files
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Serve frontend static files if directory exists
STATIC_DIR = pathlib.Path(__file__).parent.resolve() / "static"
if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
else:
    print("Warning: 'static' directory does not exist. Static files will not be served.")

# Serve the web interface HTML file at root, renamed to CLARA.html
WEB_INTERFACE_PATH = pathlib.Path(__file__).parent.resolve() / "CLARA.html"

@app.get("/", response_class=HTMLResponse)
async def serve_web_interface():
    if not WEB_INTERFACE_PATH.exists():
        return HTMLResponse(content="Web interface not found.", status_code=404)
    return HTMLResponse(content=WEB_INTERFACE_PATH.read_text(encoding="utf-8"), status_code=200)

@app.post("/upload_pdf/")
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed.")
    file_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{file_id}.pdf")
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return {"file_id": file_id, "filename": file.filename}

@app.post("/process_pdf/{file_id}")
async def process_pdf(file_id: str):
    import subprocess
    input_path = os.path.join(UPLOAD_DIR, f"{file_id}.pdf")
    if not os.path.exists(input_path):
        raise HTTPException(status_code=404, detail="File not found.")
    output_path = os.path.join(UPLOAD_DIR, f"{file_id}_redacted.pdf")

    # Call the existing PDF_PII_redactor_SL_v5.py script as a subprocess
    # Assuming the script accepts input and output file paths as arguments
    try:
        subprocess.run([
            "python", "PDF_PII_redactor_SL_v5.py",
            "--input", input_path,
            "--output", output_path
        ], check=True)
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Redaction process failed: {e}")

    return {"redacted_file_url": f"/download/{file_id}_redacted.pdf"}

@app.get("/download/{filename}")
async def download_file(filename: str):
    file_path = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found.")
    return FileResponse(file_path, media_type="application/pdf", filename=filename)

if __name__ == "__main__":
    # To run the backend server, execute this script directly:
    # python backend.py
    uvicorn.run(app, host="0.0.0.0", port=8000)