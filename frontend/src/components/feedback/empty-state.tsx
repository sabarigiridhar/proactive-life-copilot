import { Inbox } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";
import { StatePanel } from "./state-panel";

export function EmptyState({
  title,
  message,
  actionHref,
  actionLabel,
}: Readonly<{
  title: string;
  message: string;
  actionHref?: Route;
  actionLabel?: string;
}>) {
  return (
    <StatePanel
      icon={<Inbox size={24} />}
      eyebrow="Nothing here yet"
      title={title}
      message={message}
      action={
        actionHref ? (
          <Link className="button button-secondary" href={actionHref}>
            {actionLabel ?? "Go back"}
          </Link>
        ) : undefined
      }
    />
  );
}
