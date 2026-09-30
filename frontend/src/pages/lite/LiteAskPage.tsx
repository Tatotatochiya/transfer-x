import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useAIStatus, useAsk } from "../../hooks/useAssistant";
import { getApiError } from "../../lib/utils";

interface Turn {
  question: string;
  answer?: string;
  links?: { label: string; path: string }[];
  error?: string;
}

/**
 * Ask anything, basic (L2). Questions go to the existing Ask TransferX
 * (`/ai/ask`), which answers from the club's own data and returns links it
 * has checked. L5 adds suggestions, voice, and proposals that open an
 * action card (docs/feature_spec/lite-mode, BACKEND.md §3).
 */
export default function LiteAskPage() {
  const navigate = useNavigate();
  const { data: status } = useAIStatus();
  const ask = useAsk();
  const [text, setText] = useState("");
  const [thread, setThread] = useState<Turn[]>([]);

  function send() {
    const q = text.trim();
    if (q.length < 3 || ask.isPending) return;
    setText("");
    setThread((t) => [{ question: q }, ...t]);
    ask.mutate(q, {
      onSuccess: (r) => setThread((t) => [{ question: q, answer: r.answer, links: r.links }, ...t.slice(1)]),
      onError: (e) =>
        setThread((t) => [{ question: q, error: getApiError(e, "I can't answer that just now.") }, ...t.slice(1)]),
    });
  }

  if (status && !status.available) {
    return (
      <div className="space-y-4">
        <h1 className="text-[2.375rem] font-extrabold text-text">Ask anything</h1>
        <p className="text-[1.375rem] text-text-secondary">The assistant isn&rsquo;t available right now.</p>
        <Link to="/lite" className="text-[1.125rem] font-bold text-accent">Back to home →</Link>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-[2rem] font-extrabold tracking-[-0.02em] text-text sm:text-[2.375rem]">Ask anything</h1>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          send();
        }}
        className="flex min-h-[4.25rem] items-center gap-3 rounded-[18px] bg-surface px-4 ring-2 ring-role-agent-text/30"
      >
        <span className="text-[1.5rem] text-role-agent-text">✦</span>
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Ask a question in your own words"
          aria-label="Your question"
          className="min-w-0 flex-1 bg-transparent py-3 text-[1.25rem] text-text placeholder-text-muted focus:outline-none"
        />
        <button
          type="submit"
          disabled={text.trim().length < 3 || ask.isPending}
          className="min-h-[3.25rem] rounded-xl bg-role-agent-text px-6 text-[1.0625rem] font-bold text-white disabled:opacity-50"
        >
          Ask
        </button>
      </form>

      {thread.length === 0 && (
        <p className="text-[1.125rem] text-text-muted">
          For example: &ldquo;How much can I still spend?&rdquo; or &ldquo;Which offers are waiting for me?&rdquo;
        </p>
      )}

      <div className="flex flex-col gap-5">
        {thread.map((turn, i) => (
          <div key={thread.length - i} className="flex flex-col gap-3">
            <p className="self-end rounded-[18px] bg-ink px-5 py-3 text-[1.125rem] font-semibold text-white dark:bg-surface-inset dark:text-text">
              {turn.question}
            </p>
            {turn.answer === undefined && !turn.error ? (
              <div className="animate-pulse space-y-2 rounded-[20px] bg-surface px-6 py-5 ring-1 ring-border motion-reduce:animate-none">
                <div className="h-4 w-3/4 rounded bg-surface-inset" />
                <div className="h-4 w-1/2 rounded bg-surface-inset" />
                <div className="h-4 w-2/3 rounded bg-surface-inset" />
              </div>
            ) : (
              <div className="rounded-[20px] bg-surface px-6 py-5 ring-1 ring-border">
                <p className="text-[1.3125rem] leading-normal text-text">{turn.error ?? turn.answer}</p>
                {turn.links && turn.links.length > 0 && (
                  <div className="mt-4 flex flex-wrap gap-3">
                    {turn.links.map((l, j) => (
                      <button
                        key={l.path}
                        type="button"
                        onClick={() => navigate(l.path)}
                        className={`min-h-[3.25rem] rounded-[13px] px-5 text-[1.0625rem] font-bold ${
                          j === 0 ? "bg-accent text-white" : "bg-surface text-text ring-1 ring-border hover:ring-accent"
                        }`}
                      >
                        {l.label} →
                      </button>
                    ))}
                  </div>
                )}
                {!turn.error && (
                  <p className="mt-4 text-[0.9375rem] text-text-muted">
                    ✓ Based on your club&rsquo;s own data, as of now.
                  </p>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
