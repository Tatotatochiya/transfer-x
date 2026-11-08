import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import api from "../../lib/api";
import type { Paginated, Sale } from "../../types/api";
import SaleCard from "../../components/sales/SaleCard";
import PageHeader from "../../components/ui/PageHeader";
import Pagination from "../../components/ui/Pagination";
import EmptyState from "../../components/ui/EmptyState";
import { ListSkeleton } from "../../components/ui/Skeleton";

// Every listing is open to offers: fixed price is folded in, and auctions
// are retired (product ADR 0011), so the type is not a filter.
export default function SaleListPage() {
  // "Available for loan" is what a loan-hunting club is looking for: loan-only
  // listings and those open to either. The server does the "or either".
  const [forLoan, setForLoan] = useState(false);
  const [page, setPage] = useState(1);

  const { data, isLoading, isError } = useQuery<Paginated<Sale>>({
    queryKey: ["sales", { status: "OPEN", forLoan, page }],
    queryFn: () =>
      api
        .get<Paginated<Sale>>("/sales", {
          params: {
            status: "OPEN",
            page,
            page_size: 20,
            ...(forLoan && { available_for: "LOAN" }),
          },
        })
        .then((r) => r.data),
  });

  return (
    <div>
      <PageHeader title="Listings" subtitle="Players their clubs will sell or loan" />

      {/* Filters */}
      <div className="mb-6 flex flex-wrap gap-3">
        <button
          aria-pressed={forLoan}
          onClick={() => { setForLoan((v) => !v); setPage(1); }}
          className={`rounded-lg px-3 py-1.5 text-sm transition-colors ${
            forLoan
              ? "bg-accent-bg text-accent-active ring-1 ring-accent/40"
              : "bg-surface-inset text-text-muted hover:text-text"
          }`}
        >
          Available for loan
        </button>
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
