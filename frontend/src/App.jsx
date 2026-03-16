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
    const [textInput, setTextInput] = useState('');
    const [isProcessing, setIsProcessing] = useState(false);

    const audioPlayerRef = useRef(null);
    const chatEndRef = useRef(null);
    const mediaRecorderRef = useRef(null);
    const audioChunksRef = useRef([]);
    const [micStatus, setMicStatus] = useState('initializing'); // initializing, ready, denied, error

    const initMic = async (isManual = false) => {
        try {
            console.log("Initializing microphone...");
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            
            // Standard WebM/Opus path
            const mimeType = MediaRecorder.isTypeSupported('audio/webm; codecs=opus') 
                ? 'audio/webm; codecs=opus' 
                : 'audio/webm';
            
            console.log(`Using MIME type: ${mimeType}`);
            const recorder = new MediaRecorder(stream, { mimeType });
            
            recorder.ondataavailable = e => {
                if (e.data.size > 0) {
                    audioChunksRef.current.push(e.data);
                }
            };

            recorder.onstop = async () => {
                const audioBlob = new Blob(audioChunksRef.current, { type: mimeType });
                audioChunksRef.current = []; // Clear for next time
                await handleVoiceSubmit(audioBlob);
            };
            
            mediaRecorderRef.current = recorder;
            setMicStatus('ready');
            if (isManual) setStatus("Microphone ready!");
            return true;
        } catch (err) {
            console.error("Mic initialization failed:", err);
            setMicStatus(err.name === 'NotAllowedError' ? 'denied' : 'error');
            setStatus(err.name === 'NotAllowedError' ? "Permission denied." : "Mic init error.");
            if (isManual) {
                alert(`Microphone error: ${err.message}. Please check site permissions in your browser.`);
            }
            return false;
        }
    };

    useEffect(() => {
        initMic();
        return () => {
            if (mediaRecorderRef.current && mediaRecorderRef.current.stream) {
                mediaRecorderRef.current.stream.getTracks().forEach(track => track.stop());
            }
        };
    }, []);

    useEffect(() => {
        if (chatEndRef.current) {
            chatEndRef.current.scrollIntoView({ behavior: 'smooth' });
        }
    }, [history]);

    const playAssistantAudio = (base64) => {
        if (!base64 || !audioPlayerRef.current) return;
        
        try {
            // Stop any current playback
            audioPlayerRef.current.pause();
            audioPlayerRef.current.currentTime = 0;
            
            audioPlayerRef.current.src = `data:audio/mp3;base64,${base64}`;
            audioPlayerRef.current.volume = 1.0;
            
            const playPromise = audioPlayerRef.current.play();
            if (playPromise !== undefined) {
                playPromise.catch(error => {
                    console.warn("Autoplay was prevented or audio failed:", error);
                });
            }
        } catch (err) {
            console.error("Audio playback error:", err);
        }
    };

    const startRecording = async () => {
        console.log("startRecording called, mic status:", micStatus);
        if (!mediaRecorderRef.current) {
            setStatus("Wait, re-initializing...");
            const success = await initMic(true);
            if (!success) return;
        }

        // Immediately stop any currently playing assistant audio
        if (audioPlayerRef.current) {
            audioPlayerRef.current.pause();
            audioPlayerRef.current.currentTime = 0;
        }

        audioChunksRef.current = [];
        try {
            mediaRecorderRef.current.start();
            setIsRecording(true);
            setStatus("Listening...");
        } catch (e) {
            console.error("Failed to start recording:", e);
            setStatus("Failed to start recording.");
        }
    };

    const stopRecording = () => {
        if (!isRecording) return;
        try {
            if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
                mediaRecorderRef.current.stop();
            }
            setIsRecording(false);
            setIsProcessing(true);
            setStatus("Analyzing...");
        } catch (e) {
            console.error("Failed to stop recording:", e);
            setIsRecording(false);
        }
    };

    const handleVoiceSubmit = async (audioBlob) => {
        if (!audioBlob || audioBlob.size < 1000) {
            setIsProcessing(false);
            setStatus("Ready");
            return;
        }

        const formData = new FormData();
        formData.append('audio', audioBlob, 'incident.webm');
        formData.append('session_id', sessionId);

        try {
            const response = await axios.post('http://127.0.0.1:8080/api/v1/voice/incident', formData);
            if (response.data.status === 'success') {
                setStatus("Ready");
                renderResults(response.data.data);
            } else {
                setStatus("Error processing voice.");
            }
        } catch (error) {
            console.error("Voice Error:", error);
            setStatus("Error: " + (error.response?.data?.message || error.message));
        } finally {
            setIsProcessing(false);
        }
    };

    const handleTextSubmit = async (e) => {
        if (e) e.preventDefault();
        const text = textInput.trim();
        if (!text || isProcessing) return;

        setTextInput('');
        setIsProcessing(true);
        setStatus("Thinking...");

        // Proactive UI update: add user message immediately
        const tempHistory = [...history, { role: 'user', text }];
        setHistory(tempHistory);

        try {
            const response = await axios.post('http://127.0.0.1:8080/api/v1/text/incident', {
                session_id: sessionId,
                message: text
            });

            if (response.data.status === 'success') {
                setStatus("Ready");
                renderResults(response.data.data);
            }
        } catch (error) {
            console.error("Text Error:", error);
            setStatus("Error: " + (error.response?.data?.message || error.message));
        } finally {
            setIsProcessing(false);
        }
    };

    const renderResults = (data) => {
        if (data.history) setHistory(data.history);
        if (data.extracted_slots) setSlots(data.extracted_slots);

        if (data.status === "complete" || data.status === "troubleshooting") {
            const payload = data.pipeline_handoff_payload;
            if (payload) {
                setDecision(payload);
                setOpStatus(payload);
                setStaffImpact(payload.affected_roles || []);
            }
        } else {
            setDecision(null);
        }

        if (data.spoken_response_base64) {
            playAssistantAudio(data.spoken_response_base64);
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
                    <span id="backendStatus">Live Status</span>
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
                                className={`voice-orb-btn ${isRecording ? 'recording' : ''} ${micStatus !== 'ready' ? 'disabled' : ''}`}
                                title={micStatus !== 'ready' ? "Microphone not ready" : "Push to Talk"}
                            >
                                <div className="orb-inner">
                                    {micStatus === 'denied' ? <AlertCircle size={48} /> : <Mic size={48} strokeWidth={2.5} />}
                                </div>
                                {isRecording && <div className="orb-pulsar"></div>}
                            </motion.button>
                            <div className="hud-status">
                                {micStatus === 'denied' ? "Mic Access Denied" : status}
                            </div>
                            {isRecording && (
                                <div className="wave-visualizer">
                                    {[1, 2, 3, 4, 5].map(i => <div key={i} className="bar"></div>)}
                                </div>
                            )}
                        </div>
                    </section>

                    <div className="chat-viewport glass">
                        <div className="conversation-history">
                            <AnimatePresence initial={false}>
                                {history.length === 0 ? (
                                    <motion.div
                                        key="welcome"
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
                                            <div className="chat-text">
                                                {msg.role === 'assistant' ? formatAssistantMessage(msg.text) : msg.text}
                                            </div>
                                        </motion.div>
                                    ))
                                )}
                            </AnimatePresence>
                            <div ref={chatEndRef} />
                        </div>
                    </div>

                    <form className="text-input-container glass-light" onSubmit={handleTextSubmit}>
                        <input 
                            type="text"
                            placeholder="Type your message here..."
                            value={textInput}
                            onChange={(e) => setTextInput(e.target.value)}
                            disabled={isProcessing}
                            className="text-input"
                        />
                        <button 
                            type="submit" 
                            disabled={isProcessing || !textInput.trim()}
                            className="send-btn"
                        >
                            <ArrowRight size={20} />
                        </button>
                    </form>
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

// Helper: Formats assistant messages to handle numbered/bulleted lists
const formatAssistantMessage = (text) => {
    if (!text) return null;

    // Detect if the text contains numbered steps or bullet points
    const isNumbered = /\d+\.\s/.test(text);
    const isBulleted = /[\-\*•]\s/.test(text);

    if (!isNumbered && !isBulleted) {
        return <span>{text}</span>;
    }

    const items = text.split(/(?=\d+\.\s|[\-\*•]\s)/).filter(item => item.trim().length > 0);

    return (
        <ul className="assistant-msg-list">
            {items.map((item, i) => (
                <li key={i} className="assistant-msg-item">{item.trim()}</li>
            ))}
        </ul>
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

export default App;
