import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Plus, ChevronRight, RefreshCw } from "lucide-react";
import { poApi } from "@/api/procurement";
import { formatCurrency, formatDate } from "@/lib/utils";
import {
  Button,
  Card,
  EmptyState,
  TableSkeleton,
  StatusBadge,
} from "@/components/ui";

const STATUSES = [
  { value: "", label: "All" },
  { value: "DRAFT", label: "Draft" },
  { value: "PENDING_APPROVAL", label: "Pending Approval" },
  { value: "APPROVED", label: "Approved" },
  { value: "RELEASED", label: "Released" },
  { value: "SENT", label: "Sent" },
  { value: "PARTIALLY_RECEIVED", label: "Partly Received" },
  { value: "RECEIVED", label: "Received" },
  { value: "INVOICED", label: "Invoiced" },
  { value: "CLOSED", label: "Closed" },
  { value: "CANCELLED", label: "Cancelled" },
];

export default function POListPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState("");

  const { data, isLoading, isFetching } = useQuery({
    queryKey: ["pos", page, statusFilter],
    queryFn: () => poApi.list({ page, per_page: 20, status: statusFilter || undefined }),
    keepPreviousData: true,
  });

  const pos = data?.data ?? [];
  const meta = data?.meta;

  return (
    <div className="max-w-7xl space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-ink">Purchase Orders</h1>
          <p className="text-sm text-ink-muted mt-0.5">
            {meta ? `${meta.total} total` : "Loading…"}
          </p>
        </div>
        <Button onClick={() => navigate("/procurement/po/new")}>
          <Plus className="h-4 w-4" /> New PO
        </Button>
      </div>

      <Card>
        <div className="flex items-center gap-3 px-4 py-3 border-b border-surface-border">
          <select
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
            className="h-8 rounded border border-surface-border bg-white px-2 text-sm text-ink focus:outline-none focus:ring-2 focus:ring-brand-500"
          >
            {STATUSES.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
          <button
            onClick={() => qc.invalidateQueries({ queryKey: ["pos"] })}
            className="ml-auto text-ink-muted hover:text-ink"
          >
            <RefreshCw className={`h-4 w-4 ${isFetching ? "animate-spin" : ""}`} />
          </button>
        </div>

        {isLoading ? (
          <TableSkeleton rows={8} cols={7} />
        ) : pos.length === 0 ? (
          <EmptyState
            title="No purchase orders"
            description="Create a PO from an approved PR"
            action={
              <Button size="sm" onClick={() => navigate("/procurement/po/new")}>
                <Plus className="h-3.5 w-3.5" /> New PO
              </Button>
            }
          />
        ) : (
          <>
            <table className="w-full">
              <thead>
                <tr className="border-b border-surface-border">
                  <th className="th text-left">PO Number</th>
                  <th className="th text-left">Vendor</th>
                  <th className="th text-left">Type</th>
                  <th className="th text-right">Total</th>
                  <th className="th text-left">Order Date</th>
                  <th className="th text-left">Delivery</th>
                  <th className="th text-left">Status</th>
                  <th className="th" />
                </tr>
              </thead>
              <tbody>
                {pos.map((po) => (
                  <tr
                    key={po.id}
                    onClick={() => navigate(`/procurement/po/${po.id}`)}
                    className="border-b border-surface-border last:border-0 hover:bg-surface-hover cursor-pointer"
                  >
                    <td className="td font-mono text-xs text-brand-500 font-medium">
                      {po.po_number}
                    </td>
                    <td className="td text-ink text-xs">{po.vendor_id.slice(0, 8)}…</td>
                    <td className="td text-ink-muted text-xs">{po.po_type}</td>
                    <td className="td text-right tabular font-medium text-ink">
                      {formatCurrency(parseFloat(po.total_amount), po.currency)}
                    </td>
                    <td className="td text-ink-muted text-xs">
                      {formatDate(po.order_date)}
                    </td>
                    <td className="td text-ink-muted text-xs">
                      {po.delivery_date ? formatDate(po.delivery_date) : "—"}
                    </td>
                    <td className="td">
                      <StatusBadge status={po.status} />
                    </td>
                    <td className="td">
                      <ChevronRight className="h-4 w-4 text-ink-subtle" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {meta && meta.total_pages > 1 && (
              <div className="flex items-center justify-between px-4 py-3 border-t border-surface-border">
                <p className="text-xs text-ink-muted">
                  Page {meta.page} of {meta.total_pages}
                </p>
                <div className="flex gap-2">
                  <Button variant="secondary" size="sm" onClick={() => setPage((p) => p - 1)} disabled={!meta.has_prev}>Previous</Button>
                  <Button variant="secondary" size="sm" onClick={() => setPage((p) => p + 1)} disabled={!meta.has_next}>Next</Button>
                </div>
              </div>
            )}
          </>
        )}
      </Card>
    </div>
  );
}
