import { useNavigate, useSearchParams } from "react-router-dom";
import PageHeader from "../../components/ui/PageHeader";
import Card from "../../components/ui/Card";
import TransferWindowBanner from "../../components/transfers/TransferWindowBanner";
import { ListPlayerForm } from "../../components/sales/ListPlayerModal";

// Kept for deep links (`?player_id=` preselects him). In the app, listing opens
// the same form in a modal where the player is — see ListPlayerModal.
export default function CreateSalePage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  return (
    <div className="max-w-2xl">
      <PageHeader title="New Listing" subtitle="List a player for sale or auction" />

      <TransferWindowBanner />

      <Card>
        <ListPlayerForm
          defaultPlayerId={searchParams.get("player_id") ?? undefined}
          onDone={() => navigate("/sales/mine")}
          onCancel={() => navigate("/sales/mine")}
        />
      </Card>
    </div>
  );
}
