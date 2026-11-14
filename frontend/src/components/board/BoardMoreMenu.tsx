import MoreMenu from "../transfer/MoreMenu";

/** The board's ⋯ menu below 1280px: New listing and History (README_TRANSFERS §4.1). */
export default function BoardMoreMenu() {
  return (
    <MoreMenu
      label={<span aria-hidden className="text-section leading-none">⋯</span>}
      triggerAriaLabel="More"
      menuLabel="Transfers"
      triggerClassName="inline-flex h-11 w-11 items-center justify-center rounded-lg bg-surface text-text-secondary ring-1 ring-inset ring-input-border hover:text-text"
      items={[
        { label: "+ New listing", to: "/sales/new", accent: true },
        { label: "History", to: "/board/history" },
      ]}
    />
  );
}
