"use client";

import { ExternalLink, Search } from "lucide-react";
import { useState } from "react";
import { RecordsWorkspace } from "@/components/records/records-workspace";
import { type LearningSearchResult, searchLearning } from "@/lib/api/client";

function safeUrl(value?: string | null): string | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:" ? value : null;
  } catch {
    return null;
  }
}

export function LearningWorkspace() {
  const [query, setQuery] = useState("");
  const [topic, setTopic] = useState("");
  const [result, setResult] = useState<LearningSearchResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const hits = result?.hits ?? [];

  const search = async () => {
    if (!query.trim()) return;
    setBusy(true);
    setError(null);
    const response = await searchLearning(query.trim(), { topic: topic.trim() || undefined });
    if (response.ok) setResult(response.data);
    else setError(response.message);
    setBusy(false);
  };

  return (
    <div className="page-stack learning-page">
      <header className="domain-header">
        <div>
          <p className="eyebrow">Knowledge and recall</p>
          <h1>Learning</h1>
          <p>Browse sessions and search verified notes with their source evidence.</p>
        </div>
      </header>
      <section className="semantic-search" aria-labelledby="semantic-search-title">
        <div>
          <p className="eyebrow">Verified retrieval</p>
          <h2 id="semantic-search-title">Search your notes</h2>
          <p>Find related ideas even when your wording is different.</p>
        </div>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            void search();
          }}
        >
          <label>
            <span>Question or concept</span>
            <input
              type="search"
              required
              value={query}
              placeholder="What did I learn about retrieval quality?"
              onChange={(event) => setQuery(event.target.value)}
            />
          </label>
          <label>
            <span>Topic (optional)</span>
            <input value={topic} onChange={(event) => setTopic(event.target.value)} />
          </label>
          <button className="button button-primary" type="submit" disabled={busy || !query.trim()}>
            <Search size={15} /> {busy ? "Searching…" : "Search notes"}
          </button>
        </form>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        {result && (
          <div className="search-results" aria-live="polite">
            <p className="result-caption">
              {hits.length} verified result{hits.length === 1 ? "" : "s"} ·{" "}
              {result.mode === "vector" ? "Semantic index" : "Keyword fallback"}
            </p>
            {result.warning && <p className="search-warning">{result.warning}</p>}
            {hits.length === 0 ? (
              <p className="inline-empty">No learning notes matched this search.</p>
            ) : (
              hits.map((hit) => {
                const source = safeUrl(hit.url_reference);
                return (
                  <article className="search-hit" key={hit.record_id}>
                    <div>
                      <span>
                        {hit.entry_date}
                        {hit.duration_minutes == null ? "" : ` · ${hit.duration_minutes} minutes`}
                      </span>
                      <h3>{hit.topic}</h3>
                    </div>
                    <p>{hit.summary_text}</p>
                    {source ? (
                      <a className="text-link" href={source} target="_blank" rel="noreferrer">
                        Open source <ExternalLink size={14} />
                      </a>
                    ) : hit.url_reference ? (
                      <small>Source reference: {hit.url_reference}</small>
                    ) : null}
                  </article>
                );
              })
            )}
          </div>
        )}
      </section>
      <RecordsWorkspace domain="learning" showHeader={false} />
    </div>
  );
}
