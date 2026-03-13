<<<<<<< HEAD
import React, { useState, useEffect, useRef } from 'react';
import { Mic, CheckCircle2, AlertCircle, Play, Users, Activity, MessageSquare, ArrowRight } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import axios from 'axios';

const App = () => {
    const [isRecording, setIsRecording] = useState(false);
    const [status, setStatus] = useState('Push to Talk');
    const [history, setHistory] = useState([]);
    const [slots, setSlots] = useState({});
    const [decision, setDecision] = useState(null);
    const [opStatus, setOpStatus] = useState(null);
    const [staffImpact, setStaffImpact] = useState([]);
    const [sessionId] = useState(() => "session_" + Math.random().toString(36).substring(2, 10));

    const audioPlayerRef = useRef(null);
    const mediaRecorderRef = useRef(null);
    const audioChunksRef = useRef([]);

    // Recognition state
    const recognitionRef = useRef(null);
    const transcriptRef = useRef({ final: '', interim: '' }); // use Ref to avoid stale closures in listeners
    const [displayTranscript, setDisplayTranscript] = useState('');

    useEffect(() => {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (SpeechRecognition) {
            const recognition = new SpeechRecognition();
            recognition.continuous = true;
            recognition.interimResults = true;
            recognition.onresult = (event) => {
                let interim = '';
                let final = transcriptRef.current.final;
                for (let i = event.resultIndex; i < event.results.length; ++i) {
                    if (event.results[i].isFinal) {
                        final += event.results[i][0].transcript;
                    } else {
                        interim += event.results[i][0].transcript;
                    }
                }
                transcriptRef.current = { final, interim };
                const fullText = (final + interim).trim();
                setDisplayTranscript(fullText);
                setStatus(fullText || 'Listening...');
            };
            recognitionRef.current = recognition;
        }

        navigator.mediaDevices.getUserMedia({ audio: true })
            .then(stream => {
                const recorder = new MediaRecorder(stream);
                recorder.ondataavailable = e => {
                    if (e.data.size > 0) audioChunksRef.current.push(e.data);
                };
                recorder.onstop = handleAudioSubmit;
                mediaRecorderRef.current = recorder;
            })
            .catch(err => {
                console.error("Mic access denied", err);
                setStatus("Microphone access denied.");
            });
    }, []);

    const startRecording = () => {
        if (!mediaRecorderRef.current) {
            alert("Microphone not initialized. Check permissions.");
            return;
        }
        audioChunksRef.current = [];
        transcriptRef.current = { final: '', interim: '' };
        setDisplayTranscript('');

        mediaRecorderRef.current.start();
        if (recognitionRef.current) {
            try { recognitionRef.current.start(); } catch (e) { }
        }
        setIsRecording(true);
        setStatus("Listening...");
    };

    const stopRecording = () => {
        if (!mediaRecorderRef.current || mediaRecorderRef.current.state !== 'recording') return;
        mediaRecorderRef.current.stop();
        if (recognitionRef.current) {
            try { recognitionRef.current.stop(); } catch (e) { }
        }
        setIsRecording(false);
        setStatus("Analyzing Audio...");
    };

    const handleAudioSubmit = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        const formData = new FormData();
        formData.append('audio', audioBlob, 'recording.webm');

        // Use the final value from the ref to ensure it's not stale
        const combinedTranscript = (transcriptRef.current.final + transcriptRef.current.interim).trim();

        const metadata = {
            session_id: sessionId,
            incident_id: "VOICE-SESSION-REACT",
            device_id: "Contextual Device",
            reporter: "Clinical Staff",
            description: combinedTranscript
        };
        formData.append('metadata', JSON.stringify(metadata));

        try {
            setStatus("Processing Incident...");
            const response = await axios.post('/api/v1/voice/incident', formData);
            const result = response.data;

            if (result.status === 'success') {
                setStatus("Ready");
                renderResults(result.data);
            }
        } catch (error) {
            console.error(error);
            setStatus("Error: " + (error.response?.data?.message || error.message));
        }
    };

    const renderResults = (data) => {
        if (data.history) setHistory(data.history);
        if (data.extracted_slots) setSlots(data.extracted_slots);

        if (data.status === "complete") {
            const payload = data.pipeline_handoff_payload;
            setDecision(payload);
            setOpStatus(payload);
            setStaffImpact(payload.affected_roles || []);
        } else {
            setDecision(null); // Clear panels if clarifying
        }

        if (data.spoken_response_base64) {
            audioPlayerRef.current.src = `data:audio/mp3;base64,${data.spoken_response_base64}`;
            audioPlayerRef.current.play().catch(e => console.error("Audio error", e));
        }
    };

    return (
        <div className="app-shell">
            <div className="glow-bg"></div>

            <header className="navbar glass">
                <div className="brand">
                    <div className="logo-orb"></div>
                    <h1 className="font-outfit">ClinicOps <span className="accent-text">AI Copilot</span></h1>
                </div>
                <div className="status-chip glass-light">
                    <span className="pulse-dot"></span>
                    <span id="backendStatus">Backend Connected</span>
                </div>
            </header>

            <main className="dashboard">
                {/* Left Sidebar: Context */}
                <aside className="sidebar glass">
                    <section className="panel-section">
                        <h2 className="section-title">Case Context</h2>
                        <div className="slot-grid">
                            <SlotItem label="Reporter" value={slots.reported_by_role} />
                            <SlotItem label="Location" value={slots.room} />
                            <SlotItem label="Machine" value={slots.machine} />
                            <SlotItem label="Problem" value={slots.problem} />
                        </div>
                    </section>

                    <section className="panel-section">
                        <h2 className="section-title">Operational Impact</h2>
                        <div className="op-status-list">
                            {opStatus ? (
                                <OpStatusCard data={opStatus} />
                            ) : (
                                <div className="empty-state">Impact will appear after analysis.</div>
                            )}
                        </div>
                    </section>
                </aside>

                {/* Center: Interaction HUD */}
                <div className="interaction-center">
                    <section className="hud-container glass">
                        <div className="voice-hud">
                            <motion.button
                                whileTap={{ scale: 0.9 }}
                                onMouseDown={startRecording}
                                onMouseUp={stopRecording}
                                onMouseLeave={() => isRecording && stopRecording()}
                                className={`voice-orb-btn ${isRecording ? 'recording' : ''}`}
                            >
                                <div className="orb-inner">
                                    <Mic size={48} strokeWidth={2.5} />
                                </div>
                                {isRecording && <div className="orb-pulsar"></div>}
                            </motion.button>
                            <div className="hud-status">{status}</div>
                            {isRecording && (
                                <div className="wave-visualizer">
                                    {[1, 2, 3, 4, 5].map(i => <div key={i} className="bar"></div>)}
                                </div>
                            )}
                        </div>
                    </section>

                    <div className="chat-viewport glass">
                        <div className="conversation-history">
                            <AnimatePresence>
                                {history.length === 0 ? (
                                    <motion.div
                                        initial={{ opacity: 0 }}
                                        animate={{ opacity: 1 }}
                                        className="welcome-message"
                                    >
                                        <h3>👋 Hello! How can I assist you today?</h3>
                                        <p>I can help with medical device troubleshooting, SOP walk-throughs, or incident reporting.</p>
                                    </motion.div>
                                ) : (
                                    history.map((msg, idx) => (
                                        <motion.div
                                            key={idx}
                                            initial={{ opacity: 0, y: 10 }}
                                            animate={{ opacity: 1, y: 0 }}
                                            className={`chat-bubble ${msg.role === 'user' ? 'chat-user' : 'chat-assistant'}`}
                                        >
                                            <div className="chat-role">{msg.role === 'user' ? 'You' : 'AI Copilot'}</div>
                                            <div className="chat-text">{msg.text}</div>
                                        </motion.div>
                                    ))
                                )}
                            </AnimatePresence>
                        </div>
                    </div>
                </div>

                {/* Right Sidebar: Recommendations */}
                <aside className="sidebar sidebar-right glass">
                    <section className="panel-section">
                        <h2 className="section-title">Smart Recommendations</h2>
                        <div className="recommendation-list">
                            {decision ? (
                                <>
                                    {decision.escalate && (
                                        <div className="rec-card high-priority">
                                            <div className="rec-header"><AlertCircle size={16} /> URGENT: Escalation</div>
                                            <div className="rec-body">{decision.escalation_reason}</div>
                                        </div>
                                    )}
                                    {decision.recommended_actions?.map((action, i) => (
                                        <div key={i} className="rec-card">
                                            <div className="rec-header"><Activity size={16} /> Action Required</div>
                                            <div className="rec-body">{action}</div>
                                        </div>
                                    ))}
                                </>
                            ) : (
                                <div className="empty-state">Awaiting incident details...</div>
                            )}
                        </div>
                    </section>

                    <section className="panel-section">
                        <h2 className="section-title">Stakeholders</h2>
                        <div className="staff-impact-area">
                            {staffImpact.length > 0 ? (
                                staffImpact.map((aff, i) => (
                                    <div key={i} className="slot-item border-indigo">
                                        <div className="slot-val brand-blue">{aff.role}</div>
                                        <div className="slot-label text-impact">{aff.impact}</div>
                                    </div>
                                ))
                            ) : (
                                <div className="empty-state">No impact detected yet.</div>
                            )}
                        </div>
                    </section>
                </aside>
            </main>

            <audio ref={audioPlayerRef} hidden />
        </div>
    );
};

const SlotItem = ({ label, value }) => (
    <div className="slot-item">
        <div className="slot-label">{label}</div>
        <div className={`slot-val ${!value ? 'missing' : ''}`}>
            {value || 'Awaiting...'}
        </div>
    </div>
);

const OpStatusCard = ({ data }) => {
    const downtime = data.downtime_bucket || "unknown";
    let badgeClass = "bg-success";
    if (downtime.includes("temporarily") || downtime.includes("reduced")) badgeClass = "bg-warning";
    else if (downtime.includes("unavailable") || downtime.includes("failure")) badgeClass = "bg-danger";

    return (
        <div className="op-status-card">
            <div className="op-header">
                <span className="slot-label">Downtime</span>
                <span className={`status-badge ${badgeClass}`}>{downtime.replace(/_/g, " ")}</span>
            </div>
            <div className="op-info">
                <span className="slot-label">Reroute Recommendation</span>
                <div className="op-text">{data.reroute_recommendation || "Maintain current workflow."}</div>
            </div>
            <div className="broadcast glass-light">
                <span className="slot-label mini">Broadcast Message</span>
                <div className="broadcast-text">"{data.staff_notification || 'No broadcast required.'}"</div>
            </div>
        </div>
    );
};
=======
import React, { useState } from 'react';
import './index.css';
import useCopilot from './hooks/useCopilot';

function App() {
  const {
    statusText,
    isRecording,
    history,
    slots,
    decisionPayload,
    serverStatus,
    startRecording,
    stopRecording,
  } = useCopilot();

  return (
    <div className="app-container">
      <header className="app-header">
        <div className="logo">🧬 ClinicOps Copilot</div>
        <div className="status-indicator">
          <span className="dot active"></span> Backend Connected
        </div>
      </header>

      <main className="content">
        <div className="recording-section">
          <h2>Voice Incident Logger</h2>
          <p>Hold the microphone button and describe the device incident.</p>

          <button
            onMouseDown={startRecording}
            onMouseUp={stopRecording}
            onMouseLeave={stopRecording}
            onTouchStart={(e) => { e.preventDefault(); startRecording(); }}
            onTouchEnd={(e) => { e.preventDefault(); stopRecording(); }}
            className={`mic-button ${isRecording ? 'recording' : ''}`}
          >
            <svg viewBox="0 0 24 24" fill="none" className="mic-icon" stroke="currentColor" strokeWidth="2">
              <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z"></path>
              <path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
              <line x1="12" y1="19" x2="12" y2="22"></line>
            </svg>
          </button>
          <div className="status-text">{statusText}</div>
        </div>

        <div className="results-grid">
          {/* Panel 1: Conversation History */}
          <div className="panel">
            <h3>Conversation</h3>
            <div className="chat-container">
              {history.length === 0 ? (
                <span className="placeholder-text">Audio processing will appear here...</span>
              ) : (
                history.map((msg, idx) => (
                  <div key={idx} className={`chat-bubble ${msg.role === 'user' ? 'chat-user' : 'chat-assistant'}`}>
                    <div className="chat-role">{msg.role === 'user' ? 'You' : 'Copilot'}</div>
                    <div>{msg.text}</div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Panel 2: Extracted Details */}
          <div className="panel">
            <h3>Extracted Details</h3>
            <div className="slot-container">
              {!slots ? (
                <span className="placeholder-text">Listening for problem details...</span>
              ) : (
                <>
                  <SlotRow label="Reporter Role" value={slots.reported_by_role} />
                  <SlotRow label="Room/Location" value={slots.room} />
                  <SlotRow label="Machine" value={slots.machine} />
                  <SlotRow label="Problem" value={slots.problem} />
                </>
              )}
            </div>
          </div>

          {/* Panel 3: Decision Output */}
          <div className="panel">
            <h3>Decision Output</h3>
            <div className="decision-container">
              {serverStatus === 'clarifying' ? (
                <span className="placeholder-text">Waiting for missing details before triggering manuals...</span>
              ) : !decisionPayload ? (
                <span className="placeholder-text">AI Copilot recommendations will appear here...</span>
              ) : (
                <>
                  {decisionPayload.escalate && (
                    <div className="escalate-badge">🚨 ESCALATION REQUIRED: {decisionPayload.escalation_reason}</div>
                  )}
                  {decisionPayload.recommended_actions?.length > 0 ? (
                    decisionPayload.recommended_actions.map((action, i) => (
                      <div key={i} className="action-item">{action}</div>
                    ))
                  ) : (
                    <span className="placeholder-text">No actions required.</span>
                  )}
                </>
              )}
            </div>
          </div>

          {/* Panel 4: Operational Status */}
          <div className="panel">
            <h3>Operational Status</h3>
            <div className="op-container">
              {!decisionPayload ? (
                <span className="placeholder-text">Hardware impact and routing will appear here...</span>
              ) : (
                <OperationalStatus payload={decisionPayload} />
              )}
            </div>
          </div>

          {/* Panel 5: Staff Impact */}
          <div className="panel">
            <h3>Staff Impact</h3>
            <div className="staff-container">
              {!decisionPayload ? (
                <span className="placeholder-text">Role-based assignments will appear here...</span>
              ) : (
                <StaffImpact payload={decisionPayload} />
              )}
            </div>
          </div>
        </div>
      </main>

      <audio id="syntheticAudioPlayer" style={{ display: 'none' }}></audio>
    </div>
  );
}

// Subcomponents for cleaner rendering
function SlotRow({ label, value }) {
  const isMissing = value === null || value === undefined;
  return (
    <div className="slot-row">
      <span className="slot-label">{label}</span>
      <span className="slot-value">
        {isMissing ? <span className="slot-missing">Missing</span> : <span className="slot-filled">{value}</span>}
      </span>
    </div>
  );
}

function OperationalStatus({ payload }) {
  const downtime = payload.downtime_bucket || "unknown";
  let badgeClass = "badge-available";
  if (downtime.includes("temporarily")) badgeClass = "badge-warning";
  else if (downtime.includes("unavailable")) badgeClass = "badge-danger";

  return (
    <>
      <div className="op-row">
        <span className="op-label">Downtime:</span>
        <span className={`op-badge ${badgeClass}`}>{downtime.replace(/_/g, " ")}</span>
      </div>
      <div className="op-row">
        <span className="op-label">Reroute:</span> {payload.reroute_recommendation || "N/A"}
      </div>
      <div className="op-row" style={{ marginTop: '1rem', paddingTop: '1rem', borderTop: '1px solid var(--border)' }}>
        <div className="op-label" style={{ display: 'block', marginBottom: '0.5rem' }}>Staff Broadcast:</div>
        <div className="placeholder-text" style={{ color: 'var(--text-primary)', fontStyle: 'normal' }}>
          "{payload.staff_notification || "No broadcast needed."}"
        </div>
      </div>
    </>
  );
}

function StaffImpact({ payload }) {
  const reporter = payload.reported_by_role;
  const affected = payload.affected_roles;

  return (
    <>
      {reporter && (
        <div className="op-row" style={{ marginBottom: '1.5rem' }}>
          <span className="op-label">Reported by:</span> {reporter.role} ({reporter.location})
        </div>
      )}
      {affected?.length > 0 ? (
        <>
          <div className="op-label" style={{ marginBottom: '0.5rem', display: 'block' }}>Affected Roles:</div>
          <ul className="role-list">
            {affected.map((aff, i) => (
              <li key={i} className="role-item">
                <div className="role-title">{aff.role}</div>
                <div className="role-impact">{aff.impact}</div>
              </li>
            ))}
          </ul>
        </>
      ) : (
        <div className="placeholder-text">No lateral staff impact detected.</div>
      )}
    </>
  );
}
>>>>>>> dfd1748 (Migrate frontend to React/Vite)

export default App;
