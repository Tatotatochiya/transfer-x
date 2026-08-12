import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import api from "../../lib/api";
import type { Paginated, Sale } from "../../types/api";
import type { SaleType } from "../../types/enums";
import SaleCard from "../../components/sales/SaleCard";
import PageHeader from "../../components/ui/PageHeader";
import Pagination from "../../components/ui/Pagination";
import EmptyState from "../../components/ui/EmptyState";
import { ListSkeleton } from "../../components/ui/Skeleton";

const SALE_TYPES: { value: SaleType | ""; label: string }[] = [
  { value: "",               label: "All types" },
  { value: "AUCTION",        label: "Auctions" },
  { value: "OPEN_TO_OFFERS", label: "Open to Offers" },
  { value: "FIXED_PRICE",    label: "Fixed Price" },
];

export default function SaleListPage() {
  const [saleType, setSaleType] = useState<SaleType | "">("");
  const [page, setPage] = useState(1);

  const { data, isLoading, isError } = useQuery<Paginated<Sale>>({
    queryKey: ["sales", { status: "OPEN", saleType, page }],
    queryFn: () =>
      api
        .get<Paginated<Sale>>("/sales", {
          params: {
            status: "OPEN",
            page,
            page_size: 20,
            ...(saleType && { sale_type: saleType }),
          },
        })
        .then((r) => r.data),
  });

  function handleTypeChange(next: SaleType | "") {
    setSaleType(next);
    setPage(1);
  }

  return (
    <div>
      <PageHeader title="Listings" subtitle="Browse open sales and auctions" />

      {/* Filters */}
      <div className="mb-6 flex flex-wrap gap-3">
        {SALE_TYPES.map((t) => (
          <button
            key={t.value}
            onClick={() => handleTypeChange(t.value)}
            className={`rounded-lg px-3 py-1.5 text-sm transition-colors ${
              saleType === t.value
                ? "bg-success/15 text-success-text ring-1 ring-success/30"
                : "bg-surface-inset text-text-muted hover:text-text"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {isLoading && <ListSkeleton count={8} />}

      {isError && (
        <div className="rounded-xl bg-danger-bg px-5 py-4 text-sm text-danger-text ring-1 ring-danger-border">
          Failed to load listings. Please try again.
        </div>
      )}

      {data && data.items.length === 0 && (
        <EmptyState title="No listings found" body="There are no open listings matching your filter." />
      )}

      {data && data.items.length > 0 && (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {data.items.map((sale) => (
              <SaleCard key={sale.id} sale={sale} />
            ))}
          </div>
          <Pagination
            page={data.page}
            total={data.total}
            pageSize={data.page_size}
            onChange={setPage}
          />
        </>
      )}
    </div>
  );
}
