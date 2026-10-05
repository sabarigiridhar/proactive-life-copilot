"use client";

import { CircleAlert } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";
import { Button } from "react-aria-components";
import { StatePanel } from "./state-panel";

export function ErrorState({
  title,
  message,
  actionHref,
  actionLabel,
  onAction,
}: Readonly<{
  title: string;
  message: string;
  actionHref?: Route;
  actionLabel?: string;
  onAction?: () => void;
}>) {
  const action = onAction ? (
    <Button className="button button-primary" onPress={onAction}>
      {actionLabel ?? "Try again"}
    </Button>
  ) : actionHref ? (
    <Link className="button button-primary" href={actionHref}>
      {actionLabel ?? "Continue"}
    </Link>
  ) : undefined;

  return (
    <StatePanel
      icon={<CircleAlert size={24} />}
      eyebrow="Connection issue"
      title={title}
      message={message}
      action={action}
      role="alert"
    />
  );
}
