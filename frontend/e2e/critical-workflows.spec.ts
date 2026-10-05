import { expect, type Page, test } from "@playwright/test";

const envelope = (data: unknown) => ({ success: true, data, error: null, request_id: "e2e" });
const corsHeaders = {
  "access-control-allow-origin": "*",
  "access-control-allow-methods": "GET,POST,PATCH,DELETE,OPTIONS",
  "access-control-allow-headers": "content-type,x-request-id",
};

async function mockApi(page: Page) {
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (request.method() === "OPTIONS") {
      return route.fulfill({ status: 204, headers: corsHeaders });
    }
    let data: unknown;
    if (path === "/api/v1/dashboard/summary") {
      data = {
        date_range: { start_date: "2026-09-29", end_date: "2026-10-05" },
        status_date: "2026-10-05",
        daily_status: {
          entry_date: "2026-10-05",
          health_complete: true,
          wealth_reviewed: false,
          learning_complete: true,
          is_complete: false,
        },
        wealth: {
          income: [{ currency: "INR", total: 5000, records: 1 }],
          expenses: [{ currency: "INR", total: 450, records: 1 }],
          net: [{ currency: "INR", income: 5000, expense: 450, net: 4550 }],
          categories: [{ currency: "INR", category: "Groceries", total: 450, records: 1 }],
          daily: [
            { entry_date: "2026-10-05", currency: "INR", income: 5000, expense: 450, net: 4550 },
          ],
        },
        health: {
          average_sleep_hours: 7.5,
          average_calories: 2100,
          workout_days: 2,
          sleep_records: 4,
          calorie_records: 3,
          daily: [],
        },
        learning: {
          total_minutes: 90,
          sessions: 3,
          learning_days: 2,
          current_streak_days: 2,
          longest_streak_days: 4,
          daily: [],
          topics: [],
        },
      };
    } else if (path === "/api/v1/logs/wealth" && request.method() === "GET") {
      data = {
        domain: "wealth",
        page: 1,
        page_size: 200,
        total: 1,
        total_pages: 1,
        items: [
          {
            id: 1,
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
          },
        ],
      };
    } else if (path === "/api/v1/logs/wealth/1" && request.method() === "PATCH") {
      data = { record: {}, statuses: {}, warnings: [] };
    } else if (path.startsWith("/api/v1/logs/")) {
      const domain = path.split("/")[4];
      data = { domain, page: 1, page_size: 200, total: 0, total_pages: 1, items: [] };
    } else if (path === "/api/v1/learning/search") {
      data = {
        mode: "keyword",
        query: "retrieval",
        warning: null,
        hits: [
          {
            record_id: 8,
            entry_date: "2026-10-04",
            topic: "Retrieval quality",
            summary_text: "Ground answers in stored evidence.",
            duration_minutes: 30,
            url_reference: "https://example.com/source",
            score: 0.9,
          },
        ],
      };
    } else if (path === "/api/v1/settings") {
      data = {
        preferences: {
          default_currency: "INR",
          weekly_spending_limit: 3000,
          weekly_learning_minutes: 180,
          weekly_workouts: 3,
          sleep_hours_target: 8,
          updated_at: "2026-10-05T10:00:00Z",
        },
        providers: [
          { provider: "OpenAI", capability: "Chat", model: "gpt-test", configured: true },
        ],
      };
    } else if (path === "/api/v1/insights/weekly") {
      data = {
        generation_available: false,
        message: null,
        reviews: [
          {
            id: 1,
            period_start: "2026-09-28",
            period_end: "2026-10-04",
            title: "A steady week",
            summary: "Learning and recovery were consistent.",
            evidence: [{ metric: "learning_minutes", value: 90 }],
            created_at: "2026-10-05T08:00:00Z",
          },
        ],
      };
    } else if (path === "/api/v1/conversations") {
      data = { items: [] };
    } else {
      return route.fulfill({
        status: 404,
        headers: corsHeaders,
        json: { success: false, error: { message: `No E2E mock for ${path}` }, request_id: "e2e" },
      });
    }
    await route.fulfill({ status: 200, headers: corsHeaders, json: envelope(data) });
  });
}

test.beforeEach(async ({ page }) => {
  await mockApi(page);
});

test("dashboard renders daily status and cross-domain metrics", async ({ page }) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Your life, grounded in what you logged." }),
  ).toBeVisible();
  await expect(page.getByText("2/3 complete")).toBeVisible();
  await expect(page.getByText("INR 450")).toBeVisible();
  await expect(page.getByText("90", { exact: true })).toBeVisible();
});

test("wealth history supports editing a source record", async ({ page }) => {
  let updatedAmount: number | undefined;
  await page.route("**/api/v1/logs/wealth/1", async (route) => {
    if (route.request().method() === "OPTIONS") {
      return route.fulfill({ status: 204, headers: corsHeaders });
    }
    updatedAmount = (route.request().postDataJSON() as { amount?: number }).amount;
    await route.fulfill({
      headers: corsHeaders,
      json: envelope({ record: {}, statuses: {}, warnings: [] }),
    });
  });
  await page.goto("/wealth");
  await page.getByRole("button", { name: "Edit record 1" }).click();
  await page.getByRole("spinbutton", { name: "Amount" }).fill("525.50");
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByText("Wealth record updated.")).toBeVisible();
  expect(updatedAmount).toBe(525.5);
});

test("learning search preserves evidence links and weekly reviews remain readable", async ({
  page,
}) => {
  await page.goto("/learning");
  await page.getByRole("searchbox", { name: "Question or concept" }).fill("retrieval");
  await page.getByRole("button", { name: "Search notes" }).click();
  await expect(page.getByRole("heading", { name: "Retrieval quality" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Open source" })).toHaveAttribute(
    "href",
    "https://example.com/source",
  );
  await page.goto("/weekly-review");
  await expect(page.getByRole("heading", { name: "A steady week" })).toBeVisible();
  await expect(page.getByText("learning_minutes")).toBeVisible();
});

test("settings and chat are reachable from the replacement client", async ({ page }) => {
  await page.goto("/settings");
  await expect(page.getByRole("heading", { name: "Preferences and weekly targets" })).toBeVisible();
  await expect(page.getByText("Configured", { exact: true })).toBeVisible();
  await page.goto("/chat");
  await expect(page.getByRole("textbox", { name: "Message Life Copilot" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Send" })).toBeVisible();
});
