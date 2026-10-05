import { EmptyState } from "@/components/feedback/empty-state";

export function FeaturePlaceholder({
  eyebrow,
  title,
  description,
  nextStory,
}: Readonly<{
  eyebrow: string;
  title: string;
  description: string;
  nextStory: string;
}>) {
  return (
    <div className="page-stack">
      <header className="page-header">
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <p>{description}</p>
      </header>
      <EmptyState
        title={`${title} migration is queued`}
        message={`The responsive shell and typed API client are ready. This workflow is implemented in ${nextStory}.`}
        actionHref="/"
        actionLabel="View foundation status"
      />
    </div>
  );
}
