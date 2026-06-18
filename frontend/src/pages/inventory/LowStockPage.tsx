// src/pages/inventory/LowStockPage.tsx
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Package } from "lucide-react";
import { inventoryApi } from "@/api/index";
import { Card, CardHeader, EmptyState, TableSkeleton } from "@/components/ui";

export default function LowStockPage() {
  const { data: alerts, isLoading } = useQuery({
    queryKey: ["low-stock"],
    queryFn: inventoryApi.lowStockAlerts,
    refetchInterval: 300_000, // every 5 min
  });

  return (
    <div className="max-w-5xl space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-ink">Low Stock Alerts</h1>
        <p className="text-sm text-ink-muted mt-0.5">
          Materials below their reorder point
        </p>
      </div>

      <Card>
        <CardHeader
          title="Below Reorder Point"
          subtitle={alerts ? `${alerts.length} alert${alerts.length !== 1 ? "s" : ""}` : "—"}
        />
        {isLoading ? (
          <TableSkeleton rows={6} cols={5} />
        ) : !alerts || alerts.length === 0 ? (
          <EmptyState
            icon={<Package className="h-10 w-10" />}
            title="Stock levels are healthy"
            description="No materials are currently below their reorder point."
          />
        ) : (
          <table className="w-full">
            <thead>
              <tr className="border-b border-surface-border">
                <th className="th text-left">Material Number</th>
                <th className="th text-left">Warehouse</th>
                <th className="th text-right">Current Qty</th>
                <th className="th text-right">Reorder Point</th>
                <th className="th text-right">Deficit</th>
              </tr>
            </thead>
            <tbody>
              {alerts.map((alert, i) => (
                <tr
                  key={i}
                  className="border-b border-surface-border last:border-0"
                >
                  <td className="td font-mono text-xs text-brand-500">
                    {alert.material_number ?? alert.material_id.slice(0, 8)}
                  </td>
                  <td className="td text-ink-muted text-xs">
                    {alert.warehouse_code ?? alert.warehouse_id.slice(0, 8)}
                  </td>
                  <td className="td text-right tabular text-ink">
                    {alert.current_qty.toFixed(3)}
                  </td>
                  <td className="td text-right tabular text-ink-muted">
                    {alert.reorder_point.toFixed(3)}
                  </td>
                  <td className="td text-right tabular">
                    <span className="inline-flex items-center gap-1 text-red-500 font-semibold">
                      <AlertTriangle className="h-3 w-3" />
                      {alert.deficit.toFixed(3)}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}
