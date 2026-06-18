// src/pages/master/MaterialsPage.tsx
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Search, Package, ChevronRight } from "lucide-react";
import { masterApi } from "@/api/index";
import { formatCurrency } from "@/lib/utils";
import { Card, CardHeader, EmptyState, TableSkeleton } from "@/components/ui";

export default function MaterialsPage() {
  const [page, setPage] = useState(1);
  const [q, setQ] = useState("");
  const [search, setSearch] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["materials", page, search],
    queryFn: () => masterApi.materials.list({ page, per_page: 25, q: search || undefined }),
    keepPreviousData: true,
  });

  const materials = (data?.data as any[]) ?? [];
  const meta = data?.meta as any;

  return (
    <div className="max-w-6xl space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-ink">Materials</h1>
        <p className="text-sm text-ink-muted mt-0.5">
          {meta ? `${meta.total} materials registered` : "Loading…"}
        </p>
      </div>

      <Card>
        <div className="flex items-center gap-3 px-4 py-3 border-b border-surface-border">
          <div className="relative flex-1 max-w-xs">
            <Search className="absolute left-2.5 top-2 h-4 w-4 text-ink-subtle" />
            <input
              className="w-full h-8 pl-8 pr-3 rounded border border-surface-border text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              placeholder="Search by description or number…"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && setSearch(q)}
            />
          </div>
          <button
            onClick={() => setSearch(q)}
            className="h-8 px-3 rounded bg-brand-500 text-white text-sm hover:bg-brand-600"
          >Search</button>
        </div>

        {isLoading ? (
          <TableSkeleton rows={10} cols={6} />
        ) : materials.length === 0 ? (
          <EmptyState icon={<Package className="h-10 w-10" />} title="No materials found" />
        ) : (
          <>
            <table className="w-full">
              <thead>
                <tr className="border-b border-surface-border">
                  <th className="th text-left">Material Number</th>
                  <th className="th text-left">Description</th>
                  <th className="th text-left">Type</th>
                  <th className="th text-right">Std Price</th>
                  <th className="th text-right">Reorder Pt.</th>
                  <th className="th text-left">Status</th>
                </tr>
              </thead>
              <tbody>
                {materials.map((m: any) => (
                  <tr key={m.id} className="border-b border-surface-border last:border-0 hover:bg-surface-hover">
                    <td className="td font-mono text-xs text-brand-500 font-medium">{m.material_number}</td>
                    <td className="td text-ink">{m.description}</td>
                    <td className="td text-ink-muted text-xs">{m.material_type}</td>
                    <td className="td text-right tabular text-ink-muted">
                      {m.standard_price ? formatCurrency(parseFloat(m.standard_price), m.currency) : "—"}
                    </td>
                    <td className="td text-right tabular text-ink-muted">
                      {m.reorder_point ?? "—"}
                    </td>
                    <td className="td">
                      <span className={`badge ${m.is_active ? "badge-approved" : "badge-cancelled"}`}>
                        {m.is_active ? "Active" : "Inactive"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {meta?.total_pages > 1 && (
              <div className="flex justify-between items-center px-4 py-3 border-t border-surface-border">
                <p className="text-xs text-ink-muted">Page {meta.page} of {meta.total_pages}</p>
                <div className="flex gap-2">
                  <button onClick={() => setPage(p => p - 1)} disabled={!meta.has_prev}
                    className="h-7 px-3 rounded border border-surface-border text-xs disabled:opacity-50">Previous</button>
                  <button onClick={() => setPage(p => p + 1)} disabled={!meta.has_next}
                    className="h-7 px-3 rounded border border-surface-border text-xs disabled:opacity-50">Next</button>
                </div>
              </div>
            )}
          </>
        )}
      </Card>
    </div>
  );
}
