"use client";

import { ImagePlus, Mic, Square, UploadCloud, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { extractImage, transcribeAudio } from "@/lib/api/client";

type CaptureSource = "voice" | "image";

const AUDIO_TYPES = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg"];

function recordingType(): string {
  return AUDIO_TYPES.find((type) => MediaRecorder.isTypeSupported(type)) ?? "";
}

export function MediaCapture({
  disabled,
  onTextReady,
}: Readonly<{
  disabled: boolean;
  onTextReady: (text: string, source: CaptureSource) => void;
}>) {
  const recorder = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);
  const [recording, setRecording] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewName, setPreviewName] = useState<string | null>(null);
  const [previewKind, setPreviewKind] = useState<CaptureSource | null>(null);
  const [progress, setProgress] = useState<number | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(
    () => () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
      recorder.current?.stream.getTracks().forEach((track) => {
        track.stop();
      });
    },
    [previewUrl],
  );

  const replacePreview = (url: string | null, name: string | null, kind: CaptureSource | null) => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(url);
    setPreviewName(name);
    setPreviewKind(kind);
  };

  const uploadAudio = async (file: File) => {
    setError(null);
    setStatus("Uploading recording…");
    setProgress(0);
    try {
      const result = await transcribeAudio(file, setProgress);
      onTextReady(result.text, "voice");
      setStatus(`Transcribed ${Math.round(result.duration_seconds)} seconds of audio.`);
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : "Audio upload failed.");
      setStatus(null);
    } finally {
      setProgress(null);
    }
  };

  const toggleRecording = async () => {
    if (recording) {
      recorder.current?.stop();
      setRecording(false);
      return;
    }
    setError(null);
    if (!("MediaRecorder" in window) || !navigator.mediaDevices?.getUserMedia) {
      setError("Audio recording is not supported by this browser.");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = recordingType();
      const nextRecorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      chunks.current = [];
      nextRecorder.addEventListener("dataavailable", (event) => {
        if (event.data.size) chunks.current.push(event.data);
      });
      nextRecorder.addEventListener("stop", () => {
        stream.getTracks().forEach((track) => {
          track.stop();
        });
        const contentType = (nextRecorder.mimeType || "audio/webm").split(";")[0];
        const extension = contentType === "audio/ogg" ? "ogg" : "webm";
        const blob = new Blob(chunks.current, { type: contentType });
        const file = new File([blob], `copilot-recording.${extension}`, { type: contentType });
        replacePreview(URL.createObjectURL(blob), file.name, "voice");
        void uploadAudio(file);
      });
      recorder.current = nextRecorder;
      nextRecorder.start(250);
      setRecording(true);
      setStatus("Recording. Press stop when you are finished.");
    } catch {
      setError("Microphone access was not available. Check browser permissions and try again.");
    }
  };

  const handleImage = async (file: File) => {
    setError(null);
    replacePreview(URL.createObjectURL(file), file.name, "image");
    setStatus("Uploading image…");
    setProgress(0);
    try {
      const result = await extractImage(file, setProgress);
      onTextReady(result.text, "image");
      setStatus(`Extracted visible details from ${result.width} × ${result.height} image.`);
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : "Image upload failed.");
      setStatus(null);
    } finally {
      setProgress(null);
    }
  };

  return (
    <div className="capture-tools">
      <button
        className={`capture-button${recording ? " is-recording" : ""}`}
        type="button"
        disabled={disabled || progress !== null}
        aria-pressed={recording}
        onClick={() => void toggleRecording()}
      >
        {recording ? <Square size={15} aria-hidden="true" /> : <Mic size={16} aria-hidden="true" />}
        {recording ? "Stop" : "Record"}
      </button>
      <label className={`capture-button${disabled || progress !== null ? " is-disabled" : ""}`}>
        <ImagePlus size={16} aria-hidden="true" />
        Image
        <input
          className="sr-only"
          type="file"
          accept="image/png,image/jpeg,image/webp"
          disabled={disabled || progress !== null}
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) void handleImage(file);
            event.target.value = "";
          }}
        />
      </label>
      {(status || error || previewUrl) && (
        <div className="capture-status" role={error ? "alert" : "status"}>
          {previewUrl && previewName && (
            <span className="capture-preview-wrap">
              {previewKind === "image" ? (
                // biome-ignore lint/performance/noImgElement: A short-lived local object URL is not compatible with image optimization.
                <img
                  className="capture-thumbnail"
                  src={previewUrl}
                  alt={`Preview of ${previewName}`}
                />
              ) : (
                // biome-ignore lint/a11y/useMediaCaption: This previews the user's raw recording before a transcript exists.
                <audio
                  className="capture-audio"
                  controls
                  src={previewUrl}
                  aria-label={`Preview ${previewName}`}
                />
              )}
              <span className="capture-preview">
                <UploadCloud size={14} aria-hidden="true" /> {previewName}
                <button
                  type="button"
                  aria-label="Clear media preview"
                  onClick={() => replacePreview(null, null, null)}
                >
                  <X size={13} aria-hidden="true" />
                </button>
              </span>
            </span>
          )}
          <span className={error ? "capture-error" : undefined}>{error ?? status}</span>
          {progress !== null && (
            <progress aria-label="Media upload progress" max={100} value={progress} />
          )}
        </div>
      )}
    </div>
  );
}
