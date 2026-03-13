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
    
    // Generate a simple unique session ID for the conversational loop
    const sessionId = "session_" + Math.random().toString(36).substring(2, 10);

    // Web Speech API for native browser transcription (Overrides Hardcoded backend string)
    let finalTranscript = "";
    let interimTranscript = "";
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    let recognition = null;
    
    if (SpeechRecognition) {
        recognition = new SpeechRecognition();
        recognition.continuous = true;
        recognition.interimResults = true;
        
        recognition.onresult = (event) => {
            interimTranscript = '';
            for (let i = event.resultIndex; i < event.results.length; ++i) {
                if (event.results[i].isFinal) {
                    finalTranscript += event.results[i][0].transcript;
                } else {
                    interimTranscript += event.results[i][0].transcript;
                }
            }
            // Show live typing
            statusText.textContent = 'Listening: ' + (finalTranscript + interimTranscript);
        };
        
        recognition.onerror = (event) => {
            console.error("Speech recognition error", event.error);
        };
    }

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
        
        finalTranscript = "";
        interimTranscript = "";
        if (recognition) {
            try { recognition.start(); } catch(e){}
        }
        
        recordBtn.classList.add('recording');
        statusText.textContent = "Listening...";
    }
    
    function stopRecording() {
        if (!mediaRecorder || mediaRecorder.state !== 'recording') return;
        mediaRecorder.stop();
        
        if (recognition) {
            try { recognition.stop(); } catch(e){}
        }
        
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
        
        // Fix for Javascript Async Race Condition:
        // Wait 800ms to ensure the browser's SpeechRecognition engine has time 
        // to fire its final 'onresult' event before we grab the string!
        await new Promise(r => setTimeout(r, 800));
        
        let combinedTranscript = (finalTranscript + interimTranscript).trim();
        
        // Inject context metadata AND real transcript
        // (In a real app, this comes from the current Clinic Dashboard view)
        const metadata = {
            session_id: sessionId,
            incident_id: "HACKATHON-DEMO-001",
            device_id: "Unknown Device",
            reporter: "Web Copilot Frontend",
            description: combinedTranscript // Passes to backend via multi-turn slot schema
        };
        formData.append('metadata', JSON.stringify(metadata));
        
        try {
            // Loading State UI Update
            transcriptOut.innerHTML += `<div class="chat-bubble chat-user"><span class="placeholder-text">Audio sent, waiting for analysis...</span></div>`;
            transcriptOut.scrollTop = transcriptOut.scrollHeight;
            
            // Clear downstream panels if this is an active conversation
            decisionOut.innerHTML = "<span class='placeholder-text'>Analyzing manual DB...</span>";
            opStatusOut.innerHTML = "<span class='placeholder-text'>Hardware impact and routing will appear here...</span>";
            staffImpactOut.innerHTML = "<span class='placeholder-text'>Role-based assignments will appear here...</span>";
            
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
        // 1. Conversation History Updates
        if (data.history && data.history.length > 0) {
            let historyHtml = "";
            data.history.forEach(msg => {
                const bubbleClass = msg.role === 'user' ? 'chat-user' : 'chat-assistant';
                const roleLabel = msg.role === 'user' ? 'You' : 'Copilot';
                historyHtml += `
                    <div class="chat-bubble ${bubbleClass}">
                        <div class="chat-role">${roleLabel}</div>
                        <div>${msg.text}</div>
                    </div>
                `;
            });
            transcriptOut.innerHTML = historyHtml;
            transcriptOut.scrollTop = transcriptOut.scrollHeight;
        }

        // 2. Extracted Slots Update
        const slotsOut = document.getElementById('slotsOutput');
        if (slotsOut && data.extracted_slots) {
            const slots = data.extracted_slots;
            
            const renderSlot = (label, value) => {
                const isMissing = value === null || value === undefined;
                const valueHtml = isMissing 
                    ? `<span class="slot-missing">Missing</span>`
                    : `<span class="slot-filled">${value}</span>`;
                return `
                    <div class="slot-row">
                        <span class="slot-label">${label}</span>
                        <span class="slot-value">${valueHtml}</span>
                    </div>
                `;
            };
            
            slotsOut.innerHTML = `
                ${renderSlot("Reporter Role", slots.reported_by_role)}
                ${renderSlot("Room/Location", slots.room)}
                ${renderSlot("Machine", slots.machine)}
                ${renderSlot("Problem", slots.problem)}
            `;
        }

        // If still clarifying, we do NOT render the heavy AI pipeline panels yet.
        if (data.status === "clarifying") {
            decisionOut.innerHTML = "<span class='placeholder-text'>Waiting for missing details before triggering manuals...</span>";
        } 
        else if (data.status === "complete") {
            // 3. Decision Logic
            let decisionHtml = "";
            const payload = data.pipeline_handoff_payload;
            
            if (payload && payload.escalate) {
                decisionHtml += `<div class="escalate-badge">🚨 ESCALATION REQUIRED: ${payload.escalation_reason}</div>`;
            }
            
            if (payload && payload.recommended_actions && payload.recommended_actions.length > 0) {
                payload.recommended_actions.forEach(action => {
                    decisionHtml += `<div class="action-item">${action}</div>`;
                });
            }
            decisionOut.innerHTML = decisionHtml || "<span class='placeholder-text'>No actions required.</span>";
            
            // 4. Operational Status
            let opHtml = "";
            const downtime = payload ? (payload.downtime_bucket || "unknown") : "unknown";
            
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
                    <span class="op-label">Reroute:</span> ${payload ? (payload.reroute_recommendation || "N/A") : "N/A"}
                </div>
                <div class="op-row" style="margin-top: 1rem; padding-top: 1rem; border-top: 1px solid var(--border);">
                    <div class="op-label" style="display: block; margin-bottom: 0.5rem;">Staff Broadcast:</div>
                    <div class="placeholder-text" style="color: var(--text-primary); font-style: normal;">
                        "${payload ? (payload.staff_notification || "No broadcast needed.") : "No broadcast needed."}"
                    </div>
                </div>
            `;
            opStatusOut.innerHTML = opHtml;
            
            // 5. Staff Impact
            let staffHtml = "";
            const reporter = payload ? payload.reported_by_role : null;
            if (reporter) {
                staffHtml += `
                    <div class="op-row" style="margin-bottom: 1.5rem;">
                        <span class="op-label">Reported by:</span> ${reporter.role} (${reporter.location})
                    </div>
                `;
            }
            
            const affected = payload ? payload.affected_roles : null;
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
        }
        
        // 6. Play Base64 Audio natively OR fallback to browser TTS (Offline Hackathon Mode)
        if (data.spoken_response_base64) {
            const audioSrc = `data:audio/mp3;base64,${data.spoken_response_base64}`;
            player.src = audioSrc;
            player.play().catch(e => console.error("Audio auto-play blocked by browser policy:", e));
        } else if (data.final_text_response && 'speechSynthesis' in window) {
            // Cancel any ongoing speech
            window.speechSynthesis.cancel();
            const utterance = new SpeechSynthesisUtterance(data.final_text_response);
            window.speechSynthesis.speak(utterance);
        }
    }
});
