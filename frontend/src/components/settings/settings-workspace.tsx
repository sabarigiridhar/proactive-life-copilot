"use client";

import {
  Archive,
  CheckCircle2,
  DatabaseBackup,
  Save,
  ShieldCheck,
  TriangleAlert,
} from "lucide-react";
import { useEffect, useState } from "react";
import { ErrorState } from "@/components/feedback/error-state";
import { LoadingState } from "@/components/feedback/loading-state";
import {
  type BackupData,
  createBackup,
  type DomainRecord,
  getSettings,
  listAllRecords,
  type RecordDomain,
  type SettingsData,
  type SettingsPatch,
  updateSettings,
} from "@/lib/api/client";
import { isoDate } from "@/lib/dashboard";
import { createRecordsArchive } from "@/lib/records-export";

type PreferenceDraft = {
  default_currency: string;
  weekly_spending_limit: string;
  weekly_learning_minutes: string;
  weekly_workouts: string;
  sleep_hours_target: string;
};

function draftFromSettings(data: SettingsData): PreferenceDraft {
  const preferences = data.preferences;
  return {
    default_currency: preferences.default_currency,
    weekly_spending_limit: preferences.weekly_spending_limit?.toString() ?? "",
    weekly_learning_minutes: preferences.weekly_learning_minutes.toString(),
    weekly_workouts: preferences.weekly_workouts.toString(),
    sleep_hours_target: preferences.sleep_hours_target.toString(),
  };
}

export function SettingsWorkspace() {
  const [data, setData] = useState<SettingsData | null>(null);
  const [draft, setDraft] = useState<PreferenceDraft | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [saving, setSaving] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [backingUp, setBackingUp] = useState(false);
  const [backup, setBackup] = useState<BackupData | null>(null);

  useEffect(() => {
    void reloadKey;
    let cancelled = false;
    const load = async () => {
      const result = await getSettings();
      if (cancelled) return;
      if (result.ok) {
        setData(result.data);
        setDraft(draftFromSettings(result.data));
        setError(null);
      } else setError(result.message);
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  const save = async () => {
    if (!draft) return;
    const currency = draft.default_currency.trim().toUpperCase();
    if (currency.length < 3) {
      setError("Enter a currency code with at least three characters.");
      return;
    }
    const patch: SettingsPatch = {
      default_currency: currency,
      weekly_spending_limit: draft.weekly_spending_limit
        ? Number(draft.weekly_spending_limit)
        : null,
      weekly_learning_minutes: Number(draft.weekly_learning_minutes),
      weekly_workouts: Number(draft.weekly_workouts),
      sleep_hours_target: Number(draft.sleep_hours_target),
    };
    setSaving(true);
    setError(null);
    const result = await updateSettings(patch);
    if (result.ok) {
      setData(result.data);
      setDraft(draftFromSettings(result.data));
      setNotice("Settings saved.");
    } else setError(result.message);
    setSaving(false);
  };

  const exportRecords = async () => {
    setExporting(true);
    setError(null);
    const domains: RecordDomain[] = ["wealth", "health", "learning"];
    const results = await Promise.all(domains.map((domain) => listAllRecords(domain)));
    const failure = results.find((result) => !result.ok);
    if (failure && !failure.ok) {
      setError(failure.message);
      setExporting(false);
      return;
    }
    const records: Record<RecordDomain, DomainRecord[]> = {
      wealth: [],
      health: [],
      learning: [],
    };
    domains.forEach((domain, index) => {
      const result = results[index];
      if (result.ok) records[domain] = result.data;
    });
    const blob = await createRecordsArchive(records);
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `life-copilot-records-${isoDate(new Date())}.zip`;
    link.click();
    URL.revokeObjectURL(url);
    setNotice("Records export prepared.");
    setExporting(false);
  };

  const createSnapshot = async () => {
    setBackingUp(true);
    setError(null);
    const result = await createBackup();
    if (result.ok) {
      setBackup(result.data);
      setNotice(`Created ${result.data.backup_name}.`);
    } else setError(result.message);
    setBackingUp(false);
  };

  if (!data || !draft) {
    if (error)
      return (
        <ErrorState
          title="Settings unavailable"
          message={error}
          actionLabel="Try again"
          onAction={() => setReloadKey((key) => key + 1)}
        />
      );
    return <LoadingState label="Loading settings" />;
  }

  return (
    <div className="page-stack settings-page">
      <header className="domain-header">
        <div>
          <p className="eyebrow">Preferences and data</p>
          <h1>Settings</h1>
          <p>Manage weekly targets, provider readiness, portable exports, and local snapshots.</p>
        </div>
      </header>
      {notice && (
        <div className="chat-success" role="status">
          {notice}
        </div>
      )}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}

      <section className="settings-card" aria-labelledby="preference-title">
        <div className="settings-heading">
          <div>
            <span className="card-icon">
              <Save size={17} />
            </span>
            <div>
              <p className="eyebrow">Personal defaults</p>
              <h2 id="preference-title">Preferences and weekly targets</h2>
            </div>
          </div>
          <small>Last updated {new Date(data.preferences.updated_at).toLocaleString()}</small>
        </div>
        <form
          className="settings-form"
          onSubmit={(event) => {
            event.preventDefault();
            void save();
          }}
        >
          <label>
            <span>Preferred currency</span>
            <input
              required
              minLength={3}
              maxLength={8}
              value={draft.default_currency}
              onChange={(event) => setDraft({ ...draft, default_currency: event.target.value })}
            />
          </label>
          <label>
            <span>Weekly spending limit</span>
            <input
              type="number"
              min="0"
              step="100"
              placeholder="No limit"
              value={draft.weekly_spending_limit}
              onChange={(event) =>
                setDraft({ ...draft, weekly_spending_limit: event.target.value })
              }
            />
          </label>
          <label>
            <span>Weekly learning minutes</span>
            <input
              type="number"
              min="0"
              max="10080"
              step="15"
              required
              value={draft.weekly_learning_minutes}
              onChange={(event) =>
                setDraft({ ...draft, weekly_learning_minutes: event.target.value })
              }
            />
          </label>
          <label>
            <span>Weekly workouts</span>
            <input
              type="number"
              min="0"
              max="14"
              required
              value={draft.weekly_workouts}
              onChange={(event) => setDraft({ ...draft, weekly_workouts: event.target.value })}
            />
          </label>
          <label>
            <span>Sleep target (hours)</span>
            <input
              type="number"
              min="0"
              max="24"
              step="0.5"
              required
              value={draft.sleep_hours_target}
              onChange={(event) => setDraft({ ...draft, sleep_hours_target: event.target.value })}
            />
          </label>
          <button className="button button-primary" type="submit" disabled={saving}>
            <Save size={15} /> {saving ? "Saving…" : "Save settings"}
          </button>
        </form>
      </section>

      <section className="settings-card" aria-labelledby="provider-title">
        <div className="settings-heading">
          <div>
            <span className="card-icon blue">
              <ShieldCheck size={17} />
            </span>
            <div>
              <p className="eyebrow">Safe status only</p>
              <h2 id="provider-title">Model configuration</h2>
            </div>
          </div>
          <small>API keys are never displayed.</small>
        </div>
        <div className="provider-grid">
          {data.providers.map((provider) => (
            <article className="provider-card" key={`${provider.provider}-${provider.capability}`}>
              <div>
                <strong>{provider.provider}</strong>
                <span>{provider.capability}</span>
              </div>
              <code>{provider.model}</code>
              <span className={provider.configured ? "provider-ready" : "provider-missing"}>
                {provider.configured ? <CheckCircle2 size={14} /> : <TriangleAlert size={14} />}
                {provider.configured ? "Configured" : "Missing"}
              </span>
            </article>
          ))}
        </div>
      </section>

      <section className="settings-card" aria-labelledby="data-tools-title">
        <div className="settings-heading">
          <div>
            <span className="card-icon green">
              <DatabaseBackup size={17} />
            </span>
            <div>
              <p className="eyebrow">Local-first controls</p>
              <h2 id="data-tools-title">Data tools</h2>
            </div>
          </div>
        </div>
        <div className="data-tool-grid">
          <article>
            <Archive className="data-tool-icon" size={21} />
            <h3>Portable records export</h3>
            <p>
              Download public record fields as JSON plus separate wealth, health, and learning CSV
              files. Original private inputs and chats are excluded.
            </p>
            <button
              className="button button-secondary"
              type="button"
              disabled={exporting}
              onClick={() => void exportRecords()}
            >
              {exporting ? "Preparing…" : "Download records ZIP"}
            </button>
          </article>
          <article>
            <DatabaseBackup className="data-tool-icon" size={21} />
            <h3>Local data snapshot</h3>
            <p>
              Copy the SQLite database and learning vector index into the local backups directory.
            </p>
            <button
              className="button button-secondary"
              type="button"
              disabled={backingUp}
              onClick={() => void createSnapshot()}
            >
              {backingUp ? "Creating…" : "Create local snapshot"}
            </button>
            {backup && (
              <div className="snapshot-result">
                <strong>{backup.backup_name}</strong>
                <span>Includes: {backup.includes.join(", ")}</span>
                {(backup.warnings ?? []).map((warning) => (
                  <span className="provider-missing" key={warning}>
                    <TriangleAlert size={13} /> {warning}
                  </span>
                ))}
              </div>
            )}
          </article>
        </div>
      </section>
    </div>
  );
}
