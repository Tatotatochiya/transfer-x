import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import api from "../../lib/api";
import type { AIUsageStats, PromptInfo } from "../../types/api";
import PageHeader from "../../components/ui/PageHeader";
import Spinner from "../../components/ui/Spinner";
import Badge from "../../components/ui/Badge";
import { useSuggestionStats } from "../../hooks/useAssistant";

export default function AdminAIPage() {
  const qc = useQueryClient();

  const { data: usage, isLoading: usageLoading } = useQuery<AIUsageStats>({
    queryKey: ["admin", "ai", "usage"],
    queryFn: () => api.get<AIUsageStats>("/ai/usage").then((r) => r.data),
    refetchInterval: 30_000,
  });

  const { data: prompts, isLoading: promptsLoading } = useQuery<PromptInfo[]>({
    queryKey: ["admin", "ai", "prompts"],
    queryFn: () => api.get<PromptInfo[]>("/ai/prompts").then((r) => r.data),
  });

  return (
    <div className="space-y-8">
      <PageHeader title="AI Management" subtitle="Usage stats, cost tracking, and prompt versioning" />

      {/* Usage stats */}
      <section>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-text-muted">
          Usage (current session)
        </h2>
        {usageLoading ? (
          <Spinner size="sm" />
        ) : usage ? (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <StatCard label="Total Requests" value={usage.total_requests} />
              <StatCard label="Prompt Tokens" value={usage.total_prompt_tokens.toLocaleString()} />
              <StatCard label="Completion Tokens" value={usage.total_completion_tokens.toLocaleString()} />
              <StatCard label="Est. Cost (USD)" value={`$${usage.total_cost_usd.toFixed(4)}`} highlight />
            </div>

            {Object.keys(usage.by_endpoint).length > 0 && (
              <div className="rounded-xl bg-surface ring-1 ring-border overflow-hidden">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-rule text-left text-xs font-semibold uppercase tracking-wide text-text-muted">
                      <th className="px-4 py-2">Endpoint</th>
                      <th className="px-4 py-2 text-right">Requests</th>
                      <th className="px-4 py-2 text-right">Est. Cost</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-rule-faint">
                    {Object.entries(usage.by_endpoint).map(([ep, stats]) => (
                      <tr key={ep}>
                        <td className="px-4 py-2 font-mono text-xs text-text-secondary">{ep}</td>
                        <td className="px-4 py-2 text-right text-text-muted">{stats.requests}</td>
                        <td className="px-4 py-2 text-right text-text-muted">${stats.cost_usd.toFixed(4)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            <p className="text-xs text-text-muted">{usage.note}</p>
          </div>
        ) : null}
      </section>

      {/* Prompt versioning */}
      <SuggestionsSection />
      <AskQuestionsSection />

      <section>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-text-muted">
          Prompt Templates
        </h2>
        {promptsLoading ? (
          <Spinner size="sm" />
        ) : (
          <div className="space-y-3">
            {prompts?.map((prompt) => (
              <PromptRow
                key={prompt.key}
                prompt={prompt}
                onSave={async (content) => {
                  await api.put(`/ai/prompts/${prompt.key}`, { content });
                  qc.invalidateQueries({ queryKey: ["admin", "ai", "prompts"] });
                }}
                onReset={async () => {
                  await api.delete(`/ai/prompts/${prompt.key}`);
                  qc.invalidateQueries({ queryKey: ["admin", "ai", "prompts"] });
                }}
              />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function StatCard({
  label,
  value,
  highlight = false,
}: {
  label: string;
  value: string | number;
  highlight?: boolean;
}) {
  return (
    <div className="rounded-xl bg-surface px-4 py-3 ring-1 ring-border">
      <p className="text-xs text-text-muted">{label}</p>
      <p className={`mt-1 text-xl font-bold ${highlight ? "text-role-agent-text" : "text-text"}`}>
        {value}
      </p>
    </div>
  );
}

function PromptRow({
  prompt,
  onSave,
  onReset,
}: {
  prompt: PromptInfo;
  onSave: (content: string) => Promise<void>;
  onReset: () => Promise<void>;
}) {
  const [expanded, setExpanded] = useState(false);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(prompt.content);
  const [saving, setSaving] = useState(false);

  async function handleSave() {
    setSaving(true);
    try {
      await onSave(draft);
      setEditing(false);
    } finally {
      setSaving(false);
    }
  }

  async function handleReset() {
    setSaving(true);
    try {
      await onReset();
      setEditing(false);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="rounded-xl bg-surface ring-1 ring-border overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="font-mono text-sm text-text">{prompt.key}</span>
          {prompt.is_overridden && <Badge variant="warning">overridden</Badge>}
        </div>
        <div className="flex items-center gap-2">
          {prompt.is_overridden && (
            <button
              onClick={handleReset}
              disabled={saving}
              className="text-xs text-text-muted hover:text-danger-text transition-colors"
            >
              Reset
            </button>
          )}
          <button
            onClick={() => {
              setExpanded((v) => !v);
              setDraft(prompt.content);
              setEditing(false);
            }}
            className="text-xs text-text-muted hover:text-text-secondary transition-colors"
          >
            {expanded ? "Hide" : "Edit"}
          </button>
        </div>
      </div>

      {expanded && (
        <div className="border-t border-rule px-4 py-3 space-y-3">
          <textarea
            value={editing ? draft : prompt.content}
            onChange={(e) => { setDraft(e.target.value); setEditing(true); }}
            rows={8}
            className="w-full rounded-lg bg-surface-inset px-3 py-2 font-mono text-xs text-text-secondary ring-1 ring-input-border focus:outline-none focus:ring-role-agent-text/50 resize-y"
          />
          {editing && (
            <div className="flex gap-2">
              <button
                onClick={handleSave}
                disabled={saving}
                className="rounded-lg bg-role-agent-text/15 px-3 py-1.5 text-xs font-semibold text-role-agent-text ring-1 ring-role-agent-text/30 hover:bg-role-agent-text/25 disabled:opacity-50 transition-colors"
              >
                {saving ? "Saving…" : "Save Override"}
              </button>
              <button
                onClick={() => { setDraft(prompt.content); setEditing(false); }}
                className="text-xs text-text-muted hover:text-text-secondary transition-colors"
              >
                Cancel
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}


// ── Suggestions: used or ignored (ai/tracking.py) ────────────────────────────

function SuggestionsSection() {
  const [days, setDays] = useState(30);
  const { data, isLoading } = useSuggestionStats(days);
  return (
    <section>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-text-muted">Suggestions: used or ignored</h2>
        <select
          value={days}
          onChange={(e) => setDays(Number(e.target.value))}
          aria-label="Period"
          className="rounded-lg bg-surface px-2 py-1 text-sm text-text ring-1 ring-input-border"
        >
          <option value={7}>Last 7 days</option>
          <option value={30}>Last 30 days</option>
          <option value={90}>Last 90 days</option>
        </select>
      </div>
      {isLoading ? (
        <Spinner size="sm" />
      ) : (
        <div className="overflow-x-auto rounded-xl bg-surface ring-1 ring-border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-rule text-left text-xs uppercase tracking-wide text-text-muted">
                <th className="px-4 py-2 font-semibold">Feature</th>
                <th className="px-4 py-2 text-right font-semibold">Shown</th>
                <th className="px-4 py-2 text-right font-semibold">Used</th>
                <th className="px-4 py-2 text-right font-semibold">Used %</th>
              </tr>
            </thead>
            <tbody>
              {data?.features.map((f) => (
                <tr key={f.feature} className="border-b border-rule-faint last:border-b-0">
                  <td className="px-4 py-2 text-text">{f.label}</td>
                  <td className="px-4 py-2 text-right tabular-nums text-text">{f.shown}</td>
                  <td className="px-4 py-2 text-right tabular-nums text-text">{f.used}</td>
                  <td className="px-4 py-2 text-right tabular-nums font-semibold text-text">
                    {f.used_pct == null ? "—" : `${f.used_pct}%`}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="border-t border-rule-faint px-4 py-2 text-xs text-text-muted">
            Shown once per person, feature and subject a day. A draft counts as used when the message sent is mostly the draft.
          </p>
        </div>
      )}
    </section>
  );
}

// ── Questions Ask couldn't answer ────────────────────────────────────────────

interface AskQuestions {
  total: number;
  fallbacks: number;
  questions: { question: string; input: string; lite: boolean; created_at: string }[];
}

function AskQuestionsSection() {
  const { data, isLoading } = useQuery<AskQuestions>({
    queryKey: ["admin", "ai", "ask-questions"],
    queryFn: () => api.get<AskQuestions>("/ai/assistant/questions").then((r) => r.data),
  });
  return (
    <section>
      <h2 className="mb-1 text-sm font-semibold uppercase tracking-wide text-text-muted">Questions Ask couldn&rsquo;t answer</h2>
      {data && (
        <p className="mb-3 text-xs text-text-muted">
          {data.fallbacks} of {data.total} questions so far. They show what to build next.
        </p>
      )}
      {isLoading ? (
        <Spinner size="sm" />
      ) : !data?.questions.length ? (
        <p className="text-sm text-text-muted">None yet.</p>
      ) : (
        <ul className="divide-y divide-rule-faint rounded-xl bg-surface ring-1 ring-border">
          {data.questions.map((q, i) => (
            <li key={i} className="flex flex-wrap items-center justify-between gap-2 px-4 py-2 text-sm">
              <span className="text-text">{q.question}</span>
              <span className="text-xs text-text-muted">
                {q.lite ? "Lite" : "Full app"} · {q.input === "voice" ? "spoken" : "typed"} · {new Date(q.created_at).toLocaleDateString("en-GB")}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
