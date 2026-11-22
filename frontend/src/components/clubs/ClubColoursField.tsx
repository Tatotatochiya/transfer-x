import { useEffect, useState } from "react";

import ClubBand, { type BandClub } from "../dashboard/ClubBand";
import { WHITE, bandColours, contrast } from "../../lib/brandColour";
import { crestPalette, type ColourPair } from "../../lib/crestPalette";

export const HEX = /^#[0-9A-Fa-f]{6}$/;

/** "" or a #RRGGBB: what the form may send. */
export function colourError(value: string): string | null {
  return value === "" || HEX.test(value) ? null : "Use a colour like #DB0007";
}

const INPUT = "w-full rounded-lg bg-surface px-3 py-2 text-input lg:text-body text-text placeholder-text-muted ring-1 ring-input-border focus:outline-none focus:ring-accent";

function ColourInput({ id, label, value, onChange }: {
  id: string; label: string; value: string; onChange: (v: string) => void;
}) {
  const error = colourError(value);
  return (
    <div>
      <label htmlFor={id} className="mb-1.5 block text-caption font-medium text-text-muted">{label}</label>
      <div className="flex items-center gap-2">
        {/* The swatch is the native picker. */}
        <label className="relative h-10 w-10 shrink-0 cursor-pointer overflow-hidden rounded-lg ring-1 ring-border"
          style={{ backgroundColor: HEX.test(value) ? value : undefined }}>
          <span className="sr-only">Pick the {label.toLowerCase()} colour</span>
          <input type="color" value={HEX.test(value) ? value.toLowerCase() : "#ffffff"}
            onChange={(e) => onChange(e.target.value.toUpperCase())}
            className="absolute inset-0 h-full w-full cursor-pointer opacity-0" />
        </label>
        <input id={id} type="text" value={value} maxLength={7} placeholder="#DB0007"
          onChange={(e) => onChange(e.target.value.trim())}
          aria-invalid={!!error} aria-describedby={error ? `${id}-error` : undefined} className={INPUT} />
      </div>
      {error && <p id={`${id}-error`} className="mt-1 text-small text-danger-text">{error}</p>}
    </div>
  );
}

/**
 * Club colours in My Club's details form (feature_spec/club-dashboard §3.2):
 * suggestions from the crest, two colours, a live preview of the band and how
 * its text reads. "" for both removes them.
 */
export default function ClubColoursField({ club, primary, secondary, onChange }: {
  club: BandClub;
  primary: string;
  secondary: string;
  onChange: (primary: string, secondary: string) => void;
}) {
  const [suggestions, setSuggestions] = useState<ColourPair[]>([]);
  useEffect(() => {
    let live = true;
    crestPalette(club.crest_url).then((pairs) => { if (live) setSuggestions(pairs); });
    return () => { live = false; };
  }, [club.crest_url]);

  const valid = HEX.test(primary);
  const band = valid ? bandColours(primary.toUpperCase(), "light") : null;
  const ratio = band ? contrast(band.bg, band.text) : 0;

  return (
    <fieldset id="club-colours" className="scroll-mt-24 sm:col-span-2 lg:col-span-3">
      <legend className="mb-1.5 text-body font-semibold text-text">Club colours</legend>
      <p className="mb-3 text-small text-text-muted">
        Your colours appear on your Dashboard and next to your crest in the sidebar. Buttons, links and statuses keep
        TransferX&rsquo;s colours, so they mean the same thing everywhere.
      </p>

      {suggestions.length > 0 && (
        <div className="mb-3">
          <p className="mb-1.5 text-caption font-medium text-text-muted">Suggested from your crest</p>
          <div className="flex flex-wrap gap-2">
            {suggestions.map((s) => (
              <button key={s.primary + s.secondary} type="button" onClick={() => onChange(s.primary, s.secondary)}
                className="inline-flex h-10 items-center gap-2 rounded-lg bg-surface px-3 text-small font-semibold text-text ring-1 ring-border hover:ring-accent">
                <span aria-hidden="true" className="flex">
                  <span className="h-5 w-5 rounded-l ring-1 ring-border" style={{ backgroundColor: s.primary }} />
                  <span className="h-5 w-5 rounded-r ring-1 ring-border" style={{ backgroundColor: s.secondary }} />
                </span>
                {s.label}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        <ColourInput id="brand-primary" label="Primary" value={primary} onChange={(v) => onChange(v, secondary)} />
        <ColourInput id="brand-secondary" label="Secondary" value={secondary} onChange={(v) => onChange(primary, v)} />
      </div>

      {valid && (
        <div className="mt-4 max-w-[390px]">
          <p className="mb-1.5 text-caption font-medium text-text-muted">Preview</p>
          <ClubBand club={{ ...club, brand_primary: primary.toUpperCase(), brand_secondary: HEX.test(secondary) ? secondary.toUpperCase() : null }} preview />
          <p className="mt-2 text-small text-success-text">
            {band!.bg !== primary.toUpperCase()
              ? `Your primary is darkened slightly on the band, so white text reads clearly (${ratio.toFixed(1)} : 1)`
              : band!.text === WHITE
              ? `✓ White text reads clearly on your primary (${ratio.toFixed(1)} : 1)`
              : `Text on your primary will be dark, so it reads clearly (${ratio.toFixed(1)} : 1)`}
          </p>
        </div>
      )}

      {(primary || secondary) && (
        <button type="button" onClick={() => onChange("", "")}
          className="mt-3 text-small font-semibold text-accent hover:underline">
          Remove colours
        </button>
      )}
    </fieldset>
  );
}
