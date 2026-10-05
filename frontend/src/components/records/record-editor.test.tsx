import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { WealthRecord } from "@/lib/api/client";
import { RecordEditor } from "./record-editor";

const record: WealthRecord = {
  id: 12,
  entry_date: "2026-10-05",
  transaction_type: "Expense",
  amount: 450,
  currency: "INR",
  category: "Groceries",
  merchant: "Market",
  notes: null,
  source: "text",
  created_at: "2026-10-05T10:00:00Z",
  updated_at: "2026-10-05T10:00:00Z",
};

describe("record editor", () => {
  it("returns edited typed wealth fields", async () => {
    const user = userEvent.setup();
    const onSave = vi.fn();
    render(
      <RecordEditor
        domain="wealth"
        record={record}
        busy={false}
        onSave={onSave}
        onCancel={() => undefined}
      />,
    );

    const amount = screen.getByRole("spinbutton", { name: "Amount" });
    await user.clear(amount);
    await user.type(amount, "525.50");
    await user.selectOptions(screen.getByRole("combobox", { name: "Type" }), "Income");
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({ amount: 525.5, transaction_type: "Income", currency: "INR" }),
    );
  });
});
