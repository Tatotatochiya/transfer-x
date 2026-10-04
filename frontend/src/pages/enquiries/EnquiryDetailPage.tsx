import { useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import type { Enquiry } from "../../types/api";
import Button from "../../components/ui/Button";
import Spinner from "../../components/ui/Spinner";
import { useConfirm } from "../../context/ConfirmContext";
import { useToast } from "../../context/ToastContext";
import { useClubCapabilities } from "../../hooks/useClubCapabilities";
import { getApiError } from "../../lib/utils";
import ConversationPanel from "../../components/conversation/ConversationPanel";
import ClubLink from "../../components/ui/ClubLink";
import PlayerLink from "../../components/ui/PlayerLink";

/**
 * One enquiry's thread. The asking club can move to a formal offer from here
 * when it is ready — the enquiry itself reserves and commits nothing.
 */
export default function EnquiryDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const confirm = useConfirm();
  const { addToast } = useToast();
  const { can } = useClubCapabilities();

  const { data: e, isLoading, isError } = useQuery<Enquiry>({
    queryKey: ["enquiries", id],
    queryFn: () => api.get<Enquiry>(`/enquiries/${id}`).then((r) => r.data),
    enabled: !!id,
  });

  const refresh = (updated: Enquiry) => {
    queryClient.setQueryData(["enquiries", id], updated);
    queryClient.invalidateQueries({ queryKey: ["enquiries"] });
    queryClient.invalidateQueries({ queryKey: ["dashboard"] });
  };
  const close = useMutation({
    mutationFn: () => api.post<Enquiry>(`/enquiries/${id}/close`).then((r) => r.data),
    onSuccess: refresh,
    onError: (err: unknown) => addToast(getApiError(err, "Could not close."), "error"),
  });

  if (isLoading) return <div className="flex justify-center py-20"><Spinner size="lg" /></div>;
  if (isError || !e) return <p className="text-sm text-danger-text">Enquiry not found.</p>;

  const other = e.role === "owning" ? e.asking_club : e.owning_club;
  const open = e.status === "OPEN";
  const canWrite = can("MARKET_WRITE");

  return (
    <div className="max-w-2xl">
      <button onClick={() => navigate("/board")} className="mb-6 text-sm text-text-muted hover:text-text">
        ← Transfers
      </button>
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-text"><PlayerLink id={e.player_id} name={e.player_name ?? "Player"} /></h1>
          <p className="mt-1 flex flex-wrap items-center gap-1.5 text-sm text-text-muted">
            {e.role === "owning" ? (
              <><ClubLink id={other.id} name={other.name} crestUrl={other.id ? other.crest_url ?? null : undefined} /> is asking about your player</>
            ) : (
              <>You asked <ClubLink id={other.id} name={other.name} crestUrl={other.id ? other.crest_url ?? null : undefined} /></>
            )}
            {e.is_anonymous && (e.role === "owning" ? " — anonymously" : " — anonymously; they see only your league")}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {e.role === "asking" && open && canWrite && (
            <Button variant="primary" size="sm" onClick={() => navigate(`/offers/new?player_id=${e.player_id}`)}>
              Make an offer
            </Button>
          )}
          {open && canWrite && (
            <Button
              variant="ghost"
              size="sm"
              loading={close.isPending}
              onClick={async () => {
                if (await confirm({ title: "Close this enquiry", message: "Neither club can write in it afterwards.", confirmLabel: "Close" })) {
                  close.mutate();
                }
              }}
            >
              Close
            </Button>
          )}
        </div>
      </div>

      {/* The whole transfer's conversation (product ADR 0008): this enquiry,
          then any offer and deal that follow it. */}
      <div className="rounded-xl bg-surface p-5 ring-1 ring-border">
        <ConversationPanel context={{ enquiryId: e.id }} placeholder="Write a reply…" />
        {!open && <p className="mt-3 border-t border-rule-faint pt-3 text-[13px] text-text-muted">This enquiry is closed.</p>}
      </div>
    </div>
  );
}
