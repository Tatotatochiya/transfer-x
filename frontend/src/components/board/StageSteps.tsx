import { stageStep } from "./boardList";

/**
 * Five short bars for where a transfer is (README_TRANSFERS §4.5). Stage is a
 * category, so neutral; only done is coloured (success). Not silent: the
 * bars are an image with the stage in words.
 */
export default function StageSteps({ column, label }: { column: string; label: string }) {
  const step = stageStep(column);
  const done = step === 6;
  return (
    <span role="img" aria-label={done ? "Completed" : `Stage ${step} of 5: ${label}`} className="inline-flex shrink-0 gap-[3px]">
      {[1, 2, 3, 4, 5].map((n) => (
        <span
          key={n}
          className={`h-1 w-[14px] rounded-sm ${done ? "bg-success" : n < step ? "bg-text-muted" : n === step ? "bg-text" : "bg-border"}`}
        />
      ))}
    </span>
  );
}
