"use client";

import {
  Activity,
  ArrowRight,
  BookOpen,
  Check,
  Circle,
  RefreshCw,
  WalletCards,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ErrorState } from "@/components/feedback/error-state";
import { LoadingState } from "@/components/feedback/loading-state";
import { type DashboardSummary, getDashboardSummary } from "@/lib/api/client";
import { dashboardCurrencies, formatMoney, recentDateRange } from "@/lib/dashboard";

export function HomeDashboard() {
  const [dashboard, setDashboard] = useState<DashboardSummary | null>(null);
  const [currency, setCurrency] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    void reloadKey;
    let cancelled = false;
    const load = async () => {
      setError(null);
      const range = recentDateRange(7);
      const result = await getDashboardSummary({
        start_date: range.start,
        end_date: range.end,
        status_date: range.end,
      });
      if (cancelled) return;
      if (result.ok) {
        setDashboard(result.data);
        setCurrency((current) => current || dashboardCurrencies(result.data)[0] || "INR");
      } else setError(result.message);
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  if (error)
    return (
      <ErrorState
        title="Dashboard unavailable"
        message={error}
        actionLabel="Try again"
        onAction={() => setReloadKey((key) => key + 1)}
      />
    );
  if (!dashboard) return <LoadingState label="Loading your dashboard" />;

  const currencies = dashboardCurrencies(dashboard);
  const expense = dashboard.wealth.expenses.find((item) => item.currency === currency)?.total ?? 0;
  const net = dashboard.wealth.net.find((item) => item.currency === currency)?.net ?? 0;
  const wealthDaily = dashboard.wealth.daily.filter((item) => item.currency === currency);
  const categories = dashboard.wealth.categories
    .filter((item) => item.currency === currency)
    .slice(0, 5);
  const statusItems = [
    ["Health", dashboard.daily_status.health_complete],
    ["Wealth", dashboard.daily_status.wealth_reviewed],
    ["Learning", dashboard.daily_status.learning_complete],
  ] as const;
  const completed = statusItems.filter(([, complete]) => complete).length;

  return (
    <div className="page-stack dashboard-page">
      <header className="dashboard-hero">
        <div>
          <p className="eyebrow">Seven-day overview</p>
          <h1>Your life, grounded in what you logged.</h1>
          <p>
            Follow the numbers back to their records, keep today complete, and capture anything
            missing.
          </p>
        </div>
        <Link className="button button-primary" href="/chat">
          Open Copilot <ArrowRight size={16} aria-hidden="true" />
        </Link>
      </header>

      <section className="completion-strip" aria-labelledby="today-status">
        <div>
          <p className="eyebrow">Today</p>
          <h2 id="today-status">Daily check-in</h2>
        </div>
        <strong>{completed}/3 complete</strong>
        <div className="completion-items">
          {statusItems.map(([label, complete]) => (
            <span className={complete ? "is-complete" : undefined} key={label}>
              {complete ? (
                <Check size={14} aria-hidden="true" />
              ) : (
                <Circle size={12} aria-hidden="true" />
              )}
              {label}
            </span>
          ))}
        </div>
      </section>

      <div className="dashboard-grid">
        <section className="dashboard-card dashboard-card-wide" aria-labelledby="wealth-overview">
          <div className="card-heading">
            <div>
              <span className="card-icon">
                <WalletCards size={18} aria-hidden="true" />
              </span>
              <div>
                <p className="eyebrow">Wealth</p>
                <h2 id="wealth-overview">Cash flow</h2>
              </div>
            </div>
            {currencies.length > 1 && (
              <label className="compact-select">
                Currency
                <select value={currency} onChange={(event) => setCurrency(event.target.value)}>
                  {currencies.map((item) => (
                    <option key={item}>{item}</option>
                  ))}
                </select>
              </label>
            )}
          </div>
          <div className="metric-pair">
            <div>
              <span>Spent</span>
              <strong>{formatMoney(currency, expense)}</strong>
            </div>
            <div>
              <span>Net</span>
              <strong className={net < 0 ? "negative" : "positive"}>
                {formatMoney(currency, net)}
              </strong>
            </div>
          </div>
          {wealthDaily.length > 0 ? (
            <div
              className="chart-frame"
              role="img"
              aria-label="Daily expenses over the last seven days"
            >
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={wealthDaily} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
                  <CartesianGrid stroke="var(--border)" vertical={false} />
                  <XAxis
                    dataKey="entry_date"
                    tickFormatter={(value) => String(value).slice(5)}
                    stroke="var(--text-muted)"
                  />
                  <YAxis stroke="var(--text-muted)" width={48} />
                  <Tooltip
                    contentStyle={{
                      background: "var(--surface-raised)",
                      border: "1px solid var(--border)",
                    }}
                  />
                  <Line
                    type="monotone"
                    dataKey="expense"
                    stroke="var(--coral)"
                    strokeWidth={2.5}
                    dot={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <p className="inline-empty">No wealth activity in this period.</p>
          )}
          {categories.length > 0 && (
            <div className="chart-frame" role="img" aria-label="Top expense categories">
              <ResponsiveContainer width="100%" height={180}>
                <BarChart data={categories} layout="vertical" margin={{ left: 8 }}>
                  <XAxis type="number" hide />
                  <YAxis type="category" dataKey="category" width={90} stroke="var(--text-muted)" />
                  <Tooltip
                    contentStyle={{
                      background: "var(--surface-raised)",
                      border: "1px solid var(--border)",
                    }}
                  />
                  <Bar dataKey="total" fill="var(--yellow)" radius={[0, 5, 5, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
          <Link className="card-link" href="/wealth">
            View transactions <ArrowRight size={14} />
          </Link>
        </section>

        <section className="dashboard-card" aria-labelledby="health-overview">
          <div className="card-heading">
            <div>
              <span className="card-icon green">
                <Activity size={18} />
              </span>
              <div>
                <p className="eyebrow">Health</p>
                <h2 id="health-overview">Recovery & movement</h2>
              </div>
            </div>
          </div>
          <div className="metric-stack">
            <div>
              <span>Average sleep</span>
              <strong>
                {dashboard.health.average_sleep_hours == null
                  ? "Not logged"
                  : `${dashboard.health.average_sleep_hours.toFixed(1)} h`}
              </strong>
            </div>
            <div>
              <span>Workout days</span>
              <strong>{dashboard.health.workout_days}</strong>
            </div>
            <div>
              <span>Average calories</span>
              <strong>
                {dashboard.health.average_calories == null
                  ? "Not logged"
                  : Math.round(dashboard.health.average_calories).toLocaleString()}
              </strong>
            </div>
          </div>
          <Link className="card-link" href="/health">
            View health history <ArrowRight size={14} />
          </Link>
        </section>

        <section className="dashboard-card" aria-labelledby="learning-overview">
          <div className="card-heading">
            <div>
              <span className="card-icon blue">
                <BookOpen size={18} />
              </span>
              <div>
                <p className="eyebrow">Learning</p>
                <h2 id="learning-overview">Focused growth</h2>
              </div>
            </div>
          </div>
          <div className="metric-stack">
            <div>
              <span>Focused minutes</span>
              <strong>{dashboard.learning.total_minutes.toLocaleString()}</strong>
            </div>
            <div>
              <span>Sessions</span>
              <strong>{dashboard.learning.sessions}</strong>
            </div>
            <div>
              <span>Current streak</span>
              <strong>{dashboard.learning.current_streak_days} days</strong>
            </div>
          </div>
          <Link className="card-link" href="/learning">
            Open learning history <ArrowRight size={14} />
          </Link>
        </section>
      </div>

      <button className="refresh-link" type="button" onClick={() => setReloadKey((key) => key + 1)}>
        <RefreshCw size={14} aria-hidden="true" /> Refresh dashboard
      </button>
    </div>
  );
}
