"use client";

import { CheckCircle2, X } from "lucide-react";
import { useState } from "react";
import { Button } from "react-aria-components";

export function NotificationBanner({
  title,
  message,
}: Readonly<{ title: string; message: string }>) {
  const [visible, setVisible] = useState(true);
  if (!visible) {
    return null;
  }

  return (
    <aside className="notification" role="status" aria-live="polite">
      <CheckCircle2 size={19} color="var(--green)" aria-hidden="true" />
      <div>
        <strong>{title}</strong>
        <p>{message}</p>
      </div>
      <Button
        className="icon-button"
        aria-label="Dismiss notification"
        onPress={() => setVisible(false)}
      >
        <X size={17} aria-hidden="true" />
      </Button>
    </aside>
  );
}
