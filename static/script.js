class SpeechRecognitionApp {
    constructor() {
        // Deepgram configuration
        this.DEEPGRAM_API_KEY = null;
        this.deepgramClient = null;
        this.deepgramConnection = null;
        this.mediaStream = null;
        this.audioContext = null;
        this.audioProcessor = null;

        // Web Speech API
        this.webSpeechRecognition = null;

        // Current engine ('deepgram' or 'webspeech')
        this.currentEngine = 'deepgram';

        // State management
        this.isRecording = false;
        this.currentTranscript = '';
        this.finalTranscriptText = '';
        this.interimText = '';
        this.chunkQueue = [];
        this.processingChunks = false;
        this.availableTests = [];
        this.allDetectedTests = new Set();

        this.initializeElements();
        this.setupEventListeners();
        this.loadConfig();
        this.loadAvailableTests();
        this.initializeMicrophone();
        this.initializeWebSpeech();
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
        this.synonymModal = document.getElementById('synonymModal');
        this.modalTestName = document.getElementById('modalTestName');
        this.modalSynonymsList = document.getElementById('modalSynonymsList');
        this.modalCloseBtn = document.getElementById('modalCloseBtn');
        this.engineRadios = document.querySelectorAll('input[name="speechEngine"]');
    }

    setupEventListeners() {
        this.startBtn.addEventListener('click', () => this.startRecording());
        this.stopBtn.addEventListener('click', () => this.stopRecording());
        this.clearBtn.addEventListener('click', () => this.clearAll());

        // Engine selection
        this.engineRadios.forEach(radio => {
            radio.addEventListener('change', (e) => {
                this.currentEngine = e.target.value;
                console.log('Switched to:', this.currentEngine);
            });
        });

        // Modal event listeners
        this.modalCloseBtn.addEventListener('click', () => this.closeModal());
        this.synonymModal.addEventListener('click', (e) => {
            if (e.target === this.synonymModal) {
                this.closeModal();
            }
        });

        // Cleanup on page unload
        window.addEventListener('beforeunload', () => {
            this.cleanup();
        });
    }

    async initializeMicrophone() {
        try {
            this.updateStatus('Initializing microphone...', 'info');
            this.mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
            this.updateStatus('Ready to record', 'info');
        } catch (error) {
            console.error('Microphone permission denied:', error);
            this.updateStatus('Microphone permission required', 'error');
            this.startBtn.disabled = true;
        }
    }

    async loadConfig() {
        try {
            const response = await fetch('/api/config');
            if (response.ok) {
                const config = await response.json();
                this.DEEPGRAM_API_KEY = config.deepgram_api_key;
                console.log('Configuration loaded successfully');
            } else {
                console.error('Failed to load configuration:', response.status);
            }
        } catch (error) {
            console.error('Failed to load configuration:', error);
        }
    }

    initializeWebSpeech() {
        if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
            console.warn('Web Speech API not supported in this browser');
            return;
        }

        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        this.webSpeechRecognition = new SpeechRecognition();

        this.webSpeechRecognition.continuous = true;
        this.webSpeechRecognition.interimResults = true;
        this.webSpeechRecognition.lang = 'en-US';

        this.webSpeechRecognition.onstart = () => {
            this.isRecording = true;
            this.updateStatus('Listening... (Web Speech API)', 'recording');
            this.startBtn.disabled = true;
            this.stopBtn.disabled = false;
            this.recordingIndicator.classList.remove('hidden');
        };

        this.webSpeechRecognition.onresult = (event) => {
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

        this.webSpeechRecognition.onerror = (event) => {
            console.error('Web Speech recognition error:', event.error);
            this.updateStatus(`Error: ${event.error}`, 'error');
            this.stopRecording();
        };

        this.webSpeechRecognition.onend = () => {
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
                const data = await response.json();
                // Ensure we have an array, handle error responses
                if (Array.isArray(data)) {
                    this.availableTests = data;
                } else if (data.error) {
                    console.error('API returned error:', data.error);
                    this.availableTests = []; // Set to empty array on error
                } else {
                    console.warn('Unexpected response format, defaulting to empty array');
                    this.availableTests = [];
                }
                this.renderAvailableTests();
            } else {
                console.error('Failed to load tests:', response.status);
                this.availableTests = []; // Ensure it's an array even on error
            }
        } catch (error) {
            console.error('Failed to load available tests:', error);
            this.availableTests = []; // Ensure it's an array even on error
        }
    }

    renderAvailableTests() {
        if (!this.availableTestsContainer) {
            console.error('Available tests container not found');
            return;
        }

        this.availableTestsContainer.innerHTML = '';

        // Ensure availableTests is an array before iterating
        if (!Array.isArray(this.availableTests)) {
            console.warn('availableTests is not an array:', this.availableTests);
            return;
        }

        this.availableTests.forEach(test => {
            const testCard = document.createElement('div');
            testCard.className = 'test-card';
            testCard.innerHTML = `
                <div class="test-card-name">${test.name}</div>
                <div class="test-card-category">${test.category}</div>
            `;

            testCard.addEventListener('click', () => {
                this.showSynonyms(test);
            });

            this.availableTestsContainer.appendChild(testCard);
        });
    }

    async startRecording() {
        if (this.currentEngine === 'deepgram') {
            await this.startDeepgramRecording();
        } else {
            this.startWebSpeechRecording();
        }
    }

    startWebSpeechRecording() {
        if (!this.webSpeechRecognition) {
            this.updateStatus('Web Speech API not supported', 'error');
            return;
        }

        if (!this.isRecording) {
            this.webSpeechRecognition.start();
        }
    }

    async startDeepgramRecording() {
        if (!this.DEEPGRAM_API_KEY) {
            this.updateStatus('Deepgram API key not configured', 'error');
            return;
        }

        if (!this.mediaStream) {
            await this.initializeMicrophone();
            if (!this.mediaStream) return;
        }

        try {
            this.updateStatus('Connecting to Deepgram...', 'info');

            // Initialize Deepgram client
            const { createClient, LiveTranscriptionEvents } = deepgram;
            this.deepgramClient = createClient(this.DEEPGRAM_API_KEY);

            // Create live transcription connection
            this.deepgramConnection = this.deepgramClient.listen.live({
                model: 'nova-2-medical',
                language: 'en',
                smart_format: true,
                interim_results: true,
                punctuate: true,
                diarize: false,
                encoding: 'linear16',
                sample_rate: 48000,
                channels: 1
            });

            // Connection opened
            this.deepgramConnection.on(LiveTranscriptionEvents.Open, () => {
                this.isRecording = true;
                this.updateStatus('Listening... (Deepgram Medical)', 'recording');
                this.startBtn.disabled = true;
                this.stopBtn.disabled = false;
                this.recordingIndicator.classList.remove('hidden');
            });

            // Handle transcription results
            this.deepgramConnection.on(LiveTranscriptionEvents.Transcript, (data) => {
                const transcript = data.channel.alternatives[0];
                if (transcript && transcript.transcript) {
                    const isFinal = data.is_final;
                    const text = transcript.transcript;

                    if (isFinal) {
                        // Final transcript
                        this.finalTranscriptText += (this.finalTranscriptText ? ' ' : '') + text;
                        this.interimText = '';
                        this.currentTranscript = this.finalTranscriptText;
                        this.updateFinalTranscript(this.finalTranscriptText);
                        this.updateLiveTranscript(this.currentTranscript);

                        // Process the final transcript chunk
                        if (text.trim()) {
                            this.processSpeechChunk(text.trim());
                        }
                    } else {
                        // Interim transcript
                        this.interimText = text;
                        this.currentTranscript = this.finalTranscriptText +
                            (this.finalTranscriptText ? ' ' : '') + this.interimText;
                        this.updateLiveTranscript(this.currentTranscript);
                    }
                }
            });

            // Handle errors
            this.deepgramConnection.on(LiveTranscriptionEvents.Error, (error) => {
                console.error('Deepgram error:', error);
                this.updateStatus('Connection error occurred', 'error');
            });

            // Handle connection close
            this.deepgramConnection.on(LiveTranscriptionEvents.Close, () => {
                this.isRecording = false;
                this.updateStatus('Recording stopped', 'stopped');
                this.startBtn.disabled = false;
                this.stopBtn.disabled = true;
                this.recordingIndicator.classList.add('hidden');
            });

            // Setup audio processing
            this.setupAudioProcessing();

        } catch (error) {
            console.error('Error starting Deepgram recording:', error);
            this.updateStatus(`Error: ${error.message}`, 'error');
            this.startBtn.disabled = false;
        }
    }

    setupAudioProcessing() {
        // Create AudioContext for processing
        this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
        const source = this.audioContext.createMediaStreamSource(this.mediaStream);
        this.audioProcessor = this.audioContext.createScriptProcessor(4096, 1, 1);

        source.connect(this.audioProcessor);
        this.audioProcessor.connect(this.audioContext.destination);

        this.audioProcessor.onaudioprocess = (e) => {
            if (this.deepgramConnection && this.deepgramConnection.getReadyState() === 1) {
                const inputData = e.inputBuffer.getChannelData(0);

                // Convert Float32Array to Int16Array
                const int16Data = new Int16Array(inputData.length);
                for (let i = 0; i < inputData.length; i++) {
                    const s = Math.max(-1, Math.min(1, inputData[i]));
                    int16Data[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
                }

                this.deepgramConnection.send(int16Data.buffer);
            }
        };
    }

    stopRecording() {
        if (this.currentEngine === 'deepgram') {
            this.stopDeepgramRecording();
        } else {
            this.stopWebSpeechRecording();
        }
    }

    stopWebSpeechRecording() {
        if (this.webSpeechRecognition && this.isRecording) {
            this.webSpeechRecognition.stop();
        }
    }

    stopDeepgramRecording() {
        if (this.audioContext) {
            this.audioContext.close();
            this.audioContext = null;
        }

        if (this.audioProcessor) {
            this.audioProcessor.disconnect();
            this.audioProcessor = null;
        }

        if (this.deepgramConnection) {
            this.deepgramConnection.finish();
            this.deepgramConnection = null;
        }

        this.isRecording = false;
        this.startBtn.disabled = false;
        this.stopBtn.disabled = true;
        this.recordingIndicator.classList.add('hidden');
        this.updateStatus('Ready to record', 'info');
    }

    cleanup() {
        if (this.mediaStream) {
            this.mediaStream.getTracks().forEach(track => track.stop());
            this.mediaStream = null;
        }
        this.stopDeepgramRecording();
        this.stopWebSpeechRecording();
    }

    clearAll() {
        this.finalTranscriptText = '';
        this.currentTranscript = '';
        this.interimText = '';
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
                    // Add newly detected tests with metadata
                    if (result.detected_tests) {
                        result.detected_tests.forEach(test => {
                            // Store test with metadata (name, method, score)
                            const existingTest = Array.from(this.allDetectedTests).find(t => t.name === test.name);
                            if (!existingTest) {
                                this.allDetectedTests.add(test);
                            } else if (test.score && (!existingTest.score || test.score > existingTest.score)) {
                                // Update if new score is higher
                                this.allDetectedTests.delete(existingTest);
                                this.allDetectedTests.add(test);
                            }
                        });
                    }
                    // Remove negated/cancelled tests
                    if (result.removed_tests) {
                        result.removed_tests.forEach(testName => {
                            const testToRemove = Array.from(this.allDetectedTests).find(t => t.name === testName);
                            if (testToRemove) {
                                this.allDetectedTests.delete(testToRemove);
                            }
                        });
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

        const resultsHTML = detectedTests.map(testData => {
            const testName = testData.name || testData;
            const method = testData.method || 'unknown';
            const score = testData.score;

            // Ensure availableTests is an array before calling find
            const test = Array.isArray(this.availableTests) ? 
                this.availableTests.find(t => t.name === testName) : null;
            const category = test ? test.category : 'unknown';

            // Format method badge
            const methodBadge = method === 'embedding' ?
                `<span class="method-badge embedding">Embedding</span>` :
                `<span class="method-badge llm">LLM</span>`;

            // Format score if available
            const scoreDisplay = score ?
                `<span class="confidence-score">${(score * 100).toFixed(0)}%</span>` : '';

            return `
                <div class="test-item fade-in">
                    <div class="test-info">
                        <div class="test-name">${testName}</div>
                        <div class="test-metadata">
                            <span class="test-category">${category}</span>
                            ${methodBadge}
                            ${scoreDisplay}
                        </div>
                    </div>
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

    showSynonyms(test) {
        this.modalTestName.textContent = test.name;
        this.modalSynonymsList.innerHTML = '';

        if (test.synonyms && test.synonyms.length > 0) {
            test.synonyms.forEach(synonym => {
                const li = document.createElement('li');
                li.textContent = synonym;
                this.modalSynonymsList.appendChild(li);
            });
        } else {
            const li = document.createElement('li');
            li.textContent = 'No synonyms available';
            li.style.color = '#999';
            this.modalSynonymsList.appendChild(li);
        }

        this.synonymModal.classList.add('show');
    }

    closeModal() {
        this.synonymModal.classList.remove('show');
    }
}

// Initialize the app when the page loads
document.addEventListener('DOMContentLoaded', () => {
    console.log('Initializing Speech Recognition App with dual engine support...');
    new SpeechRecognitionApp();
});
