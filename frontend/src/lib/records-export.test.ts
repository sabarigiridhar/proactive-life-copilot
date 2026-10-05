import { describe, expect, it } from "vitest";
import type { DomainRecord } from "./api/client";
import { publicRecords } from "./records-export";

describe("records export", () => {
  it("keeps public wealth fields and drops private input fields", () => {
    const record = {
      id: 7,
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
      original_input: "private raw message",
    } as unknown as DomainRecord;

    const [exported] = publicRecords("wealth", [record]);
    expect(exported.amount).toBe(450);
    expect(exported).not.toHaveProperty("original_input");
  });
});
