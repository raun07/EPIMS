import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Plus, ChevronRight, PackageCheck } from "lucide-react";
import { grnApi } from "@/api/procurement";
import { formatCurrency, formatDate } from "@/lib/utils";
import { Button, Card, EmptyState, TableSkeleton, StatusBadge } from "@/components/ui";

const STATUSES = [
  { value: "", label: "All" },
  { value: "DRAFT", label: "Draft" },
  { value: "POSTED", label: "Posted" },
  { value: "REVERSED", label: "Reversed" },
];

export default function GRNListPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["grns", page, statusFilter],
    queryFn: () => grnApi.list({ page, per_page: 20 }),
  });

  const grns = (data?.data ?? []).filter(
    (g: any) => !statusFilter || g.status === statusFilter
  );
  const meta = data?.meta;

  return (
    <div className="max-w-7xl space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-ink">Goods Receipts</h1>
          <p className="text-sm text-ink-muted mt-0.5">
            {meta ? `${meta.total} total` : "Loading…"}
          </p>
        </div>
        <Button onClick={() => navigate("/procurement/grn/new")}>
          <Plus className="h-4 w-4" /> New GRN
        </Button>
      </div>

      <Card className="p-3">
        <div className="flex gap-2">
          {STATUSES.map((s) => (
            <button
              key={s.value}
              onClick={() => setStatusFilter(s.value)}
              className={`px-3 py-1.5 rounded text-xs font-medium transition-colors ${
                statusFilter === s.value
                  ? "bg-brand-500 text-white"
                  : "bg-surface text-ink-muted hover:bg-surface-hover"
              }`}
            >
              {s.label}
            </button>
          ))}
        </div>
      </Card>

      {isLoading ? (
        <TableSkeleton rows={6} cols={6} />
      ) : grns.length === 0 ? (
        <EmptyState
          icon={<PackageCheck className="h-10 w-10" />}
          title="No goods receipts found"
          description="Post a GRN once a vendor delivers against a PO"
          action={
            <Button size="sm" onClick={() => navigate("/procurement/grn/new")}>
              <Plus className="h-3.5 w-3.5" /> New GRN
            </Button>
          }
        />
      ) : (
        <Card>
          <table className="w-full">
            <thead>
              <tr className="border-b border-surface-border bg-surface">
                <th className="px-4 py-2 text-left text-2xs font-semibold text-ink-muted uppercase">GRN Number</th>
                <th className="px-4 py-2 text-left text-2xs font-semibold text-ink-muted uppercase">PO Reference</th>
                <th className="px-4 py-2 text-left text-2xs font-semibold text-ink-muted uppercase">Receipt Date</th>
                <th className="px-4 py-2 text-right text-2xs font-semibold text-ink-muted uppercase">Value</th>
                <th className="px-4 py-2 text-left text-2xs font-semibold text-ink-muted uppercase">Status</th>
                <th className="px-4 py-2 w-8"></th>
              </tr>
            </thead>
            <tbody>
              {grns.map((g: any) => (
                <tr
                  key={g.id}
                  onClick={() => navigate(`/procurement/grn/${g.id}`)}
                  className="border-b border-surface-border last:border-0 hover:bg-surface-hover cursor-pointer"
                >
                  <td className="px-4 py-3">
                    <span className="text-sm font-medium text-brand-500">{g.grn_number}</span>
                  </td>
                  <td className="px-4 py-3 text-sm text-ink-muted">{g.po_id?.slice(0, 8) ?? "—"}</td>
                  <td className="px-4 py-3 text-sm text-ink-muted">
                    {g.receipt_date ? formatDate(g.receipt_date) : "—"}
                  </td>
                  <td className="px-4 py-3 text-right tabular font-medium text-ink">
                    {formatCurrency(g.total_value ?? 0)}
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={g.status} />
                  </td>
                  <td className="px-4 py-3">
                    <ChevronRight className="h-4 w-4 text-ink-subtle" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
