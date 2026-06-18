import { useQuery } from "@tanstack/react-query";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import api from "@/lib/api";
import { formatCurrency } from "@/lib/utils";
import { Card, EmptyState } from "@/components/ui";
import { FileText } from "lucide-react";

const COLORS = ["#6366f1", "#f59e0b", "#10b981", "#0ea5e9", "#ef4444", "#8b5cf6", "#94a3b8"];

export default function PRSummaryReportPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["pr-summary"],
    queryFn: () => api.get("/reports/pr-summary").then(r => r.data),
  });

  const byStatus = data?.by_status ?? [];
  const totalValue = byStatus.reduce((s: number, r: any) => s + r.total_value, 0);
  const totalCount = byStatus.reduce((s: number, r: any) => s + r.count, 0);

  return (
    <div className="max-w-5xl space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-ink">PR Summary Report</h1>
        <p className="text-sm text-ink-muted mt-0.5">Purchase requisitions by status with approval timing</p>
      </div>

      {isLoading ? (
        <Card className="p-8 text-center text-ink-muted text-sm">Loading…</Card>
      ) : byStatus.length === 0 ? (
        <EmptyState icon={<FileText className="h-10 w-10" />} title="No PR data yet" description="Create some Purchase Requisitions to see this report" />
      ) : (
        <>
          <div className="grid grid-cols-2 gap-4">
            <Card className="p-4">
              <p className="text-2xs text-ink-muted uppercase tracking-widest">Total PRs</p>
              <p className="text-2xl font-bold text-ink mt-1">{totalCount}</p>
            </Card>
            <Card className="p-4">
              <p className="text-2xs text-ink-muted uppercase tracking-widest">Total Value</p>
              <p className="text-2xl font-bold text-ink mt-1">{formatCurrency(totalValue)}</p>
            </Card>
          </div>

          <Card className="p-4">
            <h3 className="font-semibold text-ink text-sm mb-3">Count by Status</h3>
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={byStatus} barCategoryGap="30%">
                <XAxis dataKey="status" tick={{ fontSize: 10 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 10 }} axisLine={false} tickLine={false} />
                <Tooltip />
                <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                  {byStatus.map((_: any, i: number) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </Card>

          <Card>
            <table className="w-full">
              <thead>
                <tr className="border-b border-surface-border bg-surface">
                  <th className="px-4 py-2 text-left text-2xs font-semibold text-ink-muted uppercase">Status</th>
                  <th className="px-4 py-2 text-right text-2xs font-semibold text-ink-muted uppercase">Count</th>
                  <th className="px-4 py-2 text-right text-2xs font-semibold text-ink-muted uppercase">Total Value</th>
                  <th className="px-4 py-2 text-right text-2xs font-semibold text-ink-muted uppercase">Avg Approval Time</th>
                </tr>
              </thead>
              <tbody>
                {byStatus.map((row: any) => (
                  <tr key={row.status} className="border-b border-surface-border last:border-0">
                    <td className="px-4 py-3 text-sm font-medium text-ink">{row.status.replace(/_/g, " ")}</td>
                    <td className="px-4 py-3 text-right tabular text-ink">{row.count}</td>
                    <td className="px-4 py-3 text-right tabular font-medium text-ink">{formatCurrency(row.total_value)}</td>
                    <td className="px-4 py-3 text-right tabular text-ink-muted">
                      {row.avg_approval_hours != null ? `${row.avg_approval_hours}h` : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        </>
      )}
    </div>
  );
}
