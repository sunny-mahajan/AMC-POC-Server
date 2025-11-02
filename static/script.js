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
        this.matchThreshold = 0.75; // Default threshold (75%)

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

        // New elements for categorized view
        this.categoryList = document.getElementById('categoryList');
        this.testSearch = document.getElementById('testSearch');
        this.gridViewBtn = document.getElementById('gridViewBtn');
        this.listViewBtn = document.getElementById('listViewBtn');
        this.testCount = document.getElementById('testCount');
        this.settingsBtn = document.getElementById('settingsBtn');
        this.settingsModal = document.getElementById('settingsModal');
        this.settingsModalCloseBtn = document.getElementById('settingsModalCloseBtn');
        this.thresholdSlider = document.getElementById('thresholdSlider');
        this.thresholdValue = document.getElementById('thresholdValue');
        this.generateEmbeddingsBtn = document.getElementById('generateEmbeddingsBtn');
        this.embeddingsStatus = document.getElementById('embeddingsStatus');

        // State for filtering
        this.selectedCategory = 'All';
        this.searchQuery = '';
        this.viewMode = 'grid'; // 'grid' or 'list'
    }

    setupEventListeners() {
        this.startBtn.addEventListener('click', () => this.startRecording());
        this.stopBtn.addEventListener('click', () => this.stopRecording());
        this.clearBtn.addEventListener('click', () => this.clearAll());

        // Search functionality
        if (this.testSearch) {
            this.testSearch.addEventListener('input', (e) => {
                this.searchQuery = e.target.value.toLowerCase();
                this.renderAvailableTests();
            });
        }

        // View toggle
        if (this.gridViewBtn) {
            this.gridViewBtn.addEventListener('click', () => {
                this.viewMode = 'grid';
                this.gridViewBtn.classList.add('active');
                this.listViewBtn.classList.remove('active');
                this.availableTestsContainer.classList.remove('list-view');
            });
        }

        if (this.listViewBtn) {
            this.listViewBtn.addEventListener('click', () => {
                this.viewMode = 'list';
                this.listViewBtn.classList.add('active');
                this.gridViewBtn.classList.remove('active');
                this.availableTestsContainer.classList.add('list-view');
            });
        }

        // Engine selection
        this.engineRadios.forEach(radio => {
            radio.addEventListener('change', (e) => {
                this.currentEngine = e.target.value;
                console.log('Switched to:', this.currentEngine);
            });
        });

        // Modal event listeners
        this.modalCloseBtn.addEventListener('click', () => this.closeSynonymModal());
        this.synonymModal.addEventListener('click', (e) => {
            if (e.target === this.synonymModal) {
                this.closeSynonymModal();
            }
        });

        // Settings modal event listeners
        if (this.settingsBtn) {
            this.settingsBtn.addEventListener('click', () => this.openSettingsModal());
        }
        if (this.settingsModalCloseBtn) {
            this.settingsModalCloseBtn.addEventListener('click', () => this.closeSettingsModal());
        }
        if (this.settingsModal) {
            this.settingsModal.addEventListener('click', (e) => {
                if (e.target === this.settingsModal) {
                    this.closeSettingsModal();
                }
            });
        }

        // Generate embeddings button
        if (this.generateEmbeddingsBtn) {
            this.generateEmbeddingsBtn.addEventListener('click', () => this.generateEmbeddings());
        }

        // Cleanup on page unload
        window.addEventListener('beforeunload', () => {
            this.cleanup();
        });

        // Settings handlers
        this.initializeSettings();
    }

    initializeSettings() {
        // Load threshold from localStorage or use default
        const savedThreshold = localStorage.getItem('matchThreshold');
        if (savedThreshold !== null) {
            this.matchThreshold = parseFloat(savedThreshold);
            this.thresholdSlider.value = (this.matchThreshold * 100).toString();
            this.updateThresholdDisplay();
        }

        // Threshold slider handler
        if (this.thresholdSlider) {
            this.thresholdSlider.addEventListener('input', (e) => {
                const percentageValue = parseInt(e.target.value);
                this.matchThreshold = percentageValue / 100; // Convert to 0-1 range
                this.updateThresholdDisplay();
                // Save to localStorage
                localStorage.setItem('matchThreshold', this.matchThreshold.toString());
            });
        }
    }

    openSettingsModal() {
        if (this.settingsModal) {
            this.settingsModal.classList.add('show');
        }
    }

    closeSettingsModal() {
        if (this.settingsModal) {
            this.settingsModal.classList.remove('show');
        }
    }

    updateThresholdDisplay() {
        if (this.thresholdValue) {
            const percentage = Math.round(this.matchThreshold * 100);
            this.thresholdValue.textContent = `${percentage}%`;
        }
    }

    async initializeMicrophone() {
        try {
            this.updateStatus('Initializing microphone...', 'info');

            // Check if getUserMedia is supported
            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                throw new Error('Your browser does not support microphone access. Please use a modern browser like Chrome, Firefox, or Edge.');
            }

            this.mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
            this.updateStatus('Ready to record', 'info');
        } catch (error) {
            console.error('Microphone error:', error);

            let errorMessage = 'Microphone error: ';
            if (error.name === 'NotAllowedError' || error.name === 'PermissionDeniedError') {
                errorMessage += 'Permission denied. Please allow microphone access in your browser settings.';
            } else if (error.name === 'NotFoundError' || error.name === 'DevicesNotFoundError') {
                errorMessage += 'No microphone found. Please connect a microphone and reload the page.';
            } else if (error.name === 'NotReadableError' || error.name === 'TrackStartError') {
                errorMessage += 'Microphone is already in use by another application.';
            } else {
                errorMessage += error.message || 'Unknown error occurred.';
            }

            this.updateStatus(errorMessage, 'error');
            this.showMicrophoneError(errorMessage);
            this.startBtn.disabled = true;
        }
    }

    showMicrophoneError(message) {
        // Show error in the speech section
        const errorDiv = document.createElement('div');
        errorDiv.className = 'microphone-error';
        errorDiv.style.cssText = `
            background: #fee;
            border: 2px solid #f44;
            border-radius: 10px;
            padding: 15px;
            margin-top: 15px;
            color: #c00;
            font-weight: 600;
        `;
        errorDiv.innerHTML = `
            <div style="display: flex; align-items: center; gap: 10px;">
                <span style="font-size: 1.5rem;">🎤</span>
                <div>
                    <strong>Microphone Not Available</strong>
                    <p style="margin: 5px 0 0 0; font-weight: normal;">${message}</p>
                </div>
            </div>
        `;

        const speechSection = document.querySelector('.speech-section');
        if (speechSection) {
            // Remove any existing error
            const existingError = speechSection.querySelector('.microphone-error');
            if (existingError) {
                existingError.remove();
            }
            speechSection.insertBefore(errorDiv, speechSection.firstChild);
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

    renderCategories() {
        if (!this.categoryList) return;

        // Get unique categories with counts
        const categories = {};
        this.availableTests.forEach(test => {
            if (!categories[test.category]) {
                categories[test.category] = 0;
            }
            categories[test.category]++;
        });

        // Add "All" category
        const totalCount = this.availableTests.length;

        // Clear and render
        this.categoryList.innerHTML = '';

        // All category
        const allCategory = this.createCategoryItem('All', totalCount, this.selectedCategory === 'All');
        this.categoryList.appendChild(allCategory);

        // Sort and add other categories
        Object.keys(categories).sort().forEach(category => {
            const categoryItem = this.createCategoryItem(category, categories[category], this.selectedCategory === category);
            this.categoryList.appendChild(categoryItem);
        });
    }

    createCategoryItem(name, count, isActive) {
        const item = document.createElement('div');
        item.className = `category-item${isActive ? ' active' : ''}`;
        item.innerHTML = `
            <span class="category-name">${name}</span>
            <span class="category-count">${count}</span>
        `;

        item.addEventListener('click', () => {
            this.selectedCategory = name;
            this.renderCategories();
            this.renderAvailableTests();
        });

        return item;
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

        // Filter tests by category and search
        let filteredTests = this.availableTests;

        // Filter by category
        if (this.selectedCategory !== 'All') {
            filteredTests = filteredTests.filter(test => test.category === this.selectedCategory);
        }

        // Filter by search query
        if (this.searchQuery) {
            filteredTests = filteredTests.filter(test =>
                test.name.toLowerCase().includes(this.searchQuery) ||
                test.category.toLowerCase().includes(this.searchQuery) ||
                (test.synonyms && test.synonyms.some(s => s.toLowerCase().includes(this.searchQuery)))
            );
        }

        // Update test count
        if (this.testCount) {
            this.testCount.textContent = `(${filteredTests.length})`;
        }

        // Render filtered tests
        if (filteredTests.length === 0) {
            this.availableTestsContainer.innerHTML = '<div class="no-results"><p>No tests found matching your criteria.</p></div>';
            return;
        }

        filteredTests.forEach(test => {
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

        // Render categories
        this.renderCategories();
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
            console.log('Calling match API with:', transcript, 'threshold:', this.matchThreshold);
            const response = await fetch('/match_stream', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ 
                    transcript,
                    threshold: this.matchThreshold
                })
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

    closeSynonymModal() {
        this.synonymModal.classList.remove('show');
    }

    async generateEmbeddings() {
        if (!this.generateEmbeddingsBtn || !this.embeddingsStatus) return;

        // Show loader and disable button
        const btnText = this.generateEmbeddingsBtn.querySelector('.btn-text');
        const btnLoader = this.generateEmbeddingsBtn.querySelector('.btn-loader');

        btnText.classList.add('hidden');
        btnLoader.classList.remove('hidden');
        this.generateEmbeddingsBtn.disabled = true;

        // Hide previous status
        this.embeddingsStatus.classList.add('hidden');
        this.embeddingsStatus.className = 'embeddings-status hidden';

        try {
            const response = await fetch('/generate_embeddings', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            });

            if (response.ok) {
                const result = await response.json();

                // Show success message
                this.embeddingsStatus.classList.remove('hidden');
                this.embeddingsStatus.classList.add('success');
                this.embeddingsStatus.innerHTML = `
                    <span style="font-size: 1.2rem;">✓</span>
                    <span>${result.message || 'Embeddings generated successfully!'}</span>
                `;

                // Reload available tests
                await this.loadAvailableTests();

                // Hide success message after 5 seconds
                setTimeout(() => {
                    this.embeddingsStatus.classList.add('hidden');
                }, 5000);
            } else {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to generate embeddings');
            }
        } catch (error) {
            console.error('Error generating embeddings:', error);

            // Show error message
            this.embeddingsStatus.classList.remove('hidden');
            this.embeddingsStatus.classList.add('error');
            this.embeddingsStatus.innerHTML = `
                <span style="font-size: 1.2rem;">✗</span>
                <span>${error.message || 'Failed to generate embeddings. Please try again.'}</span>
            `;

            // Hide error message after 8 seconds
            setTimeout(() => {
                this.embeddingsStatus.classList.add('hidden');
            }, 8000);
        } finally {
            // Reset button state
            btnText.classList.remove('hidden');
            btnLoader.classList.add('hidden');
            this.generateEmbeddingsBtn.disabled = false;
        }
    }
}

// Initialize the app when the page loads
document.addEventListener('DOMContentLoaded', () => {
    console.log('Initializing Speech Recognition App with dual engine support...');
    new SpeechRecognitionApp();
});
