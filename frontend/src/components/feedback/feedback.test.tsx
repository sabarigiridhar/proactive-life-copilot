import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { EmptyState } from "./empty-state";
import { ErrorState } from "./error-state";
import { LoadingState } from "./loading-state";
import { NotificationBanner } from "./notification-banner";

describe("shared feedback components", () => {
  it("announces loading state politely", () => {
    render(<LoadingState label="Loading dashboard" />);

    expect(screen.getByRole("status")).toHaveTextContent("Loading dashboard");
  });

  it("renders errors as assertive alerts", () => {
    render(<ErrorState title="API unavailable" message="Start FastAPI." />);

    expect(screen.getByRole("alert")).toHaveTextContent("API unavailable");
    expect(screen.getByRole("alert")).toHaveAttribute("aria-live", "assertive");
  });

  it("renders an empty-state recovery link", () => {
    render(
      <EmptyState
        title="No records"
        message="Capture your first entry."
        actionHref="/"
        actionLabel="Return home"
      />,
    );

    expect(screen.getByRole("link", { name: "Return home" })).toHaveAttribute("href", "/");
  });

  it("allows keyboard and pointer users to dismiss notifications", async () => {
    const user = userEvent.setup();
    render(<NotificationBanner title="Saved" message="Your settings were updated." />);

    await user.click(screen.getByRole("button", { name: "Dismiss notification" }));

    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });
});
