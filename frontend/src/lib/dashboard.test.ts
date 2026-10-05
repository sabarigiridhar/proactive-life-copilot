import { describe, expect, it } from "vitest";
import type { DashboardSummary } from "./api/client";
import { dashboardCurrencies, formatMoney, recentDateRange } from "./dashboard";

describe("dashboard helpers", () => {
  it("creates an inclusive recent date range", () => {
    expect(recentDateRange(7, new Date("2026-10-05T12:00:00Z"))).toEqual({
      start: "2026-09-29",
      end: "2026-10-05",
    });
  });

  it("deduplicates and sorts dashboard currencies", () => {
    const dashboard = {
      wealth: {
        income: [{ currency: "USD" }, { currency: "INR" }],
        expenses: [{ currency: "INR" }],
        net: [{ currency: "EUR" }],
      },
    } as DashboardSummary;
    expect(dashboardCurrencies(dashboard)).toEqual(["EUR", "INR", "USD"]);
  });

  it("keeps the currency code visible in formatted values", () => {
    expect(formatMoney("INR", 1234.5)).toMatch(/^INR\s/);
  });
});
