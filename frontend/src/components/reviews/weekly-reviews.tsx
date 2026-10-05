"use client";

import { CalendarDays, ChevronDown, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";
import { EmptyState } from "@/components/feedback/empty-state";
import { ErrorState } from "@/components/feedback/error-state";
import { LoadingState } from "@/components/feedback/loading-state";
import { getWeeklyReviews, type WeeklyReviewsData } from "@/lib/api/client";

type WeeklyReview = NonNullable<WeeklyReviewsData["reviews"]>[number];

function ReviewCard({ review }: Readonly<{ review: WeeklyReview }>) {
  const evidence = review.evidence ?? [];
  const columns = Object.keys(evidence[0] ?? {});

  return (
    <article className="review-card">
      <div className="review-heading">
        <span className="card-icon">
          <CalendarDays size={17} />
        </span>
        <div>
          <p>
            {review.period_start} — {review.period_end}
          </p>
          <h2>{review.title}</h2>
          <small>Created {new Date(review.created_at).toLocaleString()}</small>
        </div>
      </div>
      <p className="review-summary">{review.summary}</p>
      <details className="review-evidence" open>
        <summary>
          Supporting evidence <ChevronDown size={15} />
        </summary>
        {evidence.length === 0 ? (
          <p>No supporting evidence was stored for this review.</p>
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  {columns.map((key) => (
                    <th key={key}>{key.replaceAll("_", " ")}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {evidence.map((row) => (
                  <tr key={`${review.id}-${JSON.stringify(row)}`}>
                    {columns.map((key) => (
                      <td key={key}>{String(row[key] ?? "")}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </details>
    </article>
  );
}

export function WeeklyReviews() {
  const [data, setData] = useState<WeeklyReviewsData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    void reloadKey;
    let cancelled = false;
    const load = async () => {
      const result = await getWeeklyReviews();
      if (cancelled) return;
      if (result.ok) setData(result.data);
      else setError(result.message);
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  if (error)
    return (
      <ErrorState
        title="Weekly reviews unavailable"
        message={error}
        actionLabel="Try again"
        onAction={() => {
          setError(null);
          setReloadKey((key) => key + 1);
        }}
      />
    );
  if (!data) return <LoadingState label="Loading weekly reviews" />;
  const reviews = data.reviews ?? [];

  return (
    <div className="page-stack review-page">
      <header className="domain-header">
        <div>
          <p className="eyebrow">Patterns and reflection</p>
          <h1>Weekly Review</h1>
          <p>Read reproducible insights alongside the records and metrics behind them.</p>
        </div>
        <span className="review-count">
          <Sparkles size={15} /> {reviews.length} saved
        </span>
      </header>
      {reviews.length === 0 ? (
        <EmptyState
          title="No weekly reviews yet"
          message={
            data.message ?? "Scheduled review generation arrives in the Proactive Copilot phase."
          }
          actionHref="/"
          actionLabel="Return home"
        />
      ) : (
        <div className="review-list">
          {reviews.map((review) => (
            <ReviewCard key={review.id} review={review} />
          ))}
        </div>
      )}
    </div>
  );
}
