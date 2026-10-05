import type { DashboardSummary } from "./api/client";

export function isoDate(date: Date): string {
  return date.toISOString().slice(0, 10);
}

export function recentDateRange(days = 7, today = new Date()): { start: string; end: string } {
  const end = new Date(today);
  const start = new Date(today);
  start.setDate(end.getDate() - Math.max(0, days - 1));
  return { start: isoDate(start), end: isoDate(end) };
}

export function dashboardCurrencies(dashboard: DashboardSummary): string[] {
  return Array.from(
    new Set([
      ...dashboard.wealth.income.map((item) => item.currency),
      ...dashboard.wealth.expenses.map((item) => item.currency),
      ...dashboard.wealth.net.map((item) => item.currency),
    ]),
  ).sort();
}

export function formatMoney(currency: string, value: number): string {
  return `${currency} ${new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(value)}`;
}
