import { useQuery } from "@tanstack/react-query";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend
} from "recharts";
import { reportsApi } from "@/api/index";
import { formatCurrency } from "@/lib/utils";
import { Card, CardHeader, Skeleton } from "@/components/ui";

const STATUS_COLORS: Record<string, string> = {
  DRAFT: "#94a3b8",
  SUBMITTED: "#f59e0b",
  PENDING_APPROVAL: "#fbbf24",
  APPROVED: "#10b981",
  REJECTED: "#ef4444",
  RELEASED: "#6366f1",
  RECEIVED: "#0ea5e9",
  CLOSED: "#059669",
  CANCELLED: "#cbd5e1",
};

export default function ReportsDashboardPage() {
  const { data: prSummary, isLoading: prLoading } = useQuery({
    queryKey: ["pr-summary"],
    queryFn: () => reportsApi.prSummary(),
  });

  const { data: poSummary, isLoading: poLoading } = useQuery({
    queryKey: ["po-summary"],
    queryFn: () => reportsApi.poSummary(),
  });

  const { data: vendors, isLoading: vendorsLoading } = useQuery({
    queryKey: ["vendor-perf"],
    queryFn: () => reportsApi.vendorPerformance(10),
  });

  const { data: inventory } = useQuery({
    queryKey: ["inventory-valuation"],
    queryFn: reportsApi.inventoryValuation,
  });

  const prChartData = prSummary?.by_status.map((s) => ({
    status: s.status.replace(/_/g, " "),
    count: s.count,
    value: s.total_value,
  })) ?? [];

  const poChartData = poSummary?.by_status.map((s) => ({
    status: s.status.replace(/_/g, " "),
    value: s.total_value,
    count: s.count,
  })) ?? [];

  const COLORS = ["#6366f1", "#f59e0b", "#10b981", "#0ea5e9", "#ef4444", "#8b5cf6"];

  return (
    <div className="max-w-7xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-ink">Procurement Analytics</h1>
        <p className="text-sm text-ink-muted mt-0.5">Aggregate metrics across all procurement activity</p>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        {/* PR by status */}
        <Card>
          <CardHeader title="PR Status Distribution" subtitle="Count by current status" />
          <div className="p-5 h-64">
            {prLoading ? (
              <Skeleton className="h-full w-full" />
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={prChartData}
                    dataKey="count"
                    nameKey="status"
                    cx="50%"
                    cy="50%"
                    outerRadius={80}
                    label={({ status, count }) => `${status} (${count})`}
                    labelLine={false}
                  >
                    {prChartData.map((entry, i) => (
                      <Cell
                        key={i}
                        fill={STATUS_COLORS[entry.status.replace(/ /g, "_")] ?? COLORS[i % COLORS.length]}
                      />
                    ))}
                  </Pie>
                  <Tooltip formatter={(v) => [v, "Count"]} />
                </PieChart>
              </ResponsiveContainer>
            )}
          </div>
        </Card>

        {/* PO value by status */}
        <Card>
          <CardHeader title="PO Value by Status" subtitle="₹ value breakdown" />
          <div className="p-5 h-64">
            {poLoading ? (
              <Skeleton className="h-full w-full" />
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={poChartData} layout="vertical" barCategoryGap="30%">
                  <XAxis
                    type="number"
                    tick={{ fontSize: 11, fill: "#9ca3af" }}
                    axisLine={false}
                    tickLine={false}
                    tickFormatter={(v) => `₹${(v / 100000).toFixed(0)}L`}
                  />
                  <YAxis
                    type="category"
                    dataKey="status"
                    tick={{ fontSize: 10, fill: "#6b7280" }}
                    axisLine={false}
                    tickLine={false}
                    width={90}
                  />
                  <Tooltip
                    formatter={(v: number) => [formatCurrency(v), "Value"]}
                    contentStyle={{ fontSize: 12, borderRadius: 6, border: "1px solid #e4e7ec" }}
                  />
                  <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                    {poChartData.map((_, i) => (
                      <Cell key={i} fill={COLORS[i % COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </Card>

        {/* Top vendors */}
        <Card>
          <CardHeader title="Top Vendors by Spend" subtitle="Last 12 months PO value" />
          {vendorsLoading ? (
            <Skeleton className="h-48 m-4 rounded" />
          ) : vendors && vendors.length > 0 ? (
            <table className="w-full">
              <thead>
                <tr className="border-b border-surface-border">
                  <th className="th text-left">#</th>
                  <th className="th text-left">Vendor</th>
                  <th className="th text-right">PO Count</th>
                  <th className="th text-right">Total Spend</th>
                  <th className="th text-right">Rating</th>
                </tr>
              </thead>
              <tbody>
                {vendors.map((v, i) => (
                  <tr key={v.vendor_id} className="border-b border-surface-border last:border-0">
                    <td className="td text-ink-muted text-xs">{i + 1}</td>
                    <td className="td">
                      <div className="text-sm text-ink">{v.name}</div>
                      <div className="text-2xs text-ink-muted font-mono">{v.vendor_number}</div>
                    </td>
                    <td className="td text-right tabular text-ink-muted">{v.po_count}</td>
                    <td className="td text-right tabular font-medium text-ink">
                      {formatCurrency(v.total_spend)}
                    </td>
                    <td className="td text-right tabular text-ink-muted">
                      {v.avg_rating > 0 ? v.avg_rating.toFixed(1) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="py-8 text-center text-sm text-ink-muted">No vendor data</div>
          )}
        </Card>

        {/* Inventory valuation */}
        <Card>
          <CardHeader
            title="Inventory Valuation"
            subtitle={inventory ? `Total: ${formatCurrency(inventory.grand_total)}` : "—"}
          />
          {inventory?.warehouses ? (
            <table className="w-full">
              <thead>
                <tr className="border-b border-surface-border">
                  <th className="th text-left">Warehouse</th>
                  <th className="th text-right">Lines</th>
                  <th className="th text-right">Value</th>
                </tr>
              </thead>
              <tbody>
                {inventory.warehouses.map((wh) => (
                  <tr key={wh.code} className="border-b border-surface-border last:border-0">
                    <td className="td">
                      <div className="text-sm text-ink">{wh.name}</div>
                      <div className="text-2xs text-ink-muted font-mono">{wh.code}</div>
                    </td>
                    <td className="td text-right tabular text-ink-muted">{wh.line_count}</td>
                    <td className="td text-right tabular font-semibold text-ink">
                      {formatCurrency(wh.total_value)}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="border-t border-surface-border bg-surface">
                  <td colSpan={2} className="td text-right font-semibold text-ink">Grand Total</td>
                  <td className="td text-right tabular font-bold text-ink">
                    {formatCurrency(inventory.grand_total)}
                  </td>
                </tr>
              </tfoot>
            </table>
          ) : (
            <Skeleton className="h-40 m-4 rounded" />
          )}
        </Card>
      </div>
    </div>
  );
}
