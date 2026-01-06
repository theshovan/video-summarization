class VideoSummarizer {
    constructor() {
        this.uploadArea = document.getElementById('uploadArea');
        this.fileInput = document.getElementById('fileInput');
        this.browseButton = document.getElementById('browseButton');
        this.summarizeButton = document.getElementById('summarizeButton');
        this.fileName = document.getElementById('fileName');
        this.languageSelect = document.getElementById('languageSelect');
        this.progressContainer = document.getElementById('progressContainer');
        this.progressFill = document.getElementById('progressFill');
        this.progressText = document.getElementById('progressText');
        this.resultsSection = document.getElementById('resultsSection');
        this.errorSection = document.getElementById('errorSection');
        this.errorMessage = document.getElementById('errorMessage');
        this.detectedLanguage = document.getElementById('detectedLanguage');
        this.textLength = document.getElementById('textLength');
        this.summaryStatus = document.getElementById('summaryStatus');
        
        this.selectedFile = null;
        this.initializeEventListeners();
    }

    initializeEventListeners() {
        // Browse button click
        this.browseButton.addEventListener('click', () => {
            this.fileInput.click();
        });

        // File input change
        this.fileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                this.handleFileSelection(e.target.files[0]);
            }
        });

        // Summarize button click
        this.summarizeButton.addEventListener('click', () => {
            if (this.selectedFile) {
                this.processFile(this.selectedFile);
            }
        });

        // Drag & drop support
        this.uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            this.uploadArea.classList.add('dragover');
        });

        this.uploadArea.addEventListener('dragleave', () => {
            this.uploadArea.classList.remove('dragover');
        });

        this.uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            this.uploadArea.classList.remove('dragover');
            
            if (e.dataTransfer.files.length > 0) {
                this.handleFileSelection(e.dataTransfer.files[0]);
            }
        });

        // Language selection change
        this.languageSelect.addEventListener('change', () => {
            if (this.selectedFile) {
                this.hideResults();
                this.hideError();
            }
        });
    }

    handleFileSelection(file) {
        // Validate file type
        const allowedTypes = ['video/', 'audio/'];
        const isValidType = allowedTypes.some(type => file.type.startsWith(type));
        
        if (!isValidType) {
            this.showError('Please upload a valid video or audio file (MP4, AVI, MOV, MP3, WAV, etc.).');
            this.resetFileSelection();
            return;
        }

        // Validate file size (50MB max)
        const maxSize = 50 * 1024 * 1024;
        if (file.size > maxSize) {
            this.showError('File size must be less than 50MB.');
            this.resetFileSelection();
            return;
        }

        // Update UI with selected file
        this.selectedFile = file;
        this.fileName.textContent = `${file.name} (${this.formatFileSize(file.size)})`;
        this.uploadArea.classList.add('has-file');
        this.summarizeButton.disabled = false;
        this.hideError();
        this.hideResults();
        
        // Update progress text to show selected language
        const languageName = this.languageSelect.options[this.languageSelect.selectedIndex].text;
        this.progressText.textContent = `Processing your file in ${languageName}... This may take a while for longer videos.`;
    }

    resetFileSelection() {
        this.selectedFile = null;
        this.fileInput.value = '';
        this.fileName.textContent = 'No file chosen';
        this.uploadArea.classList.remove('has-file');
        this.summarizeButton.disabled = true;
    }

    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    async processFile(file) {
        this.showProgress();
        this.hideResults();
        this.hideError();
        this.summarizeButton.disabled = true;
        this.summarizeButton.innerHTML = '<span class="loading-spinner">⏳</span> Processing...';

        try {
            // Read file as base64
            const fileData = await this.readFileAsBase64(file);
            const selectedLanguage = this.languageSelect.value;
            const languageName = this.languageSelect.options[this.languageSelect.selectedIndex].text;
            
            this.progressText.textContent = `Processing your file in ${languageName}... This may take a while for longer videos.`;
            
            const response = await fetch('/process', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    fileData: fileData,
                    fileType: file.type,
                    fileName: file.name,
                    language: selectedLanguage
                })
            });

            const data = await response.json();

            if (data.success) {
                this.displayResults(data);
            } else {
                this.showError(data.error || 'An error occurred during processing.');
            }
        } catch (error) {
            this.showError('Network error: Please check your connection and try again.');
            console.error('Processing error:', error);
        } finally {
            this.hideProgress();
            this.summarizeButton.disabled = false;
            this.summarizeButton.textContent = 'Convert & Translate';
        }
    }

    readFileAsBase64(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(reader.result);
            reader.onerror = reject;
            reader.readAsDataURL(file);
        });
    }

    showProgress() {
        this.progressContainer.style.display = 'block';
        this.animateProgress();
    }

    hideProgress() {
        this.progressContainer.style.display = 'none';
        this.progressFill.style.width = '0%';
    }

    animateProgress() {
        let width = 0;
        const interval = setInterval(() => {
            if (width >= 90) {
                clearInterval(interval);
            } else {
                width += Math.random() * 5; // Slower progress for longer processing
                this.progressFill.style.width = Math.min(width, 90) + '%';
            }
        }, 300);
    }

    displayResults(data) {
        // Show detected language and text length
        this.detectedLanguage.textContent = `Detected Language: ${data.original_language}`;
        this.textLength.textContent = `Transcribed Text Length: ${data.text_length || data.original_text.length} characters`;
        
        // Show summary status
        if (data.was_summarized) {
            this.summaryStatus.textContent = "✓ Summarization was applied (text was long enough)";
            this.summaryStatus.style.color = "#4CAF50";
        } else {
            this.summaryStatus.textContent = "ℹ️ Text was too short for summarization - showing full text";
            this.summaryStatus.style.color = "#ff9800";
        }
        
        // Show original transcribed text
        const originalTextElement = document.getElementById('originalText');
        originalTextElement.textContent = data.original_text || 'No text transcribed';
        this.addCharCount(originalTextElement);
        
        if (data.original_language === 'Hindi') {
            originalTextElement.classList.add('hindi-text');
        } else {
            originalTextElement.classList.remove('hindi-text');
        }
        
        // Show English full text and summary
        const englishFullTextElement = document.getElementById('englishFullText');
        const englishSummaryElement = document.getElementById('englishSummary');
        
        englishFullTextElement.textContent = data.english_full_text || 'No English translation available';
        englishSummaryElement.textContent = data.english_summary || 'No summary available';
        
        this.addCharCount(englishFullTextElement);
        this.addCharCount(englishSummaryElement);
        
        // Show Bengali full text and summary
        const bengaliFullTextElement = document.getElementById('bengaliFullText');
        const bengaliSummaryElement = document.getElementById('bengaliSummary');
        
        bengaliFullTextElement.textContent = data.bengali_full_text || 'No Bengali translation available';
        bengaliSummaryElement.textContent = data.bengali_summary || 'No summary available';
        
        this.addCharCount(bengaliFullTextElement);
        this.addCharCount(bengaliSummaryElement);
        
        // Add Bengali text styling
        bengaliFullTextElement.classList.add('bengali-text');
        bengaliSummaryElement.classList.add('bengali-text');
        
        // Check if summaries are different from full text
        this.checkSummaryDifference(englishFullTextElement, englishSummaryElement, 'english');
        this.checkSummaryDifference(bengaliFullTextElement, bengaliSummaryElement, 'bengali');
        
        this.resultsSection.style.display = 'block';
        this.resultsSection.scrollIntoView({ behavior: 'smooth' });
    }

    addCharCount(element) {
        const charCount = element.textContent.length;
        const countElement = document.createElement('div');
        countElement.className = 'char-count';
        countElement.textContent = `${charCount} characters`;
        element.appendChild(countElement);
    }

    checkSummaryDifference(fullTextElement, summaryElement, language) {
        const fullText = fullTextElement.textContent.replace(/^\d+ characters$/, '').trim();
        const summary = summaryElement.textContent.replace(/^\d+ characters$/, '').trim();
        
        if (fullText && summary && fullText === summary) {
            summaryElement.classList.add('same-as-full');
        } else {
            summaryElement.classList.remove('same-as-full');
        }
    }

    showError(message) {
        this.errorMessage.textContent = message;
        this.errorSection.style.display = 'block';
        this.errorSection.scrollIntoView({ behavior: 'smooth' });
    }

    hideError() {
        this.errorSection.style.display = 'none';
    }

    hideResults() {
        this.resultsSection.style.display = 'none';
    }
}

// Initialize the application when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new VideoSummarizer();
});

// Add keyboard shortcut
document.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.target.matches('select, input')) {
        const summarizeButton = document.getElementById('summarizeButton');
        if (!summarizeButton.disabled) {
            summarizeButton.click();
        }
    }
});