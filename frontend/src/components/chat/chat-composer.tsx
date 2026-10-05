"use client";

import { Send } from "lucide-react";
import type { KeyboardEvent } from "react";
import { MediaCapture } from "./media-capture";

type CaptureSource = "text" | "voice" | "image" | "mixed";

export function ChatComposer({
  value,
  source,
  busy,
  onChange,
  onSourceChange,
  onSubmit,
}: Readonly<{
  value: string;
  source: CaptureSource;
  busy: boolean;
  onChange: (value: string) => void;
  onSourceChange: (source: CaptureSource) => void;
  onSubmit: () => void;
}>) {
  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      if (value.trim() && !busy) onSubmit();
    }
  };

  return (
    <div className="composer-shell">
      <label className="sr-only" htmlFor="copilot-message">
        Message Life Copilot
      </label>
      <textarea
        id="copilot-message"
        value={value}
        rows={3}
        maxLength={20_000}
        placeholder="Log your day or ask a question…"
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={handleKeyDown}
        disabled={busy}
      />
      <div className="composer-actions">
        <MediaCapture
          disabled={busy}
          onTextReady={(text, captureSource) => {
            onChange(value.trim() ? `${value.trim()}\n${text}` : text);
            onSourceChange(source === "text" ? captureSource : "mixed");
          }}
        />
        <div className="composer-submit-group">
          <span className="composer-hint">Enter to send · Shift+Enter for a new line</span>
          <button
            className="button button-primary composer-send"
            type="button"
            disabled={busy || !value.trim()}
            onClick={onSubmit}
          >
            <Send size={16} aria-hidden="true" />
            {busy ? "Working…" : "Send"}
          </button>
        </div>
      </div>
    </div>
  );
}
