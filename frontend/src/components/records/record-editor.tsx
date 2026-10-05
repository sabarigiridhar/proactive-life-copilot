"use client";

import { Save, X } from "lucide-react";
import { useState } from "react";
import type { DomainRecord, RecordDomain, RecordPatch } from "@/lib/api/client";

function text(value: FormDataEntryValue | null): string | null {
  const cleaned = String(value ?? "").trim();
  return cleaned || null;
}

function number(value: FormDataEntryValue | null): number | null {
  const cleaned = String(value ?? "").trim();
  return cleaned ? Number(cleaned) : null;
}

export function RecordEditor({
  domain,
  record,
  busy,
  error,
  onSave,
  onCancel,
}: Readonly<{
  domain: RecordDomain;
  record: DomainRecord;
  busy: boolean;
  error?: string | null;
  onSave: (patch: RecordPatch) => void;
  onCancel: () => void;
}>) {
  const [entryDate, setEntryDate] = useState(record.entry_date);

  const submit = (form: FormData) => {
    const base = { entry_date: entryDate };
    if (domain === "wealth") {
      onSave({
        ...base,
        transaction_type: String(form.get("transaction_type")) as "Income" | "Expense",
        amount: number(form.get("amount")),
        currency: text(form.get("currency")),
        category: text(form.get("category")),
        merchant: text(form.get("merchant")),
        notes: text(form.get("notes")),
      });
    } else if (domain === "health") {
      onSave({
        ...base,
        sleep_hours: number(form.get("sleep_hours")),
        workout_type: text(form.get("workout_type")),
        calories_consumed: number(form.get("calories_consumed")),
        notes: text(form.get("notes")),
      });
    } else {
      onSave({
        ...base,
        topic: text(form.get("topic")),
        summary_text: text(form.get("summary_text")),
        duration_minutes: number(form.get("duration_minutes")),
        url_reference: text(form.get("url_reference")),
      });
    }
  };

  return (
    <section className="record-editor" aria-labelledby="record-editor-title">
      <div className="modal-heading">
        <div>
          <p className="eyebrow">Record #{record.id}</p>
          <h2 id="record-editor-title">Edit {domain} record</h2>
        </div>
        <button
          className="icon-button"
          type="button"
          aria-label="Close record editor"
          onClick={onCancel}
        >
          <X size={18} />
        </button>
      </div>
      <form action={submit} className="record-form">
        <label>
          Entry date
          <input
            type="date"
            name="entry_date"
            required
            value={entryDate}
            onChange={(event) => setEntryDate(event.target.value)}
          />
        </label>
        {domain === "wealth" && "amount" in record && (
          <>
            <label>
              Type
              <select name="transaction_type" defaultValue={record.transaction_type}>
                <option>Expense</option>
                <option>Income</option>
              </select>
            </label>
            <label>
              Amount
              <input
                type="number"
                name="amount"
                min="0.01"
                step="0.01"
                required
                defaultValue={record.amount}
              />
            </label>
            <label>
              Currency
              <input name="currency" required maxLength={8} defaultValue={record.currency} />
            </label>
            <label>
              Category
              <input name="category" required maxLength={100} defaultValue={record.category} />
            </label>
            <label>
              Merchant
              <input name="merchant" maxLength={200} defaultValue={record.merchant ?? ""} />
            </label>
            <label className="full-width">
              Notes
              <textarea name="notes" rows={3} maxLength={2000} defaultValue={record.notes ?? ""} />
            </label>
          </>
        )}
        {domain === "health" && "sleep_hours" in record && (
          <>
            <label>
              Sleep hours
              <input
                type="number"
                name="sleep_hours"
                min="0"
                max="24"
                step="0.1"
                defaultValue={record.sleep_hours ?? ""}
              />
            </label>
            <label>
              Workout
              <input name="workout_type" maxLength={200} defaultValue={record.workout_type ?? ""} />
            </label>
            <label>
              Calories
              <input
                type="number"
                name="calories_consumed"
                min="0"
                max="20000"
                defaultValue={record.calories_consumed ?? ""}
              />
            </label>
            <label className="full-width">
              Notes
              <textarea name="notes" rows={3} maxLength={2000} defaultValue={record.notes ?? ""} />
            </label>
          </>
        )}
        {domain === "learning" && "topic" in record && (
          <>
            <label>
              Topic
              <input name="topic" required maxLength={200} defaultValue={record.topic} />
            </label>
            <label>
              Duration (minutes)
              <input
                type="number"
                name="duration_minutes"
                min="0"
                max="1440"
                defaultValue={record.duration_minutes ?? ""}
              />
            </label>
            <label className="full-width">
              Summary
              <textarea
                name="summary_text"
                required
                rows={4}
                maxLength={10000}
                defaultValue={record.summary_text ?? ""}
              />
            </label>
            <label className="full-width">
              Source URL
              <input
                type="url"
                name="url_reference"
                maxLength={2000}
                defaultValue={record.url_reference ?? ""}
              />
            </label>
          </>
        )}
        {error && (
          <p className="form-error full-width" role="alert">
            {error}
          </p>
        )}
        <div className="form-actions full-width">
          <button className="button button-secondary" type="button" onClick={onCancel}>
            Cancel
          </button>
          <button className="button button-primary" type="submit" disabled={busy}>
            <Save size={15} /> {busy ? "Saving…" : "Save changes"}
          </button>
        </div>
      </form>
    </section>
  );
}
