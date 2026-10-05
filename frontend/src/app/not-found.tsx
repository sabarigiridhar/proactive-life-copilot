import { EmptyState } from "@/components/feedback/empty-state";

export default function NotFound() {
  return (
    <EmptyState
      title="Page not found"
      message="That workspace does not exist in Life Copilot."
      actionHref="/"
      actionLabel="Return home"
    />
  );
}
