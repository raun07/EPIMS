import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import api from "@/lib/api";
import { formatCurrency } from "@/lib/utils";
import { Card, EmptyState } from "@/components/ui";
import { Clock, ChevronDown, ChevronUp } from "lucide-react";

const BUCKET_COLORS: Record<string, string> = {
  "0-30": "#10b981",
  "31-60": "#f59e0b",
  "61-90": "#f97316",
  "90+": "#ef4444",
};

export default function InvoiceAgingReportPage() {
  const [expanded, setExpanded] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["invoice-aging-report"],
    queryFn: () => api.get("/reports/invoice-aging").then(r => r.data),
  });

  const buckets = Array.isArray(data) ? data : [];
  const totalOutstanding = buckets.reduce((s: number, b: any) => s + b.total_balance, 0);
  const chartData = buckets.map((b: any) => ({ bucket: `${b.bucket} days`, value: b.total_balance }));

  return (
    <div className="max-w-5xl space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-ink">Invoice Aging Report</h1>
        <p className="text-sm text-ink-muted mt-0.5">Outstanding balances grouped by overdue period</p>
      </div>

      {isLoading ? (
        <Card className="p-8 text-center text-ink-muted text-sm">Loading…</Card>
      ) : totalOutstanding === 0 ? (
        <EmptyState icon={<Clock className="h-10 w-10" />} title="No overdue invoices" description="Great work — all invoices are current!" />
      ) : (
        <>
          <Card className="p-4">
            <p className="text-2xs text-ink-muted uppercase tracking-widest">Total Outstanding</p>
            <p className="text-2xl font-bold text-ink mt-1">{formatCurrency(totalOutstanding)}</p>
          </Card>

          <Card className="p-4">
            <h3 className="font-semibold text-ink text-sm mb-3">Outstanding by Aging Bucket</h3>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={chartData} barCategoryGap="35%">
                <XAxis dataKey="bucket" tick={{ fontSize: 10 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 10 }} axisLine={false} tickLine={false} tickFormatter={(v) => `₹${(v / 1000).toFixed(0)}k`} />
                <Tooltip formatter={(v: number) => formatCurrency(v)} />
                <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                  {buckets.map((b: any, i: number) => <Cell key={i} fill={BUCKET_COLORS[b.bucket]} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </Card>

          {buckets.map((b: any) => (
            <Card key={b.bucket} className="overflow-hidden">
              <button
                onClick={() => setExpanded(expanded === b.bucket ? null : b.bucket)}
                className="w-full flex items-center justify-between px-4 py-3 hover:bg-surface-hover"
              >
                <div className="flex items-center gap-3">
                  <span className="w-2 h-2 rounded-full" style={{ backgroundColor: BUCKET_COLORS[b.bucket] }} />
                  <span className="text-sm font-medium text-ink">{b.bucket} days overdue</span>
                  <span className="text-2xs text-ink-muted">({b.count} invoice{b.count !== 1 ? "s" : ""})</span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-sm font-semibold text-ink tabular">{formatCurrency(b.total_balance)}</span>
                  {expanded === b.bucket ? <ChevronUp className="h-4 w-4 text-ink-subtle" /> : <ChevronDown className="h-4 w-4 text-ink-subtle" />}
                </div>
              </button>
              {expanded === b.bucket && b.invoices.length > 0 && (
                <table className="w-full border-t border-surface-border">
                  <thead>
                    <tr className="bg-surface">
                      <th className="px-4 py-2 text-left text-2xs font-semibold text-ink-muted uppercase">Invoice #</th>
                      <th className="px-4 py-2 text-left text-2xs font-semibold text-ink-muted uppercase">Due Date</th>
                      <th className="px-4 py-2 text-right text-2xs font-semibold text-ink-muted uppercase">Days Overdue</th>
                      <th className="px-4 py-2 text-right text-2xs font-semibold text-ink-muted uppercase">Balance</th>
                    </tr>
                  </thead>
                  <tbody>
                    {b.invoices.map((inv: any) => (
                      <tr key={inv.invoice_number} className="border-t border-surface-border">
                        <td className="px-4 py-2 text-xs font-mono text-brand-500">{inv.invoice_number}</td>
                        <td className="px-4 py-2 text-xs text-ink-muted">{inv.due_date ?? "—"}</td>
                        <td className="px-4 py-2 text-right tabular text-xs text-ink">{inv.days_overdue}</td>
                        <td className="px-4 py-2 text-right tabular text-xs font-medium text-ink">{formatCurrency(inv.balance)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </Card>
          ))}
        </>
      )}
    </div>
  );
}
