"use client";

import { Download, Pencil, RefreshCw, Search, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
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
import { EmptyState } from "@/components/feedback/empty-state";
import { ErrorState } from "@/components/feedback/error-state";
import { LoadingState } from "@/components/feedback/loading-state";
import {
  type DomainRecord,
  deleteRecord,
  type HealthRecord,
  type LearningRecord,
  listAllRecords,
  type RecordDomain,
  type RecordPatch,
  updateRecord,
  type WealthRecord,
} from "@/lib/api/client";
import { formatMoney } from "@/lib/dashboard";
import { RecordEditor } from "./record-editor";

type Filters = { search: string; start_date: string; end_date: string; detail: string };
const emptyFilters: Filters = { search: "", start_date: "", end_date: "", detail: "" };

function csvValue(value: unknown): string {
  return `"${String(value ?? "").replaceAll('"', '""')}"`;
}

function exportCsv(domain: RecordDomain, records: DomainRecord[]) {
  if (records.length === 0) return;
  const keys = Array.from(new Set(records.flatMap((record) => Object.keys(record))));
  const content = [
    keys.join(","),
    ...records.map((record) =>
      keys.map((key) => csvValue((record as unknown as Record<string, unknown>)[key])).join(","),
    ),
  ].join("\n");
  const url = URL.createObjectURL(new Blob([content], { type: "text/csv;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = `life-copilot-${domain}.csv`;
  link.click();
  URL.revokeObjectURL(url);
}

function recordLabel(domain: RecordDomain, record: DomainRecord): string {
  if (domain === "wealth" && "amount" in record)
    return `${record.transaction_type} · ${record.currency} ${record.amount} · ${record.category}`;
  if (domain === "health" && "sleep_hours" in record)
    return `${record.workout_type || "Health log"} · ${record.sleep_hours ?? "—"} h sleep`;
  if (domain === "learning" && "topic" in record)
    return `${record.topic} · ${record.duration_minutes ?? 0} min`;
  return `Record #${record.id}`;
}

function isWealthRecord(record: DomainRecord): record is WealthRecord {
  return "amount" in record;
}

function isHealthRecord(record: DomainRecord): record is HealthRecord {
  return "sleep_hours" in record;
}

function isLearningRecord(record: DomainRecord): record is LearningRecord {
  return "topic" in record;
}

export function RecordsWorkspace({
  domain,
  showHeader = true,
}: Readonly<{ domain: RecordDomain; showHeader?: boolean }>) {
  const [records, setRecords] = useState<DomainRecord[]>([]);
  const [filters, setFilters] = useState<Filters>(emptyFilters);
  const [draftFilters, setDraftFilters] = useState<Filters>(emptyFilters);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [editing, setEditing] = useState<DomainRecord | null>(null);
  const [deleting, setDeleting] = useState<DomainRecord | null>(null);
  const [mutationError, setMutationError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    void reloadKey;
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      setError(null);
      const query = {
        search: filters.search || undefined,
        start_date: filters.start_date || undefined,
        end_date: filters.end_date || undefined,
        ...(domain === "wealth" ? { category: filters.detail || undefined } : {}),
        ...(domain === "health" ? { workout_type: filters.detail || undefined } : {}),
        ...(domain === "learning" ? { topic: filters.detail || undefined } : {}),
      };
      const result = await listAllRecords(domain, query);
      if (cancelled) return;
      if (result.ok) setRecords(result.data);
      else setError(result.message);
      setLoading(false);
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, [domain, filters, reloadKey]);

  const totalPages = Math.max(1, Math.ceil(records.length / pageSize));
  const pageRecords = records.slice(
    (Math.min(page, totalPages) - 1) * pageSize,
    Math.min(page, totalPages) * pageSize,
  );
  const wealth = records.filter(isWealthRecord);
  const health = records.filter(isHealthRecord);
  const learning = records.filter(isLearningRecord);
  const currencies = Array.from(new Set(wealth.map((record) => record.currency))).sort();
  const [selectedCurrency, setSelectedCurrency] = useState("");
  const currency = currencies.includes(selectedCurrency)
    ? selectedCurrency
    : currencies[0] || "INR";
  const wealthMetrics = wealth.filter((record) => record.currency === currency);
  const income = wealthMetrics
    .filter((record) => record.transaction_type === "Income")
    .reduce((sum, record) => sum + record.amount, 0);
  const expense = wealthMetrics
    .filter((record) => record.transaction_type === "Expense")
    .reduce((sum, record) => sum + record.amount, 0);
  const sleep = health.flatMap((record) =>
    record.sleep_hours == null ? [] : [record.sleep_hours],
  );
  const calories = health.flatMap((record) =>
    record.calories_consumed == null ? [] : [record.calories_consumed],
  );
  const chartData = useMemo(
    () =>
      records.map((record) => ({
        date: record.entry_date,
        value:
          "amount" in record
            ? record.amount
            : "sleep_hours" in record
              ? (record.sleep_hours ?? 0)
              : "duration_minutes" in record
                ? (record.duration_minutes ?? 0)
                : 0,
      })),
    [records],
  );
  const titles = {
    wealth: [
      "Money and decisions",
      "Wealth",
      "Understand cash flow and maintain every transaction.",
    ],
    health: [
      "Energy and consistency",
      "Health",
      "Review sleep, calories, workouts, and missing data.",
    ],
    learning: [
      "Knowledge and recall",
      "Learning",
      "Browse sessions and search verified notes with their sources.",
    ],
  } as const;
  const [eyebrow, title, description] = titles[domain];

  const save = async (patch: RecordPatch) => {
    if (!editing) return;
    setBusy(true);
    setMutationError(null);
    const result = await updateRecord(domain, editing.id, patch);
    if (result.ok) {
      setEditing(null);
      setNotice(`${title} record updated.`);
      setReloadKey((key) => key + 1);
    } else setMutationError(result.message);
    setBusy(false);
  };

  const remove = async () => {
    if (!deleting) return;
    setBusy(true);
    setMutationError(null);
    const result = await deleteRecord(domain, deleting.id);
    if (result.ok) {
      setDeleting(null);
      setNotice(`${title} record deleted.`);
      setReloadKey((key) => key + 1);
    } else setMutationError(result.message);
    setBusy(false);
  };

  return (
    <div className="page-stack records-page">
      {showHeader && (
        <header className="domain-header">
          <div>
            <p className="eyebrow">{eyebrow}</p>
            <h1>{title}</h1>
            <p>{description}</p>
          </div>
          <button
            className="button button-secondary"
            type="button"
            disabled={!records.length}
            onClick={() => exportCsv(domain, records)}
          >
            <Download size={15} /> Export CSV
          </button>
        </header>
      )}
      {notice && (
        <div className="chat-success" role="status">
          {notice}
        </div>
      )}
      <form
        className="filter-bar"
        onSubmit={(event) => {
          event.preventDefault();
          setFilters(draftFilters);
          setPage(1);
        }}
      >
        <label>
          <span>Search</span>
          <input
            type="search"
            value={draftFilters.search}
            placeholder={`Search ${domain} records`}
            onChange={(event) => setDraftFilters({ ...draftFilters, search: event.target.value })}
          />
        </label>
        <label>
          <span>From</span>
          <input
            type="date"
            value={draftFilters.start_date}
            onChange={(event) =>
              setDraftFilters({ ...draftFilters, start_date: event.target.value })
            }
          />
        </label>
        <label>
          <span>To</span>
          <input
            type="date"
            value={draftFilters.end_date}
            onChange={(event) => setDraftFilters({ ...draftFilters, end_date: event.target.value })}
          />
        </label>
        <label>
          <span>
            {domain === "wealth" ? "Category" : domain === "health" ? "Workout" : "Topic"}
          </span>
          <input
            value={draftFilters.detail}
            onChange={(event) => setDraftFilters({ ...draftFilters, detail: event.target.value })}
          />
        </label>
        <button className="button button-primary" type="submit">
          <Search size={15} /> Apply
        </button>
        <button
          className="button button-secondary"
          type="button"
          onClick={() => {
            setDraftFilters(emptyFilters);
            setFilters(emptyFilters);
            setPage(1);
          }}
        >
          Clear
        </button>
      </form>

      {loading ? (
        <LoadingState label={`Loading ${domain} history`} />
      ) : error ? (
        <ErrorState
          title={`${title} unavailable`}
          message={error}
          actionLabel="Try again"
          onAction={() => setReloadKey((key) => key + 1)}
        />
      ) : records.length === 0 ? (
        <EmptyState
          title={`No ${domain} records`}
          message="Adjust the filters or capture a new entry with the Copilot."
          actionHref="/chat"
          actionLabel="Open Copilot"
        />
      ) : (
        <>
          <section className="domain-overview" aria-label={`${title} summary`}>
            {domain === "wealth" && (
              <>
                <label className="compact-select">
                  Currency
                  <select
                    value={currency}
                    onChange={(event) => setSelectedCurrency(event.target.value)}
                  >
                    {currencies.map((item) => (
                      <option key={item}>{item}</option>
                    ))}
                  </select>
                </label>
                <div className="overview-metrics">
                  <div>
                    <span>Income</span>
                    <strong>{formatMoney(currency, income)}</strong>
                  </div>
                  <div>
                    <span>Expenses</span>
                    <strong>{formatMoney(currency, expense)}</strong>
                  </div>
                  <div>
                    <span>Net</span>
                    <strong>{formatMoney(currency, income - expense)}</strong>
                  </div>
                  <div>
                    <span>Transactions</span>
                    <strong>{wealthMetrics.length}</strong>
                  </div>
                </div>
              </>
            )}
            {domain === "health" && (
              <div className="overview-metrics">
                <div>
                  <span>Average sleep</span>
                  <strong>
                    {sleep.length
                      ? `${(sleep.reduce((a, b) => a + b, 0) / sleep.length).toFixed(1)} h`
                      : "Not logged"}
                  </strong>
                </div>
                <div>
                  <span>Average calories</span>
                  <strong>
                    {calories.length
                      ? Math.round(
                          calories.reduce((a, b) => a + b, 0) / calories.length,
                        ).toLocaleString()
                      : "Not logged"}
                  </strong>
                </div>
                <div>
                  <span>Workout days</span>
                  <strong>{health.filter((record) => record.workout_type).length}</strong>
                </div>
                <div>
                  <span>Entries</span>
                  <strong>{health.length}</strong>
                </div>
              </div>
            )}
            {domain === "learning" && (
              <div className="overview-metrics">
                <div>
                  <span>Learning minutes</span>
                  <strong>
                    {learning.reduce((sum, record) => sum + (record.duration_minutes ?? 0), 0)}
                  </strong>
                </div>
                <div>
                  <span>Sessions</span>
                  <strong>{learning.length}</strong>
                </div>
                <div>
                  <span>Active days</span>
                  <strong>{new Set(learning.map((record) => record.entry_date)).size}</strong>
                </div>
                <div>
                  <span>Topics</span>
                  <strong>
                    {new Set(learning.map((record) => record.topic.toLowerCase())).size}
                  </strong>
                </div>
              </div>
            )}
            <div className="chart-frame" role="img" aria-label={`${title} activity by date`}>
              <ResponsiveContainer width="100%" height={240}>
                {domain === "wealth" ? (
                  <BarChart data={chartData}>
                    <CartesianGrid stroke="var(--border)" vertical={false} />
                    <XAxis dataKey="date" stroke="var(--text-muted)" />
                    <YAxis stroke="var(--text-muted)" />
                    <Tooltip />
                    <Bar dataKey="value" fill="var(--coral)" />
                  </BarChart>
                ) : (
                  <LineChart data={chartData}>
                    <CartesianGrid stroke="var(--border)" vertical={false} />
                    <XAxis dataKey="date" stroke="var(--text-muted)" />
                    <YAxis stroke="var(--text-muted)" />
                    <Tooltip />
                    <Line
                      dataKey="value"
                      stroke={domain === "health" ? "var(--green)" : "var(--blue)"}
                      strokeWidth={2.5}
                    />
                  </LineChart>
                )}
              </ResponsiveContainer>
            </div>
          </section>

          <section className="records-table-card" aria-labelledby={`${domain}-records-title`}>
            <div className="table-heading">
              <div>
                <p className="eyebrow">Source records</p>
                <h2 id={`${domain}-records-title`}>{title} history</h2>
              </div>
              <button
                className="refresh-link"
                type="button"
                onClick={() => setReloadKey((key) => key + 1)}
              >
                <RefreshCw size={14} /> Refresh
              </button>
            </div>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Details</th>
                    <th>Source</th>
                    <th>
                      <span className="sr-only">Actions</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {pageRecords.map((record) => (
                    <tr key={record.id}>
                      <td>{record.entry_date}</td>
                      <td>{recordLabel(domain, record)}</td>
                      <td>
                        <span className="source-pill">{record.source}</span>
                      </td>
                      <td>
                        <div className="row-actions">
                          <button
                            type="button"
                            aria-label={`Edit record ${record.id}`}
                            onClick={() => {
                              setEditing(record);
                              setDeleting(null);
                            }}
                          >
                            <Pencil size={14} />
                          </button>
                          <button
                            type="button"
                            aria-label={`Delete record ${record.id}`}
                            onClick={() => {
                              setDeleting(record);
                              setEditing(null);
                            }}
                          >
                            <Trash2 size={14} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="pagination">
              <label>
                Rows
                <select
                  value={pageSize}
                  onChange={(event) => {
                    setPageSize(Number(event.target.value));
                    setPage(1);
                  }}
                >
                  <option>10</option>
                  <option>25</option>
                  <option>50</option>
                </select>
              </label>
              <span>
                Page {Math.min(page, totalPages)} of {totalPages} · {records.length} records
              </span>
              <div>
                <button
                  type="button"
                  disabled={page <= 1}
                  onClick={() => setPage((current) => current - 1)}
                >
                  Previous
                </button>
                <button
                  type="button"
                  disabled={page >= totalPages}
                  onClick={() => setPage((current) => current + 1)}
                >
                  Next
                </button>
              </div>
            </div>
          </section>
        </>
      )}

      {editing && (
        <RecordEditor
          domain={domain}
          record={editing}
          busy={busy}
          error={mutationError}
          onSave={(patch) => void save(patch)}
          onCancel={() => {
            setEditing(null);
            setMutationError(null);
          }}
        />
      )}
      {deleting && (
        <section
          className="delete-confirm"
          role="alertdialog"
          aria-labelledby="delete-title"
          aria-describedby="delete-description"
        >
          <h2 id="delete-title">Delete record #{deleting.id}?</h2>
          <p id="delete-description">
            This permanently removes the record and recalculates daily status. This cannot be
            undone.
          </p>
          {mutationError && <p className="form-error">{mutationError}</p>}
          <div className="form-actions">
            <button
              className="button button-secondary"
              type="button"
              onClick={() => {
                setDeleting(null);
                setMutationError(null);
              }}
            >
              Keep record
            </button>
            <button
              className="button button-danger"
              type="button"
              disabled={busy}
              onClick={() => void remove()}
            >
              {busy ? "Deleting…" : "Delete permanently"}
            </button>
          </div>
        </section>
      )}
    </div>
  );
}
