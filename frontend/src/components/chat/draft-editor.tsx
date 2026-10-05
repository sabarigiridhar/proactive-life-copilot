"use client";

import { Plus, Save, Trash2, X } from "lucide-react";
import { useEffect, useState } from "react";
import type { DailyLogDraft } from "@/lib/api/client";

type Health = NonNullable<DailyLogDraft["health"]>;
type Wealth = NonNullable<DailyLogDraft["wealth"]>[number];
type Learning = NonNullable<DailyLogDraft["learning"]>[number];

function optionalNumber(value: string): number | null {
  return value === "" ? null : Number(value);
}

export function DraftEditor({
  draft,
  busy,
  error,
  onConfirm,
  onCancel,
}: Readonly<{
  draft: DailyLogDraft;
  busy: boolean;
  error?: string | null;
  onConfirm: (draft: DailyLogDraft) => void;
  onCancel: () => void;
}>) {
  const [working, setWorking] = useState<DailyLogDraft>(draft);

  useEffect(() => setWorking(draft), [draft]);

  const updateHealth = (patch: Partial<Health>) => {
    setWorking(
      (current) => ({ ...current, health: { ...current.health, ...patch } }) as DailyLogDraft,
    );
  };
  const updateWealth = (index: number, patch: Partial<Wealth>) => {
    setWorking((current) => ({
      ...current,
      wealth: (current.wealth ?? []).map((item, itemIndex) =>
        itemIndex === index ? { ...item, ...patch } : item,
      ),
    }));
  };
  const updateLearning = (index: number, patch: Partial<Learning>) => {
    setWorking((current) => ({
      ...current,
      learning: (current.learning ?? []).map((item, itemIndex) =>
        itemIndex === index ? { ...item, ...patch } : item,
      ),
    }));
  };

  return (
    <section className="draft-review" aria-labelledby="draft-title">
      <div className="draft-heading">
        <div>
          <p className="eyebrow">Review before saving</p>
          <h2 id="draft-title">Confirm extracted records</h2>
          <p>Edit anything the Copilot misunderstood. Nothing is saved until you confirm.</p>
        </div>
        <button
          className="icon-button"
          type="button"
          aria-label="Close draft review"
          onClick={onCancel}
        >
          <X size={18} aria-hidden="true" />
        </button>
      </div>

      <form
        className="draft-form"
        onSubmit={(event) => {
          event.preventDefault();
          onConfirm(working);
        }}
      >
        <div className="draft-meta-grid">
          <label>
            Entry date
            <input
              type="date"
              required
              value={working.entry_date}
              onChange={(event) => setWorking({ ...working, entry_date: event.target.value })}
            />
          </label>
          <div className="draft-confidence">
            <span>Extraction confidence</span>
            <strong>{Math.round((working.confidence ?? 0) * 100)}%</strong>
          </div>
        </div>

        {working.ambiguities && working.ambiguities.length > 0 && (
          <div className="draft-ambiguities" role="note">
            <strong>Please check:</strong> {working.ambiguities.join(" · ")}
          </div>
        )}

        {working.health ? (
          <fieldset className="draft-group">
            <legend>Health</legend>
            <button
              className="draft-remove"
              type="button"
              onClick={() => setWorking({ ...working, health: null })}
            >
              <Trash2 size={14} aria-hidden="true" /> Remove health
            </button>
            <div className="draft-fields four-columns">
              <label>
                Sleep hours
                <input
                  type="number"
                  min="0"
                  max="24"
                  step="0.1"
                  value={working.health.sleep_hours ?? ""}
                  onChange={(event) =>
                    updateHealth({ sleep_hours: optionalNumber(event.target.value) })
                  }
                />
              </label>
              <label>
                Workout
                <input
                  type="text"
                  maxLength={200}
                  value={working.health.workout_type ?? ""}
                  onChange={(event) => updateHealth({ workout_type: event.target.value || null })}
                />
              </label>
              <label>
                Calories
                <input
                  type="number"
                  min="0"
                  max="20000"
                  value={working.health.calories_consumed ?? ""}
                  onChange={(event) =>
                    updateHealth({ calories_consumed: optionalNumber(event.target.value) })
                  }
                />
              </label>
              <label>
                Notes
                <input
                  type="text"
                  maxLength={2000}
                  value={working.health.notes ?? ""}
                  onChange={(event) => updateHealth({ notes: event.target.value || null })}
                />
              </label>
            </div>
          </fieldset>
        ) : (
          <button
            className="button button-secondary draft-add"
            type="button"
            onClick={() => setWorking({ ...working, health: { notes: "Health check-in" } })}
          >
            <Plus size={15} aria-hidden="true" /> Add health record
          </button>
        )}

        <fieldset className="draft-group">
          <legend>Wealth</legend>
          {(working.wealth ?? []).map((item, index) => (
            // biome-ignore lint/suspicious/noArrayIndexKey: Extracted draft records have no stable IDs and all fields are controlled.
            <div className="draft-record" key={`wealth-${index}-${item.category}`}>
              <button
                className="draft-remove"
                type="button"
                aria-label={`Remove wealth record ${index + 1}`}
                onClick={() =>
                  setWorking({
                    ...working,
                    wealth: (working.wealth ?? []).filter((_, itemIndex) => itemIndex !== index),
                  })
                }
              >
                <Trash2 size={14} aria-hidden="true" /> Remove
              </button>
              <div className="draft-fields three-columns">
                <label>
                  Type
                  <select
                    value={item.transaction_type}
                    onChange={(event) =>
                      updateWealth(index, {
                        transaction_type: event.target.value as "Income" | "Expense",
                      })
                    }
                  >
                    <option>Expense</option>
                    <option>Income</option>
                  </select>
                </label>
                <label>
                  Amount
                  <input
                    type="number"
                    required
                    min="0.01"
                    step="0.01"
                    value={item.amount}
                    onChange={(event) =>
                      updateWealth(index, { amount: Number(event.target.value) })
                    }
                  />
                </label>
                <label>
                  Currency
                  <input
                    type="text"
                    required
                    maxLength={8}
                    value={item.currency ?? "INR"}
                    onChange={(event) =>
                      updateWealth(index, { currency: event.target.value.toUpperCase() })
                    }
                  />
                </label>
                <label>
                  Category
                  <input
                    type="text"
                    required
                    maxLength={100}
                    value={item.category}
                    onChange={(event) => updateWealth(index, { category: event.target.value })}
                  />
                </label>
                <label>
                  Merchant
                  <input
                    type="text"
                    maxLength={200}
                    value={item.merchant ?? ""}
                    onChange={(event) =>
                      updateWealth(index, { merchant: event.target.value || null })
                    }
                  />
                </label>
                <label>
                  Notes
                  <input
                    type="text"
                    maxLength={2000}
                    value={item.notes ?? ""}
                    onChange={(event) => updateWealth(index, { notes: event.target.value || null })}
                  />
                </label>
              </div>
            </div>
          ))}
          <button
            className="draft-inline-add"
            type="button"
            onClick={() =>
              setWorking({
                ...working,
                wealth: [
                  ...(working.wealth ?? []),
                  { transaction_type: "Expense", amount: 0.01, currency: "INR", category: "Other" },
                ],
              })
            }
          >
            <Plus size={14} aria-hidden="true" /> Add transaction
          </button>
        </fieldset>

        <fieldset className="draft-group">
          <legend>Learning</legend>
          {(working.learning ?? []).map((item, index) => (
            // biome-ignore lint/suspicious/noArrayIndexKey: Extracted draft records have no stable IDs and all fields are controlled.
            <div className="draft-record" key={`learning-${index}-${item.topic}`}>
              <button
                className="draft-remove"
                type="button"
                aria-label={`Remove learning record ${index + 1}`}
                onClick={() =>
                  setWorking({
                    ...working,
                    learning: (working.learning ?? []).filter(
                      (_, itemIndex) => itemIndex !== index,
                    ),
                  })
                }
              >
                <Trash2 size={14} aria-hidden="true" /> Remove
              </button>
              <div className="draft-fields two-columns">
                <label>
                  Topic
                  <input
                    type="text"
                    required
                    maxLength={200}
                    value={item.topic}
                    onChange={(event) => updateLearning(index, { topic: event.target.value })}
                  />
                </label>
                <label>
                  Duration (minutes)
                  <input
                    type="number"
                    min="0"
                    max="1440"
                    value={item.duration_minutes ?? ""}
                    onChange={(event) =>
                      updateLearning(index, {
                        duration_minutes: optionalNumber(event.target.value),
                      })
                    }
                  />
                </label>
                <label className="full-width">
                  Summary
                  <textarea
                    required
                    rows={3}
                    maxLength={10_000}
                    value={item.summary_text}
                    onChange={(event) =>
                      updateLearning(index, { summary_text: event.target.value })
                    }
                  />
                </label>
                <label className="full-width">
                  Source URL
                  <input
                    type="url"
                    maxLength={2000}
                    value={item.url_reference ?? ""}
                    onChange={(event) =>
                      updateLearning(index, { url_reference: event.target.value || null })
                    }
                  />
                </label>
              </div>
            </div>
          ))}
          <button
            className="draft-inline-add"
            type="button"
            onClick={() =>
              setWorking({
                ...working,
                learning: [
                  ...(working.learning ?? []),
                  { topic: "New topic", summary_text: "Add what you learned." },
                ],
              })
            }
          >
            <Plus size={14} aria-hidden="true" /> Add learning session
          </button>
        </fieldset>

        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        <div className="draft-actions">
          <button
            className="button button-secondary"
            type="button"
            disabled={busy}
            onClick={onCancel}
          >
            Cancel
          </button>
          <button className="button button-primary" type="submit" disabled={busy}>
            <Save size={16} aria-hidden="true" /> {busy ? "Saving…" : "Confirm and save"}
          </button>
        </div>
      </form>
    </section>
  );
}
