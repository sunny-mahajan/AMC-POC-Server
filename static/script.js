class SpeechRecognitionApp {
    constructor() {
        this.recognition = null;
        this.isRecording = false;
        this.currentTranscript = '';
        this.finalTranscriptText = '';
        this.chunkQueue = [];
        this.processingChunks = false;
        this.availableTests = [];
        this.allDetectedTests = new Set();

        this.initializeElements();
        this.setupEventListeners();
        this.initializeSpeechRecognition();
        this.loadAvailableTests();
    }

    initializeElements() {
        this.startBtn = document.getElementById('startBtn');
        this.stopBtn = document.getElementById('stopBtn');
        this.clearBtn = document.getElementById('clearBtn');
        this.status = document.getElementById('status');
        this.recordingIndicator = document.getElementById('recordingIndicator');
        this.liveTranscript = document.getElementById('liveTranscript');
        this.finalTranscript = document.getElementById('finalTranscript');
        this.testResults = document.getElementById('testResults');
        this.processingStatus = document.getElementById('processingStatus');
        this.availableTestsContainer = document.getElementById('availableTests');
    }

    setupEventListeners() {
        this.startBtn.addEventListener('click', () => this.startRecording());
        this.stopBtn.addEventListener('click', () => this.stopRecording());
        this.clearBtn.addEventListener('click', () => this.clearAll());
    }

    initializeSpeechRecognition() {
        if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
            this.updateStatus('Speech recognition not supported in this browser', 'error');
            this.startBtn.disabled = true;
            return;
        }

        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        this.recognition = new SpeechRecognition();
        
        this.recognition.continuous = true;
        this.recognition.interimResults = true;
        this.recognition.lang = 'en-US';

        this.recognition.onstart = () => {
            this.isRecording = true;
            this.updateStatus('Listening...', 'recording');
            this.startBtn.disabled = true;
            this.stopBtn.disabled = false;
            this.recordingIndicator.classList.remove('hidden');
        };

        this.recognition.onresult = (event) => {
            let interimTranscript = '';
            let finalTranscript = '';

            for (let i = event.resultIndex; i < event.results.length; i++) {
                const transcript = event.results[i][0].transcript;
                if (event.results[i].isFinal) {
                    finalTranscript += transcript;
                } else {
                    interimTranscript += transcript;
                }
            }

            // Update live transcript
            this.currentTranscript = this.finalTranscriptText + finalTranscript + interimTranscript;
            this.updateLiveTranscript(this.currentTranscript);

            // Process final results
            if (finalTranscript.trim()) {
                this.finalTranscriptText += finalTranscript;
                this.updateFinalTranscript(this.finalTranscriptText);
                this.processSpeechChunk(finalTranscript.trim());
            }
        };

        this.recognition.onerror = (event) => {
            console.error('Speech recognition error:', event.error);
            this.updateStatus(`Error: ${event.error}`, 'error');
            this.stopRecording();
        };

        this.recognition.onend = () => {
            this.isRecording = false;
            this.updateStatus('Recording stopped', 'stopped');
            this.startBtn.disabled = false;
            this.stopBtn.disabled = true;
            this.recordingIndicator.classList.add('hidden');
        };
    }

    async loadAvailableTests() {
        try {
            const response = await fetch('/api/tests');
            if (response.ok) {
                this.availableTests = await response.json();
                this.renderAvailableTests();
            } else {
                console.error('Failed to load tests:', response.status);
            }
        } catch (error) {
            console.error('Failed to load available tests:', error);
        }
    }

    renderAvailableTests() {
        if (!this.availableTestsContainer) {
            console.error('Available tests container not found');
            return;
        }
        
        this.availableTestsContainer.innerHTML = '';
        
        this.availableTests.forEach(test => {
            const testCard = document.createElement('div');
            testCard.className = 'test-card';
            testCard.innerHTML = `
                <div class="test-card-name">${test.name}</div>
                <div class="test-card-category">${test.category}</div>
            `;
            
            testCard.addEventListener('click', () => {
                testCard.classList.toggle('selected');
            });
            
            this.availableTestsContainer.appendChild(testCard);
        });
    }

    startRecording() {
        if (this.recognition && !this.isRecording) {
            this.recognition.start();
        }
    }

    stopRecording() {
        if (this.recognition && this.isRecording) {
            this.recognition.stop();
        }
    }

    clearAll() {
        this.finalTranscriptText = '';
        this.currentTranscript = '';
        this.updateLiveTranscript('');
        this.updateFinalTranscript('');
        this.allDetectedTests.clear();
        this.clearTestResults();
        this.chunkQueue = [];
    }

    updateStatus(message, type = 'info') {
        if (this.status) {
            this.status.textContent = message;
            this.status.className = `status ${type}`;
        }
    }

    updateLiveTranscript(text) {
        if (!this.liveTranscript) return;
        
        if (text.trim()) {
            this.liveTranscript.innerHTML = `<span class="live-text">${text}</span>`;
            this.liveTranscript.classList.add('has-content');
        } else {
            this.liveTranscript.innerHTML = '<span class="placeholder">Speech will appear here...</span>';
            this.liveTranscript.classList.remove('has-content');
        }
    }

    updateFinalTranscript(text) {
        if (!this.finalTranscript) return;
        
        if (text.trim()) {
            this.finalTranscript.innerHTML = `<span class="final-text">${text}</span>`;
            this.finalTranscript.classList.add('has-content');
        } else {
            this.finalTranscript.innerHTML = '<span class="placeholder">Final transcript will appear here...</span>';
            this.finalTranscript.classList.remove('has-content');
        }
    }

    async processSpeechChunk(chunk) {
        if (!chunk.trim()) return;

        this.chunkQueue.push(chunk);
        
        if (!this.processingChunks) {
            this.processingChunks = true;
            if (this.processingStatus) {
                this.processingStatus.classList.remove('hidden');
            }
            
            // Process chunks with a small delay to allow for batching
            setTimeout(() => {
                this.processChunkQueue();
            }, 500);
        }
    }

    async processChunkQueue() {
        if (this.chunkQueue.length === 0) {
            this.processingChunks = false;
            if (this.processingStatus) {
                this.processingStatus.classList.add('hidden');
            }
            return;
        }

        const chunks = [...this.chunkQueue];
        this.chunkQueue = [];

        try {
            // Process all chunks in parallel
            const promises = chunks.map(chunk => this.callMatchAPI(chunk));
            const results = await Promise.all(promises);

            // Merge new detections and handle removals
            results.forEach(result => {
                if (result) {
                    // Add newly detected tests
                    if (result.detected_tests) {
                        result.detected_tests.forEach(test => this.allDetectedTests.add(test));
                    }
                    // Remove negated/cancelled tests
                    if (result.removed_tests) {
                        result.removed_tests.forEach(test => this.allDetectedTests.delete(test));
                    }
                }
            });

            // Update display with all accumulated tests
            this.updateTestResults(Array.from(this.allDetectedTests));

        } catch (error) {
            console.error('Error processing speech chunks:', error);
        }

        // Continue processing remaining chunks
        setTimeout(() => {
            this.processChunkQueue();
        }, 100);
    }

    async callMatchAPI(transcript) {
        try {
            console.log('Calling match API with:', transcript);
            const response = await fetch('/match_stream', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ transcript })
            });

            if (response.ok) {
                const result = await response.json();
                console.log('API response:', result);
                return result;
            } else {
                console.error('API call failed:', response.status, response.statusText);
                return null;
            }
        } catch (error) {
            console.error('Error calling match API:', error);
            return null;
        }
    }

    updateTestResults(detectedTests) {
        if (!this.testResults) return;
        
        if (detectedTests.length === 0) {
            this.testResults.innerHTML = `
                <div class="no-results">
                    <span class="icon">🔍</span>
                    <p>No tests detected yet. Start speaking to see results.</p>
                </div>
            `;
            return;
        }

        const resultsHTML = detectedTests.map(testName => {
            const test = this.availableTests.find(t => t.name === testName);
            const category = test ? test.category : 'unknown';
            
            return `
                <div class="test-item fade-in">
                    <div class="test-info">
                        <div class="test-name">${testName}</div>
                        <div class="test-category">${category}</div>
                    </div>
                    <div class="test-confidence">Detected</div>
                </div>
            `;
        }).join('');

        this.testResults.innerHTML = resultsHTML;
    }

    clearTestResults() {
        if (!this.testResults) return;
        
        this.testResults.innerHTML = `
            <div class="no-results">
                <span class="icon">🔍</span>
                <p>No tests detected yet. Start speaking to see results.</p>
            </div>
        `;
    }
}

// Initialize the app when the page loads
document.addEventListener('DOMContentLoaded', () => {
    console.log('Initializing Speech Recognition App...');
    new SpeechRecognitionApp();
});