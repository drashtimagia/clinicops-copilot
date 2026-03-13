import { useState, useRef, useEffect } from 'react';

export default function useCopilot() {
  const [statusText, setStatusText] = useState('Ready to Record');
  const [isRecording, setIsRecording] = useState(false);
  
  // Pipeline State
  const [history, setHistory] = useState([]);
  const [slots, setSlots] = useState(null);
  const [decisionPayload, setDecisionPayload] = useState(null);
  const [serverStatus, setServerStatus] = useState(null);

  // Audio References
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const recognitionRef = useRef(null);
  
  // Transcript State
  const finalTranscriptRef = useRef('');
  const interimTranscriptRef = useRef('');

  const sessionId = useRef("session_" + Math.random().toString(36).substring(2, 10)).current;

  // Initialize Speech Recognition & Media Recorder on Mount
  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
      const recognition = new SpeechRecognition();
      recognition.continuous = true;
      recognition.interimResults = true;
      
      recognition.onresult = (event) => {
        let interim = '';
        for (let i = event.resultIndex; i < event.results.length; ++i) {
          if (event.results[i].isFinal) {
            finalTranscriptRef.current += event.results[i][0].transcript;
          } else {
            interim += event.results[i][0].transcript;
          }
        }
        interimTranscriptRef.current = interim;
        setStatusText('Listening: ' + (finalTranscriptRef.current + interim));
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
        setStatusText("Microphone access denied.");
      });
  }, []);

  const startRecording = () => {
    if (!mediaRecorderRef.current || isRecording) return;
    
    audioChunksRef.current = [];
    finalTranscriptRef.current = '';
    interimTranscriptRef.current = '';
    
    mediaRecorderRef.current.start();
    try { recognitionRef.current?.start(); } catch(e){}
    
    setIsRecording(true);
    setStatusText("Listening...");
  };

  const stopRecording = () => {
    if (!mediaRecorderRef.current || mediaRecorderRef.current.state !== 'recording') return;
    
    mediaRecorderRef.current.stop();
    try { recognitionRef.current?.stop(); } catch(e){}
    
    setIsRecording(false);
    setStatusText("Processing incident via Amazon Nova...");
  };

  const handleAudioSubmit = async () => {
    const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
    const formData = new FormData();
    formData.append('audio', audioBlob, 'recording.webm');
    
    // Wait for final speech recognition results
    await new Promise(r => setTimeout(r, 800));
    
    const combinedTranscript = (finalTranscriptRef.current + interimTranscriptRef.current).trim();
    
    const metadata = {
      session_id: sessionId,
      incident_id: "HACKATHON-DEMO-001",
      device_id: "Unknown Device",
      reporter: "Web Copilot Frontend",
      description: combinedTranscript
    };
    formData.append('metadata', JSON.stringify(metadata));

    // Optimistic UI Update
    setHistory(prev => [...prev, { role: 'user', text: "Audio sent, waiting for analysis..." }]);
    setDecisionPayload(null); // Clear downstream panels
    setServerStatus('processing');

    try {
      const response = await fetch('/api/v1/voice/incident', {
        method: 'POST',
        body: formData
      });
      
      const result = await response.json();
      
      if (response.ok && result.status === 'success') {
        setStatusText("Analysis Complete");
        processResult(result.data);
      } else {
        throw new Error(result.message || "Server Error");
      }
    } catch (error) {
      console.error(error);
      setStatusText("Error: " + error.message);
    }
  };

  const processResult = (data) => {
    if (data.history) setHistory(data.history);
    if (data.extracted_slots) setSlots(data.extracted_slots);
    
    setServerStatus(data.status);
    
    if (data.status === 'complete') {
      setDecisionPayload(data.pipeline_handoff_payload);
    }

    // Playback Audio Output
    if (data.spoken_response_base64) {
      const audioSrc = `data:audio/mp3;base64,${data.spoken_response_base64}`;
      const player = document.getElementById('syntheticAudioPlayer');
      if (player) {
        player.src = audioSrc;
        player.play().catch(e => console.error("Auto-play blocked:", e));
      }
    } else if (data.final_text_response && 'speechSynthesis' in window) {
      window.speechSynthesis.cancel();
      window.speechSynthesis.speak(new SpeechSynthesisUtterance(data.final_text_response));
    }
  };

  return {
    statusText,
    isRecording,
    history,
    slots,
    decisionPayload,
    serverStatus,
    startRecording,
    stopRecording
  };
}
