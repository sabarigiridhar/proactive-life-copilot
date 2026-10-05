"use client";

import { useEffect } from "react";
import { ErrorState } from "@/components/feedback/error-state";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Frontend render failed", error.digest ?? "unknown");
  }, [error]);

  return (
    <ErrorState
      title="This page could not be displayed"
      message="Your data was not changed. Try loading the page again."
      onAction={reset}
      actionLabel="Try again"
    />
  );
}
