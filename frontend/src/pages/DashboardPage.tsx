import { useQuery } from "@tanstack/react-query";
import {
  FileText,
  ShoppingCart,
  AlertTriangle,
  Package,
  TrendingUp,
} from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { reportsApi } from "@/api/index";
import { formatCurrency } from "@/lib/utils";
import { KPICard, Card, CardHeader, Skeleton, StatusBadge } from "@/components/ui";
import { prApi } from "@/api/procurement";

export default function DashboardPage() {
  const { data: kpis, isLoading: kpisLoading } = useQuery({
    queryKey: ["dashboard-kpis"],
    queryFn: reportsApi.dashboard,
    refetchInterval: 60_000,
  });

  const { data: prs } = useQuery({
    queryKey: ["recent-prs"],
    queryFn: () => prApi.list({ page: 1, per_page: 5 }),
  });

  const { data: aging } = useQuery({
    queryKey: ["invoice-aging"],
    queryFn: reportsApi.invoiceAging,
  });

  const agingChartData = aging?.map((a) => ({
    bucket: a.bucket,
    total: a.total_balance,
    count: a.count,
  })) ?? [];

  const COLORS = ["#6366f1", "#f59e0b", "#ef4444", "#991b1b"];

  return (
    <div className="space-y-6 max-w-7xl">
      {/* Page header */}
      <div>
        <h1 className="text-xl font-semibold text-ink">Dashboard</h1>
        <p className="text-sm text-ink-muted mt-0.5">
          Live procurement overview — refreshes every minute
        </p>
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
        {kpisLoading ? (
          Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-28 rounded-lg" />
          ))
        ) : (
          <>
            <KPICard
              label="PRs pending approval"
              value={kpis?.pending_pr_approvals ?? 0}
              icon={<FileText className="h-5 w-5" />}
            />
            <KPICard
              label="Open PO value"
              value={formatCurrency(kpis?.open_po_value ?? 0)}
              icon={<ShoppingCart className="h-5 w-5" />}
            />
            <KPICard
              label="Overdue invoices"
              value={kpis?.overdue_invoices ?? 0}
              icon={<AlertTriangle className="h-5 w-5" />}
              accent="amber"
            />
            <KPICard
              label="Low stock alerts"
              value={kpis?.low_stock_alerts ?? 0}
              icon={<Package className="h-5 w-5" />}
              accent="amber"
            />
          </>
        )}
      </div>

      {/* Charts + recent row */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        {/* Invoice aging chart */}
        <Card>
          <CardHeader
            title="Invoice Aging"
            subtitle="Outstanding balances by overdue period"
          />
          <div className="p-5 h-56">
            {aging && aging.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={agingChartData} barCategoryGap="35%">
                  <XAxis
                    dataKey="bucket"
                    tick={{ fontSize: 11, fill: "#9ca3af" }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    tick={{ fontSize: 11, fill: "#9ca3af" }}
                    axisLine={false}
                    tickLine={false}
                    tickFormatter={(v) => `₹${(v / 1000).toFixed(0)}k`}
                  />
                  <Tooltip
                    formatter={(v: number) => [formatCurrency(v), "Balance"]}
                    contentStyle={{
                      fontSize: 12,
                      borderRadius: 6,
                      border: "1px solid #e4e7ec",
                    }}
                  />
                  <Bar dataKey="total" radius={[4, 4, 0, 0]}>
                    {agingChartData.map((_, i) => (
                      <Cell key={i} fill={COLORS[i % COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex items-center justify-center h-full text-sm text-ink-muted">
                No overdue invoices — great work!
              </div>
            )}
          </div>
        </Card>

        {/* Recent PRs */}
        <Card>
          <CardHeader title="Recent Requisitions" />
          <div>
            {prs?.data && prs.data.length > 0 ? (
              <table className="w-full">
                <thead>
                  <tr className="border-b border-surface-border">
                    <th className="th text-left">PR Number</th>
                    <th className="th text-left">Title</th>
                    <th className="th text-right">Value</th>
                    <th className="th text-left">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {prs.data.map((pr) => (
                    <tr
                      key={pr.id}
                      className="border-b border-surface-border last:border-0 hover:bg-surface-hover"
                    >
                      <td className="td font-mono text-xs text-brand-500">
                        {pr.pr_number}
                      </td>
                      <td className="td text-ink max-w-[160px] truncate">
                        {pr.title}
                      </td>
                      <td className="td text-right tabular text-ink-muted">
                        {formatCurrency(parseFloat(pr.total_value))}
                      </td>
                      <td className="td">
                        <StatusBadge status={pr.status} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="py-10 text-center text-sm text-ink-muted">
                No requisitions yet
              </div>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}
