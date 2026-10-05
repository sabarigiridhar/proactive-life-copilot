import type { ReactNode } from "react";

export function StatePanel({
  icon,
  eyebrow,
  title,
  message,
  action,
  role = "status",
}: Readonly<{
  icon: ReactNode;
  eyebrow: string;
  title: string;
  message: string;
  action?: ReactNode;
  role?: "status" | "alert";
}>) {
  return (
    <section
      className="state-panel"
      role={role}
      aria-live={role === "alert" ? "assertive" : "polite"}
    >
      <div className="state-panel-icon" aria-hidden="true">
        {icon}
      </div>
      <p className="eyebrow">{eyebrow}</p>
      <h2>{title}</h2>
      <p>{message}</p>
      {action ? <div className="state-panel-action">{action}</div> : null}
    </section>
  );
}
