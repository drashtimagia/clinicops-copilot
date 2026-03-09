document.addEventListener('DOMContentLoaded', () => {
    
    // UI Elements
    const recordBtn = document.getElementById('recordButton');
    const statusText = document.getElementById('recordingStatus');
    const transcriptOut = document.getElementById('transcriptOutput');
    const decisionOut = document.getElementById('decisionOutput');
    const player = document.getElementById('syntheticAudioPlayer');
    
    let mediaRecorder = null;
    let audioChunks = [];
    
    // Attempt to request mic permissions immediately on load for the hackathon
    navigator.mediaDevices.getUserMedia({ audio: true })
        .then(stream => {
            mediaRecorder = new MediaRecorder(stream);
            
            mediaRecorder.ondataavailable = e => {
                if (e.data.size > 0) audioChunks.push(e.data);
            };
            
            mediaRecorder.onstop = handleAudioSubmit;
        })
        .catch(err => {
            console.error("Mic access denied", err);
            statusText.textContent = "Microphone access denied.";
            statusText.style.color = "var(--danger)";
        });

    // Interaction handlers (Push-to-Talk emulation via mousedown/mouseup)
    recordBtn.addEventListener('mousedown', startRecording);
    recordBtn.addEventListener('mouseup', stopRecording);
    recordBtn.addEventListener('mouseleave', () => {
        if (mediaRecorder && mediaRecorder.state === 'recording') stopRecording();
    });
    
    // Mobile Touch Support
    recordBtn.addEventListener('touchstart', (e) => { e.preventDefault(); startRecording(); });
    recordBtn.addEventListener('touchend', (e) => { e.preventDefault(); stopRecording(); });
    
    
    function startRecording() {
        if (!mediaRecorder) return;
        audioChunks = [];
        mediaRecorder.start();
        recordBtn.classList.add('recording');
        statusText.textContent = "Listening...";
    }
    
    function stopRecording() {
        if (!mediaRecorder || mediaRecorder.state !== 'recording') return;
        mediaRecorder.stop();
        recordBtn.classList.remove('recording');
        statusText.textContent = "Processing incident via Amazon Nova...";
    }
    
    async function handleAudioSubmit() {
        // Construct the Blob (Browser default is typically audio/webm or audio/ogg)
        const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
        
        // Construct FormData payload
        const formData = new FormData();
        
        // We append the blob with a fake extension so the backend parser handles it
        // The backend `process_voice_incident` auto-detects based on this string
        formData.append('audio', audioBlob, 'recording.webm');
        
        // Inject fake hackathon context metadata 
        // (In a real app, this comes from the current Clinic Dashboard view)
        const metadata = {
            incident_id: "HACKATHON-DEMO-001",
            device_id: "Centrifuge C400",
            reporter: "Web Copilot Frontend"
        };
        formData.append('metadata', JSON.stringify(metadata));
        
        try {
            // Loading State UI Update
            transcriptOut.innerHTML = "<span style='color: var(--text-dim)'>Transcribing audio...</span>";
            decisionOut.innerHTML = "<span style='color: var(--text-dim)'>Analyzing manual DB...</span>";
            
            // Execute the REST fetch
            const response = await fetch('/api/v1/voice/incident', {
                method: 'POST',
                body: formData
            });
            
            const result = await response.json();
            
            if (response.ok && result.status === 'success') {
                statusText.textContent = "Analysis Complete";
                renderResults(result.data);
            } else {
                throw new Error(result.message || "Server Error");
            }
            
        } catch (error) {
            console.error(error);
            statusText.textContent = "Error: " + error.message;
            statusText.style.color = "var(--danger)";
        }
    }
    
    function renderResults(data) {
        // 1. Transcript
        transcriptOut.innerHTML = `<div>${data.transcript}</div>`;
        
        // 2. Decision Logic
        let decisionHtml = "";
        
        const payload = data.pipeline_handoff_payload;
        if (payload.escalate) {
            decisionHtml += `<div class="escalate-badge">🚨 ESCALATION REQUIRED: ${payload.escalation_reason}</div>`;
        }
        
        if (payload.recommended_actions && payload.recommended_actions.length > 0) {
            payload.recommended_actions.forEach(action => {
                decisionHtml += `<div class="action-item">${action}</div>`;
            });
        }
        
        decisionOut.innerHTML = decisionHtml;
        
        // 3. Play Base64 Audio natively
        if (data.spoken_response_base64) {
            const audioSrc = `data:audio/mp3;base64,${data.spoken_response_base64}`;
            player.src = audioSrc;
            player.play().catch(e => console.error("Audio auto-play blocked by browser policy:", e));
        }
    }
});
