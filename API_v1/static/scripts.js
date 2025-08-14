// scripts.js

document.addEventListener('DOMContentLoaded', () => {
    // Cache DOM elements
    const contentSection = document.getElementById('content');
    const spellLevelSelect = document.getElementById('spellLevel');
    const grammarLevelSelect = document.getElementById('grammarLevel');
    const fluencyLevelSelect = document.getElementById('fluencyLevel');

    // Navigation buttons
    window.navigateTo = function(mode) {
        contentSection.innerHTML = '';
        if (mode === 'upload') {
            renderUploadUI();
        } else if (mode === 'redact') {
            renderRedactUI();
        } else if (mode === 'manual') {
            renderManualUI();
        }
    };

    // Initial load
    navigateTo('upload');

    function renderUploadUI() {
        contentSection.innerHTML = `
            <h2>Upload PDF</h2>
            <input type="file" id="pdfFileInput" accept="application/pdf" />
            <button id="uploadBtn">Upload</button>
            <div id="uploadStatus"></div>
        `;

        const uploadBtn = document.getElementById('uploadBtn');
        const pdfFileInput = document.getElementById('pdfFileInput');
        const uploadStatus = document.getElementById('uploadStatus');

        uploadBtn.addEventListener('click', () => {
            const file = pdfFileInput.files[0];
            if (!file) {
                alert('Please select a PDF file to upload.');
                return;
            }
            uploadStatus.textContent = 'Uploading...';

            const formData = new FormData();
            formData.append('file', file);

            fetch('/upload_pdf/', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                uploadStatus.textContent = 'Uploaded: ' + data.filename;
                // Store file_id for later processing
                window.uploadedFileId = data.file_id;
            })
            .catch(err => {
                uploadStatus.textContent = 'Upload failed.';
                console.error(err);
            });
        });
    }

    function renderRedactUI() {
        if (!window.uploadedFileId) {
            contentSection.innerHTML = '<p>Please upload a PDF first.</p>';
            return;
        }
        contentSection.innerHTML = `
            <h2>Auto Redact PDF</h2>
            <button id="processBtn">Start Redaction</button>
            <div id="processStatus"></div>
            <div id="downloadLink"></div>
        `;

        const processBtn = document.getElementById('processBtn');
        const processStatus = document.getElementById('processStatus');
        const downloadLink = document.getElementById('downloadLink');

        processBtn.addEventListener('click', () => {
            processStatus.textContent = 'Processing...';
            downloadLink.innerHTML = '';

            fetch('/process_pdf/' + window.uploadedFileId, {
                method: 'POST'
            })
            .then(response => response.json())
            .then(data => {
                processStatus.textContent = 'Processing complete.';
                downloadLink.innerHTML = '<a href="' + data.redacted_file_url + '" target="_blank" download>Download Redacted PDF</a>';
            })
            .catch(err => {
                processStatus.textContent = 'Processing failed.';
                console.error(err);
            });
        });
    }

    function renderManualUI() {
        contentSection.innerHTML = '<h2>Manual Highlights - Coming Soon</h2>';
    }
});