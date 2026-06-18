import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import { formatCurrency } from "@/lib/utils";
import { Card, EmptyState } from "@/components/ui";
import { Award, Star } from "lucide-react";

export default function VendorPerformanceReportPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["vendor-performance"],
    queryFn: () => api.get("/reports/vendor-performance?limit=20").then(r => r.data),
  });

  const vendors = Array.isArray(data) ? data : [];

  return (
    <div className="max-w-5xl space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-ink">Vendor Performance Report</h1>
        <p className="text-sm text-ink-muted mt-0.5">Top vendors ranked by total spend</p>
      </div>

      {isLoading ? (
        <Card className="p-8 text-center text-ink-muted text-sm">Loading…</Card>
      ) : vendors.length === 0 ? (
        <EmptyState icon={<Award className="h-10 w-10" />} title="No vendor data yet" description="Create Purchase Orders against vendors to see this report" />
      ) : (
        <Card>
          <table className="w-full">
            <thead>
              <tr className="border-b border-surface-border bg-surface">
                <th className="px-4 py-2 text-left text-2xs font-semibold text-ink-muted uppercase">#</th>
                <th className="px-4 py-2 text-left text-2xs font-semibold text-ink-muted uppercase">Vendor</th>
                <th className="px-4 py-2 text-right text-2xs font-semibold text-ink-muted uppercase">PO Count</th>
                <th className="px-4 py-2 text-right text-2xs font-semibold text-ink-muted uppercase">Total Spend</th>
                <th className="px-4 py-2 text-right text-2xs font-semibold text-ink-muted uppercase">Rating</th>
              </tr>
            </thead>
            <tbody>
              {vendors.map((v: any, idx: number) => (
                <tr key={v.vendor_id} className="border-b border-surface-border last:border-0 hover:bg-surface-hover">
                  <td className="px-4 py-3 text-sm text-ink-muted">{idx + 1}</td>
                  <td className="px-4 py-3">
                    <p className="text-sm font-medium text-ink">{v.name}</p>
                    <p className="text-2xs text-ink-muted font-mono">{v.vendor_number}</p>
                  </td>
                  <td className="px-4 py-3 text-right tabular text-ink">{v.po_count}</td>
                  <td className="px-4 py-3 text-right tabular font-medium text-ink">{formatCurrency(v.total_spend)}</td>
                  <td className="px-4 py-3 text-right">
                    <span className="inline-flex items-center gap-1 text-sm text-ink">
                      <Star className="h-3.5 w-3.5 text-amber-400 fill-amber-400" />
                      {v.avg_rating ? Number(v.avg_rating).toFixed(1) : "—"}
                    </span>
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
