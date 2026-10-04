import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import api from "../../lib/api";
import { formatDateTime, getApiError } from "../../lib/utils";
import { useConfirm } from "../../context/ConfirmContext";
import { useToast } from "../../context/ToastContext";
import Badge from "../ui/Badge";
import Button from "../ui/Button";
import Card from "../ui/Card";
import Spinner from "../ui/Spinner";

interface Session {
  id: string;
  device: string;
  signed_in_at: string;
  last_used_at: string;
  current: boolean;
}

/** Where you're signed in (backend: /auth/sessions). Signing a device out
 *  takes effect at its next request. */
export default function SessionsCard() {
  const qc = useQueryClient();
  const confirm = useConfirm();
  const { addToast } = useToast();
  const { data: sessions, isLoading } = useQuery<Session[]>({
    queryKey: ["auth", "sessions"],
    queryFn: () => api.get<Session[]>("/auth/sessions").then((r) => r.data),
  });
  const refresh = () => qc.invalidateQueries({ queryKey: ["auth", "sessions"] });
  const signOut = useMutation({
    mutationFn: (id: string) => api.delete(`/auth/sessions/${id}`),
    onSuccess: () => { addToast("Signed out that device", "success"); void refresh(); },
    onError: (e) => addToast(getApiError(e), "error"),
  });
  const signOutOthers = useMutation({
    mutationFn: () => api.post<{ signed_out: number }>("/auth/sessions/sign-out-others").then((r) => r.data),
    onSuccess: () => { addToast("Signed out everywhere else", "success"); void refresh(); },
    onError: (e) => addToast(getApiError(e), "error"),
  });
  const others = (sessions ?? []).filter((s) => !s.current);

  return (
    <Card noPadding className="divide-y divide-rule-faint">
      {isLoading ? (
        <div className="flex justify-center py-6"><Spinner /></div>
      ) : (
        (sessions ?? []).map((s) => (
          <div key={s.id} className="flex flex-wrap items-center gap-3 px-5 py-3.5">
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-text">
                {s.device}
                {s.current && <Badge variant="success" className="ml-2">This device</Badge>}
              </p>
              <p className="mt-0.5 text-xs text-text-muted">
                Signed in {formatDateTime(s.signed_in_at)} · last used {formatDateTime(s.last_used_at)}
              </p>
            </div>
            {!s.current && (
              <Button size="sm" variant="ghost" disabled={signOut.isPending} onClick={() => signOut.mutate(s.id)}>
                Sign out
              </Button>
            )}
          </div>
        ))
      )}
      {others.length > 0 && (
        <div className="px-5 py-3.5">
          <Button
            variant="secondary"
            disabled={signOutOthers.isPending}
            onClick={async () => {
              const ok = await confirm({
                title: "Sign out everywhere else?",
                message: `This signs you out on ${others.length} other device${others.length === 1 ? "" : "s"}. You stay signed in here.`,
                confirmLabel: "Sign out everywhere else",
              });
              if (ok) signOutOthers.mutate();
            }}
          >
            Sign out everywhere else
          </Button>
        </div>
      )}
    </Card>
  );
}
