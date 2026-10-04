import { useState } from "react";
import { useMutation } from "@tanstack/react-query";

import api from "../../lib/api";
import { getApiError } from "../../lib/utils";
import { useAuthStore } from "../../store/auth";
import type { User } from "../../types/api";
import Button from "../ui/Button";
import Card from "../ui/Card";
import NameFields from "../auth/NameFields";

/** Your first and last name: your team, approvals and the audit trail use it.
 *  Other clubs still see only your club's name. */
export default function YourNameCard() {
  const { user, setUser } = useAuthStore();
  const [first, setFirst] = useState(user?.first_name ?? "");
  const [last, setLast] = useState(user?.last_name ?? "");
  const [saved, setSaved] = useState(false);

  const save = useMutation({
    mutationFn: () => api.patch<User>("/auth/me", { first_name: first.trim(), last_name: last.trim() }).then((r) => r.data),
    onSuccess: (me) => { setUser(me); setSaved(true); },
  });
  const unchanged = first.trim() === (user?.first_name ?? "") && last.trim() === (user?.last_name ?? "");

  return (
    <Card>
      <form
        onSubmit={(e) => { e.preventDefault(); setSaved(false); save.mutate(); }}
        className="space-y-3"
      >
        <NameFields first={first} last={last} onFirst={setFirst} onLast={setLast} />
        <p className="text-xs text-text-muted">
          Your team, approvals and the audit trail show your name. Other clubs see only your club.
        </p>
        {save.isError && <p className="text-sm text-danger-text">{getApiError(save.error)}</p>}
        <div className="flex items-center gap-3">
          <Button type="submit" disabled={unchanged || !first.trim() || !last.trim() || save.isPending}>
            {save.isPending ? "Saving…" : "Save name"}
          </Button>
          {saved && unchanged && <span className="text-sm text-success-text">Saved</span>}
        </div>
      </form>
    </Card>
  );
}
