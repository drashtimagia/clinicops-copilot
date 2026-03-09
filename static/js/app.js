document.addEventListener('DOMContentLoaded', () => {
    
    // UI Elements
    const recordBtn = document.getElementById('recordButton');
    const statusText = document.getElementById('recordingStatus');
    const transcriptOut = document.getElementById('transcriptOutput');
    const decisionOut = document.getElementById('decisionOutput');
    const opStatusOut = document.getElementById('opStatusOutput');
    const staffImpactOut = document.getElementById('staffImpactOutput');
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
        
        decisionOut.innerHTML = decisionHtml || "<span class='placeholder-text'>No actions required.</span>";
        
        // 3. Operational Status
        let opHtml = "";
        const downtime = payload.downtime_bucket || "unknown";
        
        let badgeClass = "badge-available";
        if (downtime.includes("temporarily")) badgeClass = "badge-warning";
        else if (downtime.includes("unavailable")) badgeClass = "badge-danger";
        
        const friendlyDowntime = downtime.replace(/_/g, " ");
        
        opHtml += `
            <div class="op-row">
                <span class="op-label">Downtime:</span>
                <span class="op-badge ${badgeClass}">${friendlyDowntime}</span>
            </div>
            <div class="op-row">
                <span class="op-label">Reroute:</span> ${payload.reroute_recommendation || "N/A"}
            </div>
            <div class="op-row" style="margin-top: 1rem; padding-top: 1rem; border-top: 1px solid var(--border);">
                <div class="op-label" style="display: block; margin-bottom: 0.5rem;">Staff Broadcast:</div>
                <div class="placeholder-text" style="color: var(--text-primary); font-style: normal;">
                    "${payload.staff_notification || "No broadcast needed."}"
                </div>
            </div>
        `;
        opStatusOut.innerHTML = opHtml;
        
        // 4. Staff Impact
        let staffHtml = "";
        
        const reporter = payload.reported_by_role;
        if (reporter) {
            staffHtml += `
                <div class="op-row" style="margin-bottom: 1.5rem;">
                    <span class="op-label">Reported by:</span> ${reporter.role} (${reporter.location})
                </div>
            `;
        }
        
        const affected = payload.affected_roles;
        if (affected && affected.length > 0) {
            staffHtml += `<div class="op-label" style="margin-bottom: 0.5rem; display:block;">Affected Roles:</div>`;
            staffHtml += `<ul class="role-list">`;
            affected.forEach(aff => {
                staffHtml += `
                    <li class="role-item">
                        <div class="role-title">${aff.role}</div>
                        <div class="role-impact">${aff.impact}</div>
                    </li>
                `;
            });
            staffHtml += `</ul>`;
        } else {
            staffHtml += `<div class="placeholder-text">No lateral staff impact detected.</div>`;
        }
        
        staffImpactOut.innerHTML = staffHtml;
        
        // 5. Play Base64 Audio natively
        if (data.spoken_response_base64) {
            const audioSrc = `data:audio/mp3;base64,${data.spoken_response_base64}`;
            player.src = audioSrc;
            player.play().catch(e => console.error("Audio auto-play blocked by browser policy:", e));
        }
    }
});
