import { LoaderCircle } from "lucide-react";

export function LoadingState({ label = "Loading" }: Readonly<{ label?: string }>) {
  return (
    <div className="loading-state" role="status" aria-live="polite">
      <LoaderCircle className="spinner" size={22} aria-hidden="true" />
      <span>{label}</span>
    </div>
  );
}
