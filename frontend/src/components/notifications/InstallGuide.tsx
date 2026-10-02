import { useEffect } from "react";
import { useFocusTrap } from "../../hooks/useFocusTrap";
import { trackClick } from "../../lib/analytics";
import { isIPad } from "../../lib/push";
import Icon from "../layout/Icon";

/**
 * "Add TransferX to your Home Screen" (mobile notifications §7.3, 5b). On
 * iPhone and iPad, only the Home Screen app can get notifications, so this
 * is the first step there. Full screen; Escape or Close dismisses it.
 */

const STEPS: { title: string; hint: string }[] = [
  { title: "Tap Share", hint: "The square with an arrow, in Safari's bar" },
  { title: "Tap Add to Home Screen", hint: "Scroll down the list if you can't see it" },
  { title: "Open TransferX from your Home Screen", hint: "Then tap Turn on notifications" },
];

export default function InstallGuide({ open, onClose }: { open: boolean; onClose: () => void }) {
  const ref = useFocusTrap(open, onClose);
  const ipad = isIPad();

  useEffect(() => {
    if (open) trackClick("push_install_guide_shown", window.location.pathname);
  }, [open]);

  if (!open) return null;
  return (
    <div
      ref={ref as React.RefObject<HTMLDivElement>}
      role="dialog"
      aria-modal="true"
      aria-labelledby="install-guide-title"
      className="fixed inset-0 z-[60] flex flex-col overflow-y-auto bg-surface px-5 pb-8 pt-6"
    >
      <div className="flex justify-end">
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          className="flex h-11 w-11 items-center justify-center rounded-lg text-text-secondary hover:bg-surface-inset"
        >
          <Icon name="x" />
        </button>
      </div>
      {ipad && <p className="text-right text-sm font-semibold text-accent">Share is at the top right ↑</p>}

      <div className="mx-auto mt-4 w-full max-w-md flex-1">
        <h2 id="install-guide-title" className="text-2xl font-bold text-text">Add TransferX to your Home Screen</h2>
        <p className="mt-2 text-[15px] leading-relaxed text-text-secondary">
          iPhone only sends notifications to web apps opened from the Home Screen. It takes three taps.
        </p>
        <ol className="mt-6 space-y-5">
          {STEPS.map((s, i) => (
            <li key={s.title} className="flex gap-3.5">
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-accent-bg text-sm font-bold text-accent">
                {i + 1}
              </span>
              <div>
                <p className="text-[15px] font-semibold text-text">{s.title}</p>
                <p className="text-sm text-text-muted">{s.hint}</p>
              </div>
            </li>
          ))}
        </ol>
      </div>

      {!ipad && <p className="mt-8 text-center text-sm font-semibold text-accent">Share is in the bar below ↓</p>}
    </div>
  );
}
