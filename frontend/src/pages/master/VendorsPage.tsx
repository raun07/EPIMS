import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Search, Ban, CheckCircle, ChevronRight } from "lucide-react";
import { masterApi } from "@/api/index";
import { Button, Card, EmptyState, TableSkeleton, StatusBadge } from "@/components/ui";

export default function VendorsPage() {
  const qc = useQueryClient();
  const [page, setPage] = useState(1);
  const [q, setQ] = useState("");
  const [search, setSearch] = useState("");
  const [blockModal, setBlockModal] = useState<{ vendorId: string; name: string } | null>(null);
  const [blockReason, setBlockReason] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["vendors", page, search],
    queryFn: () => masterApi.vendors.list({ page, per_page: 20, q: search || undefined }),
    keepPreviousData: true,
  });

  const vendors = (data?.data as any[]) ?? [];
  const meta = data?.meta as any;

  const blockMutation = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      masterApi.vendors.block(id, reason),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["vendors"] }); setBlockModal(null); },
  });

  const unblockMutation = useMutation({
    mutationFn: (id: string) => masterApi.vendors.unblock(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["vendors"] }),
  });

  return (
    <div className="max-w-6xl space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-ink">Vendors</h1>
        <p className="text-sm text-ink-muted mt-0.5">
          {meta ? `${meta.total} vendors` : "Loading…"}
        </p>
      </div>

      <Card>
        <div className="flex items-center gap-3 px-4 py-3 border-b border-surface-border">
          <div className="relative flex-1 max-w-xs">
            <Search className="absolute left-2.5 top-2 h-4 w-4 text-ink-subtle" />
            <input
              className="w-full h-8 pl-8 pr-3 rounded border border-surface-border text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              placeholder="Search vendors…"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && setSearch(q)}
            />
          </div>
          <button onClick={() => setSearch(q)}
            className="h-8 px-3 rounded bg-brand-500 text-white text-sm hover:bg-brand-600">
            Search
          </button>
        </div>

        {isLoading ? (
          <TableSkeleton rows={8} cols={7} />
        ) : vendors.length === 0 ? (
          <EmptyState title="No vendors found" description="Add vendors to start creating purchase orders" />
        ) : (
          <>
            <table className="w-full">
              <thead>
                <tr className="border-b border-surface-border">
                  <th className="th text-left">Vendor #</th>
                  <th className="th text-left">Name</th>
                  <th className="th text-left">Type</th>
                  <th className="th text-left">GST</th>
                  <th className="th text-left">Payment Terms</th>
                  <th className="th text-right">Rating</th>
                  <th className="th text-left">Status</th>
                  <th className="th text-center">Actions</th>
                </tr>
              </thead>
              <tbody>
                {vendors.map((v: any) => (
                  <tr key={v.id} className="border-b border-surface-border last:border-0 hover:bg-surface-hover">
                    <td className="td font-mono text-xs text-brand-500 font-medium">{v.vendor_number}</td>
                    <td className="td">
                      <div className="text-sm font-medium text-ink">{v.name}</div>
                      {v.email && <div className="text-2xs text-ink-muted">{v.email}</div>}
                    </td>
                    <td className="td text-ink-muted text-xs">{v.vendor_type}</td>
                    <td className="td font-mono text-xs text-ink-muted">{v.gst_number ?? "—"}</td>
                    <td className="td text-ink-muted text-xs">{v.payment_terms}</td>
                    <td className="td text-right tabular text-ink-muted">
                      {v.rating ? parseFloat(v.rating).toFixed(1) : "—"}
                    </td>
                    <td className="td"><StatusBadge status={v.status} /></td>
                    <td className="td">
                      <div className="flex items-center justify-center">
                        {v.status === "BLOCKED" ? (
                          <button
                            title="Unblock"
                            onClick={() => unblockMutation.mutate(v.id)}
                            className="h-7 w-7 flex items-center justify-center rounded hover:bg-emerald-50 text-emerald-500"
                          >
                            <CheckCircle className="h-3.5 w-3.5" />
                          </button>
                        ) : (
                          <button
                            title="Block vendor"
                            onClick={() => { setBlockModal({ vendorId: v.id, name: v.name }); setBlockReason(""); }}
                            className="h-7 w-7 flex items-center justify-center rounded hover:bg-red-50 text-red-400"
                          >
                            <Ban className="h-3.5 w-3.5" />
                          </button>
                        )}
                      </div>
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

      {blockModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-lg shadow-xl p-6 w-full max-w-md mx-4">
            <h3 className="font-semibold text-ink mb-1">Block Vendor</h3>
            <p className="text-sm text-ink-muted mb-4">
              Blocking <strong>{blockModal.name}</strong> prevents new POs from being created.
            </p>
            <textarea
              value={blockReason}
              onChange={(e) => setBlockReason(e.target.value)}
              placeholder="Reason for blocking (min 10 characters)…"
              rows={3}
              className="w-full border border-surface-border rounded px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
            <div className="flex gap-2 mt-4 justify-end">
              <Button variant="secondary" size="sm" onClick={() => setBlockModal(null)}>Cancel</Button>
              <Button variant="danger" size="sm"
                disabled={blockReason.trim().length < 10}
                loading={blockMutation.isPending}
                onClick={() => blockMutation.mutate({ id: blockModal.vendorId, reason: blockReason })}>
                Block Vendor
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
