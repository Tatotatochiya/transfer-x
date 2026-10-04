import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useAIStatus, useLiteAsk } from "../../hooks/useAssistant";
import { useLiteAskSuggestions, useTeamContact } from "../../hooks/useLite";
import { liteMoney } from "../../lib/liteMoney";
import type { AskProposal } from "../../types/api";
import AskTeamButton from "../../components/lite/AskTeamButton";

interface Turn {
  question: string;
  input: "text" | "voice";
  done: boolean;
  answer?: string | null;
  links?: { label: string; path: string }[];
  proposal?: AskProposal | null;
  fallback?: boolean;
  error?: string;
}

// The browser's speech recognition (Chrome, Edge, Safari); absent in Firefox,
// where the Speak button is hidden. On iPad the keyboard's dictation works too.
type Recognition = {
  lang: string;
  interimResults: boolean;
  onresult: ((e: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null;
  onend: (() => void) | null;
  onerror: (() => void) | null;
  start: () => void;
  stop: () => void;
};
const SpeechRecognitionCtor: (new () => Recognition) | undefined =
  typeof window === "undefined"
    ? undefined
    : ((window as unknown as Record<string, unknown>).SpeechRecognition ??
        (window as unknown as Record<string, unknown>).webkitSpeechRecognition) as (new () => Recognition) | undefined;

const PROPOSAL_TITLE: Record<AskProposal["kind"], (p: AskProposal) => string> = {
  bid: (p) => `Bid ${liteMoney(p.amount)} for ${p.player}`,
  counter: (p) => `Counter at ${liteMoney(p.amount)} for ${p.player}`,
  accept: (p) => `Accept ${liteMoney(p.amount)} for ${p.player}`,
  reject: (p) => `Say no to the offer for ${p.player}`,
};

/**
 * Ask anything (docs/feature_spec/lite-mode README "Screen 4", L5). Questions
 * go to `/ai/ask` with `lite: true`: short answers, shortcut buttons, and a
 * `proposal` the server has already checked, which opens the action card
 * (nothing is sent until the user confirms there, ADR 0006).
 */
export default function LiteAskPage() {
  const navigate = useNavigate();
  const { data: status } = useAIStatus();
  const { data: suggestions } = useLiteAskSuggestions();
  const ask = useLiteAsk();
  const [text, setText] = useState("");
  const contactLabel = useTeamContact().data?.label ?? "your team";
  const [thread, setThread] = useState<Turn[]>([]);
  const [listening, setListening] = useState(false);
  const recognition = useRef<Recognition | null>(null);
  const autoSend = useRef<number | null>(null);

  useEffect(() => () => {
    recognition.current?.stop();
    if (autoSend.current) window.clearTimeout(autoSend.current);
  }, []);

  function send(question: string, input: "text" | "voice" = "text") {
    const q = question.trim();
    if (q.length < 3 || ask.isPending) return;
    if (autoSend.current) window.clearTimeout(autoSend.current);
    setText("");
    setThread((t) => [{ question: q, input, done: false }, ...t]);
    const settle = (patch: Partial<Turn>) =>
      setThread((t) => t.map((turn, i) => (i === 0 ? { ...turn, ...patch, done: true } : turn)));
    ask.mutate(
      { question: q, input },
      {
        onSuccess: (r) => settle({ answer: r.answer, links: r.links, proposal: r.proposal, fallback: r.fallback }),
        onError: (e) => {
          const limited = (e as { response?: { status?: number } }).response?.status === 429;
          settle(limited
            ? { error: "You've asked a lot of questions this hour. Try again in a little while." }
            : { fallback: true, links: [{ label: "Buy a player", path: "/lite/buy" }, { label: "Answer offers", path: "/lite/offers" }] });
        },
      },
    );
  }

  function toggleVoice() {
    if (!SpeechRecognitionCtor) return;
    if (listening) {
      recognition.current?.stop();
      return;
    }
    const r = new SpeechRecognitionCtor();
    r.lang = "en-GB";
    r.interimResults = false;
    r.onresult = (e) => {
      const said = e.results[0]?.[0]?.transcript ?? "";
      setText(said);
      // Sent after a second unless they start editing it.
      autoSend.current = window.setTimeout(() => send(said, "voice"), 1000);
    };
    r.onend = () => setListening(false);
    r.onerror = () => setListening(false);
    recognition.current = r;
    setListening(true);
    r.start();
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
        onSubmit={(e) => { e.preventDefault(); send(text); }}
        className="flex min-h-[4.25rem] flex-wrap items-center gap-3 rounded-[18px] bg-surface px-4 py-2 ring-2 ring-role-agent-text/30"
      >
        <span className="text-[1.5rem] text-role-agent-text" aria-hidden="true">✦</span>
        <input
          value={text}
          onChange={(e) => {
            if (autoSend.current) window.clearTimeout(autoSend.current);
            setText(e.target.value);
          }}
          placeholder={SpeechRecognitionCtor ? "Type or tap the microphone to speak" : "Ask a question in your own words"}
          aria-label="Your question"
          className="min-w-0 flex-1 bg-transparent py-3 text-[1.25rem] text-text placeholder-text-muted focus:outline-none"
        />
        {SpeechRecognitionCtor && (
          <button
            type="button"
            onClick={toggleVoice}
            aria-pressed={listening}
            className={`flex min-h-[3.25rem] items-center gap-2 rounded-xl px-4 text-[1.0625rem] font-bold ${
              listening ? "bg-role-agent-text text-white" : "bg-role-agent-text/10 text-role-agent-text"
            }`}
          >
            {listening ? (
              <><span className="h-2.5 w-2.5 animate-pulse rounded-full bg-white motion-reduce:animate-none" aria-hidden="true" /> Listening…</>
            ) : (
              <>🎙 Speak</>
            )}
          </button>
        )}
        <button
          type="submit"
          disabled={text.trim().length < 3 || ask.isPending}
          className="min-h-[3.25rem] rounded-xl bg-role-agent-text px-6 text-[1.0625rem] font-bold text-white disabled:opacity-50"
        >
          Ask
        </button>
      </form>

      {thread.length === 0 && suggestions && suggestions.suggestions.length > 0 && (
        <div>
          <p className="mb-3 text-[1.0625rem] text-text-muted">Or tap a question</p>
          <div className="grid gap-3 sm:grid-cols-2">
            {suggestions.suggestions.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => send(s)}
                className="min-h-[4.75rem] rounded-[16px] bg-surface px-5 text-left text-[1.25rem] font-semibold text-text ring-1 ring-border hover:ring-2 hover:ring-role-agent-text/40 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="flex flex-col gap-5">
        {thread.map((turn, i) => (
          <div key={thread.length - i} className="flex flex-col gap-3">
            <p className="max-w-[85%] self-end rounded-[18px] bg-ink px-5 py-3 text-[1.125rem] font-semibold text-white dark:bg-surface-inset dark:text-text">
              {turn.input === "voice" && <span className="mr-1" aria-label="Spoken">🎙</span>}
              {turn.input === "voice" ? `“${turn.question}”` : turn.question}
            </p>
            {!turn.done ? (
              <div className="animate-pulse space-y-2 rounded-[20px] bg-surface px-6 py-5 ring-1 ring-border motion-reduce:animate-none">
                <div className="h-4 w-3/4 rounded bg-surface-inset" />
                <div className="h-4 w-1/2 rounded bg-surface-inset" />
                <div className="h-4 w-2/3 rounded bg-surface-inset" />
              </div>
            ) : (
              <div className="rounded-[20px] bg-surface px-6 py-5 ring-1 ring-border">
                <p className="text-[1.3125rem] leading-normal text-text">
                  {turn.error ?? (turn.fallback || !turn.answer
                    ? `I don't have an answer for that yet. These might help, or I can pass the question to ${contactLabel}.`
                    : turn.answer)}
                </p>

                {turn.proposal && (
                  <div className="mt-4 rounded-[16px] bg-accent-bg px-5 py-4 ring-1 ring-accent/30">
                    <p className="text-[0.8125rem] font-extrabold uppercase tracking-wide text-accent">Ready to check · nothing sent yet</p>
                    <p className="mt-1 text-[1.375rem] font-extrabold text-text">{PROPOSAL_TITLE[turn.proposal.kind](turn.proposal)}</p>
                    {turn.proposal.club && <p className="text-[1.0625rem] text-text-secondary">{turn.proposal.kind === "bid" ? "To" : "With"} {turn.proposal.club}</p>}
                    <button
                      type="button"
                      onClick={() => navigate(turn.proposal!.card_path)}
                      className="mt-3 min-h-[3.25rem] rounded-[13px] bg-accent px-5 text-[1.0625rem] font-bold text-white"
                    >
                      Check and confirm →
                    </button>
                  </div>
                )}

                {turn.links && turn.links.length > 0 && (
                  <div className="mt-4 flex flex-wrap gap-3">
                    {turn.links.map((l, j) => (
                      <button
                        key={l.path}
                        type="button"
                        onClick={() => navigate(l.path)}
                        className={`min-h-[3.25rem] rounded-[13px] px-5 text-[1.0625rem] font-bold ${
                          j === 0 && !turn.proposal ? "bg-accent text-white" : "bg-surface text-text ring-1 ring-border hover:ring-accent"
                        }`}
                      >
                        {l.label} →
                      </button>
                    ))}
                  </div>
                )}
                {!turn.error && (turn.fallback || !turn.answer) && (
                  <AskTeamButton
                    subject={{ type: "general" }}
                    verb="Send to"
                    sendNow
                    draft={turn.question}
                    className="mt-3 min-h-[3.25rem] rounded-[13px] bg-accent px-5 text-[1.0625rem] font-bold text-white"
                  />
                )}
                {!turn.error && !turn.fallback && turn.answer && (
                  <p className="mt-4 flex flex-wrap items-center gap-x-3 text-[0.9375rem] text-text-muted">
                    <span>✓ Based on your club&rsquo;s own data on TransferX, as of now.</span>
                    <AskTeamButton
                      subject={{ type: "general" }}
                      suffix=" to check first →"
                      draft={`Can you check this? I asked: "${turn.question}" and was told: "${turn.answer}"`}
                      className="text-[1rem] font-bold text-accent"
                    />
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
