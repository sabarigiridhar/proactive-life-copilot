import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import type { DailyLogDraft } from "@/lib/api/client";
import { ChatComposer } from "./chat-composer";
import { DraftEditor } from "./draft-editor";

function ComposerHarness({ onSubmit }: Readonly<{ onSubmit: () => void }>) {
  const [value, setValue] = useState("A daily note");
  return (
    <ChatComposer
      value={value}
      source="text"
      busy={false}
      onChange={setValue}
      onSourceChange={() => undefined}
      onSubmit={onSubmit}
    />
  );
}

const draft: DailyLogDraft = {
  entry_date: "2026-10-05",
  source: "text",
  original_input: "I spent 450 INR on groceries.",
  confidence: 0.92,
  health: null,
  learning: [],
  wealth: [
    {
      transaction_type: "Expense",
      amount: 450,
      currency: "INR",
      category: "Groceries",
      merchant: "Market",
    },
  ],
  ambiguities: [],
  operation: "create",
};

describe("chat interactions", () => {
  it("submits with Enter and keeps Shift+Enter for multiline text", () => {
    const onSubmit = vi.fn();
    render(<ComposerHarness onSubmit={onSubmit} />);
    const composer = screen.getByRole("textbox", { name: "Message Life Copilot" });

    fireEvent.keyDown(composer, { key: "Enter", shiftKey: true });
    expect(onSubmit).not.toHaveBeenCalled();

    fireEvent.keyDown(composer, { key: "Enter" });
    expect(onSubmit).toHaveBeenCalledOnce();
  });

  it("exposes media and send controls with accessible names", () => {
    render(<ComposerHarness onSubmit={() => undefined} />);

    expect(screen.getByRole("button", { name: "Record" })).toBeInTheDocument();
    expect(screen.getByLabelText("Image")).toHaveAttribute(
      "accept",
      "image/png,image/jpeg,image/webp",
    );
    expect(screen.getByRole("button", { name: "Send" })).toBeEnabled();
  });

  it("allows extracted values to be edited before confirmation", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    render(
      <DraftEditor draft={draft} busy={false} onConfirm={onConfirm} onCancel={() => undefined} />,
    );

    const amount = screen.getByRole("spinbutton", { name: "Amount" });
    await user.clear(amount);
    await user.type(amount, "475");
    await user.click(screen.getByRole("button", { name: "Confirm and save" }));

    expect(onConfirm).toHaveBeenCalledOnce();
    expect(onConfirm.mock.calls[0]?.[0].wealth[0].amount).toBe(475);
  });
});
