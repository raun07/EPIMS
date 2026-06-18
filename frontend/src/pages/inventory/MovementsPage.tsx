import { useQuery } from "@tanstack/react-query";
import { ArrowRightLeft } from "lucide-react";
import api from "@/lib/api";
import { formatCurrency, formatDate } from "@/lib/utils";
import { Card, EmptyState, TableSkeleton } from "@/components/ui";

const MOVEMENT_TYPE_LABELS: Record<string, string> = {
  GOODS_RECEIPT: "Goods Receipt (101)",
  GOODS_ISSUE: "Goods Issue (201)",
  TRANSFER: "Stock Transfer (301)",
  INITIAL: "Initial Stock (561)",
  RETURN: "Return (122)",
  ADJUSTMENT: "Adjustment",
};

export default function MovementsPage() {
  const { data: movements, isLoading } = useQuery({
    queryKey: ["all-movements"],
    queryFn: () => api.get("/inventory/movements?page=1&per_page=50").then(r => r.data),
  });

  return (
    <div className="max-w-6xl space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-ink">Stock Movements</h1>
        <p className="text-sm text-ink-muted mt-0.5">
          Immutable ledger of every stock change — mirrors SAP material document (MB51)
        </p>
      </div>

      {isLoading ? (
        <TableSkeleton rows={8} cols={7} />
      ) : !movements || movements.length === 0 ? (
        <EmptyState
          icon={<ArrowRightLeft className="h-10 w-10" />}
          title="No stock movements yet"
          description="Movements are created automatically when GRNs are posted or stock is issued/transferred"
        />
      ) : (
        <Card>
          <table className="w-full">
            <thead>
              <tr className="border-b border-surface-border bg-surface">
                <th className="px-4 py-2 text-left text-2xs font-semibold text-ink-muted uppercase">Movement #</th>
                <th className="px-4 py-2 text-left text-2xs font-semibold text-ink-muted uppercase">Type</th>
                <th className="px-4 py-2 text-left text-2xs font-semibold text-ink-muted uppercase">Material</th>
                <th className="px-4 py-2 text-left text-2xs font-semibold text-ink-muted uppercase">Warehouse</th>
                <th className="px-4 py-2 text-right text-2xs font-semibold text-ink-muted uppercase">Qty</th>
                <th className="px-4 py-2 text-right text-2xs font-semibold text-ink-muted uppercase">Value</th>
                <th className="px-4 py-2 text-left text-2xs font-semibold text-ink-muted uppercase">Date</th>
              </tr>
            </thead>
            <tbody>
              {movements.map((m: any) => (
                <tr key={m.id} className="border-b border-surface-border last:border-0 hover:bg-surface-hover">
                  <td className="px-4 py-3 text-xs font-mono text-brand-500">{m.movement_number}</td>
                  <td className="px-4 py-3">
                    <span className="text-xs px-2 py-0.5 rounded bg-surface text-ink-muted">
                      {MOVEMENT_TYPE_LABELS[m.movement_type] ?? m.movement_type}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm text-ink">
                    {m.material?.description ?? m.material?.material_number ?? "—"}
                  </td>
                  <td className="px-4 py-3 text-sm text-ink-muted">
                    {m.to_warehouse?.name ?? m.from_warehouse?.name ?? "—"}
                  </td>
                  <td className="px-4 py-3 text-right tabular text-ink">
                    {parseFloat(m.quantity).toLocaleString("en-IN")}
                  </td>
                  <td className="px-4 py-3 text-right tabular font-medium text-ink">
                    {m.total_value ? formatCurrency(parseFloat(m.total_value)) : "—"}
                  </td>
                  <td className="px-4 py-3 text-xs text-ink-muted">
                    {m.movement_date ? formatDate(m.movement_date) : "—"}
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
