import { useAuth } from "../../hooks/useAuth";
import { useIdentity } from "../../hooks/useIdentity";

/**
 * Across the top of a read-only "view as this club" tab: whose view this is,
 * who is looking, and a way out. Nothing in this tab can change anything;
 * the server refuses every write.
 */
export default function ViewAsBanner() {
  const { viewedBy } = useAuth();
  const identity = useIdentity();

  function exit() {
    window.close();
    // Opened some other way, so the browser won't close it.
    window.location.replace("/login");
  }

  return (
    <div
      role="status"
      // Bottom-right, so it covers neither the sidebar nor the page header.
      className="fixed bottom-4 right-4 z-[70] flex max-w-[calc(100vw-2rem)] flex-wrap items-center gap-x-3 gap-y-1 rounded-2xl bg-ink px-4 py-2.5 text-sm text-white shadow-xl"
    >
      <span>
        <span className="font-semibold">Viewing as {identity.name ?? "this club"}</span>
        {" · read-only"}
        {viewedBy && <span className="opacity-75"> · you are {viewedBy}</span>}
      </span>
      <button type="button" onClick={exit} className="rounded-md bg-white/15 px-2.5 py-0.5 font-semibold hover:bg-white/25">
        Exit
      </button>
    </div>
  );
}
