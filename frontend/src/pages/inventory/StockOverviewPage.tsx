import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search, Package } from "lucide-react";
import { inventoryApi } from "@/api/index";
import { formatCurrency } from "@/lib/utils";
import { Card, EmptyState, TableSkeleton } from "@/components/ui";

export default function StockOverviewPage() {
  const [materialId, setMaterialId] = useState("");
  const [search, setSearch] = useState("");

  const { data: stocks, isLoading } = useQuery({
    queryKey: ["stock", search],
    queryFn: () => inventoryApi.materialStock(search),
    enabled: !!search,
  });

  return (
    <div className="max-w-5xl space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-ink">Stock Overview</h1>
        <p className="text-sm text-ink-muted mt-0.5">Query current stock levels by material</p>
      </div>

      <Card className="p-4">
        <div className="flex gap-3">
          <input
            className="flex-1 h-9 rounded border border-surface-border px-3 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            placeholder="Enter Material UUID…"
            value={materialId}
            onChange={(e) => setMaterialId(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && setSearch(materialId)}
          />
          <button
            onClick={() => setSearch(materialId)}
            disabled={!materialId}
            className="h-9 px-4 rounded bg-brand-500 text-white text-sm hover:bg-brand-600 disabled:opacity-50"
          >
            Query Stock
          </button>
        </div>
      </Card>

      {!search ? (
        <EmptyState
          icon={<Package className="h-10 w-10" />}
          title="Enter a material ID"
          description="Stock levels for that material will appear here"
        />
      ) : isLoading ? (
        <TableSkeleton rows={5} cols={6} />
      ) : !stocks || stocks.length === 0 ? (
        <EmptyState title="No stock found" description="This material has no stock records" />
      ) : (
        <Card>
          <table className="w-full">
            <thead>
              <tr className="border-b border-surface-border">
                <th className="th text-left">Warehouse</th>
                <th className="th text-left">Location</th>
                <th className="th text-left">Stock Type</th>
                <th className="th text-left">Batch</th>
                <th className="th text-right">Quantity</th>
                <th className="th text-right">Val. Price</th>
                <th className="th text-right">Total Value</th>
              </tr>
            </thead>
            <tbody>
              {stocks.map((s) => (
                <tr key={s.id} className="border-b border-surface-border last:border-0">
                  <td className="td font-mono text-xs text-brand-500">{s.warehouse_id.slice(0, 10)}…</td>
                  <td className="td text-ink-muted text-xs font-mono">
                    {s.storage_location_id ? s.storage_location_id.slice(0, 10) + "…" : "—"}
                  </td>
                  <td className="td">
                    <span className="badge badge-released text-2xs">{s.stock_type}</span>
                  </td>
                  <td className="td text-ink-muted text-xs font-mono">{s.batch_number ?? "—"}</td>
                  <td className="td text-right tabular font-semibold text-ink">{parseFloat(s.quantity).toFixed(3)}</td>
                  <td className="td text-right tabular text-ink-muted">
                    {s.valuation_price ? formatCurrency(parseFloat(s.valuation_price), s.currency) : "—"}
                  </td>
                  <td className="td text-right tabular font-medium text-ink">
                    {formatCurrency(parseFloat(s.total_value), s.currency)}
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="border-t-2 border-surface-border bg-surface">
                <td colSpan={4} className="td text-right font-semibold text-ink">Total</td>
                <td className="td text-right tabular font-bold">
                  {stocks.reduce((s, i) => s + parseFloat(i.quantity), 0).toFixed(3)}
                </td>
                <td />
                <td className="td text-right tabular font-bold text-ink">
                  {formatCurrency(stocks.reduce((s, i) => s + parseFloat(i.total_value), 0), stocks[0]?.currency ?? "INR")}
                </td>
              </tr>
            </tfoot>
          </table>
        </Card>
      )}
    </div>
  );
}
