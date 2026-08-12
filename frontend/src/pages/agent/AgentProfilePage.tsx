import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import type { AgentProfileResponse } from "../../types/api";
import Card from "../../components/ui/Card";
import PageHeader from "../../components/ui/PageHeader";
import Spinner from "../../components/ui/Spinner";
import Button from "../../components/ui/Button";
import Badge from "../../components/ui/Badge";
import RequestVerificationPanel from "../../components/verification/RequestVerificationPanel";

const INPUT_CLS =
  "w-full rounded-lg bg-surface px-3 py-2.5 text-sm text-text placeholder-text-muted ring-1 ring-input-border focus:outline-none focus:ring-accent transition-colors disabled:opacity-50";

const LABEL_CLS = "mb-1.5 block text-sm font-semibold text-text-secondary";

export default function AgentProfilePage() {
  const queryClient = useQueryClient();

  const { data: profile, isLoading } = useQuery<AgentProfileResponse>({
    queryKey: ["agents", "me"],
    queryFn: () => api.get<AgentProfileResponse>("/agents/me").then((r) => r.data),
  });

  const [editing, setEditing]         = useState(false);
  const [displayName, setDisplayName] = useState("");
  const [agencyName, setAgencyName]   = useState("");
  const [country, setCountry]         = useState("");
  const [licenceNo, setLicenceNo]     = useState("");
  const [saving, setSaving]           = useState(false);
  const [saveError, setSaveError]     = useState<string | null>(null);

  useEffect(() => {
    if (profile) {
      setDisplayName(profile.display_name);
      setAgencyName(profile.agency_name);
      setCountry(profile.country);
      setLicenceNo(profile.licence_no ?? "");
    }
  }, [profile]);

  async function handleSave() {
    setSaveError(null);
    setSaving(true);
    try {
      await api.patch("/agents/me", {
        display_name: displayName || undefined,
        agency_name:  agencyName  || undefined,
        country:      country     || undefined,
        licence_no:   licenceNo.trim() || null,
      });
      await queryClient.invalidateQueries({ queryKey: ["agents", "me"] });
      setEditing(false);
    } catch {
      setSaveError("Failed to save changes. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  function handleCancel() {
    if (profile) {
      setDisplayName(profile.display_name);
      setAgencyName(profile.agency_name);
      setCountry(profile.country);
      setLicenceNo(profile.licence_no ?? "");
    }
    setSaveError(null);
    setEditing(false);
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner size="lg" />
      </div>
    );
  }

  if (!profile) return null;

  return (
    <div className="max-w-xl">
      <PageHeader title="Agent Profile" subtitle="Manage your agency details" />

      <Card>
        <div className="flex items-start justify-between mb-6">
          <div>
            <p className="text-lg font-semibold text-text">{profile.display_name}</p>
            <p className="text-sm text-text-muted">{profile.agency_name}</p>
          </div>
          <div className="flex items-center gap-2">
            {profile.verified && <Badge variant="success">Verified</Badge>}
            {!editing && (
              <Button variant="secondary" size="sm" onClick={() => setEditing(true)}>
                Edit
              </Button>
            )}
          </div>
        </div>

        {saveError && (
          <div className="mb-4 rounded-lg bg-danger-bg px-4 py-3 text-sm text-danger-text ring-1 ring-danger-border">
            {saveError}
          </div>
        )}

        <div className="space-y-4">
          <div>
            <label className={LABEL_CLS}>Display name</label>
            <input
              type="text"
              value={displayName}
              disabled={!editing}
              onChange={(e) => setDisplayName(e.target.value)}
              className={INPUT_CLS}
            />
          </div>
          <div>
            <label className={LABEL_CLS}>Agency name</label>
            <input
              type="text"
              value={agencyName}
              disabled={!editing}
              onChange={(e) => setAgencyName(e.target.value)}
              className={INPUT_CLS}
            />
          </div>
          <div>
            <label className={LABEL_CLS}>Country</label>
            <input
              type="text"
              value={country}
              disabled={!editing}
              onChange={(e) => setCountry(e.target.value)}
              className={INPUT_CLS}
            />
          </div>
          <div>
            <label className={LABEL_CLS}>
              FIFA licence no. <span className="text-text-muted font-normal">(optional)</span>
            </label>
            <input
              type="text"
              value={licenceNo}
              disabled={!editing}
              onChange={(e) => setLicenceNo(e.target.value)}
              className={INPUT_CLS}
              placeholder="—"
            />
          </div>

          <div className="pt-2 border-t border-rule text-xs text-text-muted">
            Member since {new Date(profile.created_at).toLocaleDateString()}
            {profile.verified && " · Verified agent"}
          </div>

          <RequestVerificationPanel verified={profile.verified} />
        </div>

        {editing && (
          <div className="mt-6 flex gap-3">
            <Button variant="primary" size="md" loading={saving} onClick={handleSave}>
              Save changes
            </Button>
            <Button variant="secondary" size="md" onClick={handleCancel} disabled={saving}>
              Cancel
            </Button>
          </div>
        )}
      </Card>
    </div>
  );
}
