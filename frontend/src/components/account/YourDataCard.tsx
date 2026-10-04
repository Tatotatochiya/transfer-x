import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import api from "../../lib/api";
import { getApiError } from "../../lib/utils";
import { useAuthStore } from "../../store/auth";
import { useToast } from "../../context/ToastContext";
import Button from "../ui/Button";
import Card from "../ui/Card";

/** GDPR (backend: auth/privacy.py): download your data, or close your account. */
export default function YourDataCard() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { addToast } = useToast();
  const [closing, setClosing] = useState(false);
  const [password, setPassword] = useState("");
  const [confirmText, setConfirmText] = useState("");

  const download = useMutation({
    mutationFn: async () => {
      const resp = await api.get<Blob>("/auth/me/export", { responseType: "blob" });
      const url = URL.createObjectURL(resp.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = `transferx-my-data-${new Date().toISOString().slice(0, 10)}.json`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    },
    onError: (e) => addToast(getApiError(e), "error"),
  });

  const { data: closeCheck } = useQuery<{ can_close: boolean; reason: string | null }>({
    queryKey: ["auth", "close-check"],
    queryFn: () => api.get("/auth/me/close-check").then((r) => r.data),
    enabled: closing,
  });

  const close = useMutation({
    mutationFn: () => api.post("/auth/me/close", { password, confirm: confirmText }),
    onSuccess: () => {
      useAuthStore.getState().logout();
      qc.clear();
      navigate("/login", { replace: true });
    },
  });
  const input = "w-full rounded-lg bg-surface px-3 py-2 text-sm text-text ring-1 ring-input-border focus:outline-none focus:ring-accent";

  return (
    <Card className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-text">Download your data</p>
          <p className="mt-0.5 text-xs text-text-muted">
            Your account, preferences, devices, notifications, activity and messages, as a JSON file.
          </p>
        </div>
        <Button variant="secondary" disabled={download.isPending} onClick={() => download.mutate()}>
          {download.isPending ? "Preparing…" : "Download"}
        </Button>
      </div>

      <div className="border-t border-rule-faint pt-5">
        <p className="text-sm font-medium text-text">Close your account</p>
        <p className="mt-0.5 text-xs text-text-muted">
          Your name, email and settings are erased and you're signed out everywhere. The audit trail, deal
          comments and messages stay, so the records others rely on still make sense, but without your name.
        </p>
        {!closing ? (
          <Button variant="danger" className="mt-3" onClick={() => setClosing(true)}>Close my account…</Button>
        ) : closeCheck && !closeCheck.can_close ? (
          <p className="mt-3 rounded-lg bg-surface-inset px-3 py-2 text-sm text-text-secondary">{closeCheck.reason}</p>
        ) : (
          <form
            className="mt-3 grid gap-3 sm:grid-cols-2"
            onSubmit={(e) => { e.preventDefault(); close.mutate(); }}
          >
            <label className="text-xs text-text-secondary">
              Your password
              <input type="password" autoComplete="current-password" required value={password}
                onChange={(e) => setPassword(e.target.value)} className={`${input} mt-1`} />
            </label>
            <label className="text-xs text-text-secondary">
              Type DELETE to confirm
              <input required value={confirmText} onChange={(e) => setConfirmText(e.target.value)} className={`${input} mt-1`} />
            </label>
            {close.isError && <p className="text-sm text-danger-text sm:col-span-2">{getApiError(close.error)}</p>}
            <div className="flex gap-2 sm:col-span-2">
              <Button type="submit" variant="danger"
                disabled={!password || confirmText.trim().toUpperCase() !== "DELETE" || close.isPending}>
                {close.isPending ? "Closing…" : "Close my account"}
              </Button>
              <Button type="button" variant="ghost" onClick={() => setClosing(false)}>Cancel</Button>
            </div>
          </form>
        )}
      </div>
    </Card>
  );
}
