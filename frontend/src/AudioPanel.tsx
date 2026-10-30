import { useEffect, useRef, useState } from "react";
import { api } from "./api";
import { useApp } from "./store";

export default function AudioPanel() {
  const sessionId = useApp((s) => s.sessionId);
  const narration = useApp((s) => s.narration);
  const [recording, setRecording] = useState(false);
  const [lastTranscript, setLastTranscript] = useState("");
  const [speaking, setSpeaking] = useState(false);
  const [error, setError] = useState("");
  const mediaRecorder = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);

  useEffect(() => {
    return () => {
      window.speechSynthesis?.cancel();
    };
  }, []);

  const speak = (text: string) => {
    if (!("speechSynthesis" in window)) {
      setError("Speech synthesis not available in this browser");
      return;
    }
    window.speechSynthesis.cancel();
    const utter = new SpeechSynthesisUtterance(text);
    utter.rate = 1.0;
    utter.onstart = () => setSpeaking(true);
    utter.onend = () => setSpeaking(false);
    utter.onerror = () => setSpeaking(false);
    window.speechSynthesis.speak(utter);
  };

  const startRecording = async () => {
    setError("");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const rec = new MediaRecorder(stream);
      chunks.current = [];
      rec.ondataavailable = (e) => {
        if (e.data.size > 0) chunks.current.push(e.data);
      };
      rec.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunks.current, { type: rec.mimeType || "audio/webm" });
        if (sessionId == null) return;
        const fd = new FormData();
        fd.append("file", blob, "chunk.webm");
        try {
          const resp = await fetch(`/api/sessions/${sessionId}/transcribe`, { method: "POST", body: fd });
          if (resp.ok) {
            const data = await resp.json();
            setLastTranscript(data.text ?? "");
          } else {
            setError(`Transcription failed (${resp.status}) — is faster-whisper installed on the host?`);
          }
        } catch {
          setError("Transcription request failed");
        }
      };
      rec.start();
      mediaRecorder.current = rec;
      setRecording(true);
    } catch {
      setError("Microphone access denied");
    }
  };

  const stopRecording = () => {
    mediaRecorder.current?.stop();
    setRecording(false);
  };

  const latest = narration[narration.length - 1];

  return (
    <div className="panel">
      <h2>🎙️ Audio</h2>
      <div className="row">
        {recording ? (
          <button className="danger" onClick={stopRecording}>
            ■ Stop &amp; transcribe
          </button>
        ) : (
          <button onClick={startRecording} disabled={sessionId == null}>
            ● Record table talk
          </button>
        )}
        {latest && (
          <button onClick={() => speak(latest)} disabled={speaking}>
            {speaking ? "🔊 Speaking…" : "🔈 Read narration aloud"}
          </button>
        )}
      </div>
      {recording && <p className="rec-indicator">● recording — audio is transcribed locally, never stored</p>}
      {lastTranscript && (
        <p className="transcript">
          <strong>Heard:</strong> {lastTranscript}
        </p>
      )}
      {error && <p className="error">{error}</p>}
      <p className="muted small">Mic audio goes to local Whisper on the host only. TTS uses the device speaker.</p>
    </div>
  );
}

export function VisionButton() {
  const sessionId = useApp((s) => s.sessionId);
  const adminToken = useApp((s) => s.adminToken);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState("");
  const [error, setError] = useState("");
  const videoRef = useRef<HTMLVideoElement | null>(null);

  const capture = async () => {
    setBusy(true);
    setError("");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true });
      const video = document.createElement("video");
      video.srcObject = stream;
      await video.play();
      await new Promise((r) => setTimeout(r, 400));
      const canvas = document.createElement("canvas");
      canvas.width = video.videoWidth || 640;
      canvas.height = video.videoHeight || 480;
      canvas.getContext("2d")?.drawImage(video, 0, 0);
      stream.getTracks().forEach((t) => t.stop());
      const dataUrl = canvas.toDataURL("image/jpeg", 0.7);
      void videoRef;
      if (sessionId == null) return;
      const resp = await fetch(`/api/sessions/${sessionId}/vision`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Admin-Token": adminToken },
        body: JSON.stringify({ image: dataUrl }),
      });
      if (resp.ok) {
        const data = await resp.json();
        setResult(data.description ?? "");
      } else {
        setError(`Vision failed (${resp.status})`);
      }
    } catch {
      setError("Camera access denied");
    } finally {
      setBusy(false);
    }
  };

  if (!adminToken) return null;
  return (
    <div className="panel">
      <h2>📷 Vision (host)</h2>
      <button onClick={capture} disabled={busy || sessionId == null}>
        {busy ? "Analyzing…" : "Capture table & describe (Pixtral, EU)"}
      </button>
      {result && <p className="transcript">{result}</p>}
      {error && <p className="error">{error}</p>}
      <p className="muted small">Frames go only to Mistral&apos;s EU endpoint on explicit action and are discarded after the call.</p>
    </div>
  );
}

export function useTtsOnNarration() {
  const narration = useApp((s) => s.narration);
  const prev = useRef("");
  useEffect(() => {
    const latest = narration[narration.length - 1];
    if (latest && latest !== prev.current && "speechSynthesis" in window) {
      prev.current = latest;
    }
  }, [narration]);
}

void api;
