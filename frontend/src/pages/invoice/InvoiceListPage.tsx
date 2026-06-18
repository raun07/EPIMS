import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Plus, ChevronRight, RefreshCw } from "lucide-react";
import { invoiceApi } from "@/api/index";
import { formatCurrency, formatDate } from "@/lib/utils";
import { Button, Card, EmptyState, TableSkeleton, StatusBadge } from "@/components/ui";

const STATUSES = [
  { value: "", label: "All" },
  { value: "PENDING_VERIFICATION", label: "Pending Verification" },
  { value: "MATCHED", label: "Matched" },
  { value: "DISPUTED", label: "Disputed" },
  { value: "APPROVED", label: "Approved" },
  { value: "PAID", label: "Paid" },
];

export default function InvoiceListPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState("");

  const { data, isLoading, isFetching } = useQuery({
    queryKey: ["invoices", page, statusFilter],
    queryFn: () => invoiceApi.list({ page, per_page: 20, status: statusFilter || undefined }),
    keepPreviousData: true,
  });

  const invoices = (data?.data as any[]) ?? [];
  const meta = data?.meta as any;

  return (
    <div className="max-w-7xl space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-ink">Invoices</h1>
          <p className="text-sm text-ink-muted mt-0.5">
            {meta ? `${meta.total} total` : "Loading…"}
          </p>
        </div>
        <Button onClick={() => navigate("/invoices/new")}>
          <Plus className="h-4 w-4" /> New Invoice
        </Button>
      </div>

      <Card>
        <div className="flex items-center gap-3 px-4 py-3 border-b border-surface-border">
          <select
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
            className="h-8 rounded border border-surface-border bg-white px-2 text-sm text-ink focus:outline-none focus:ring-2 focus:ring-brand-500"
          >
            {STATUSES.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
          <button
            onClick={() => qc.invalidateQueries({ queryKey: ["invoices"] })}
            className="ml-auto text-ink-muted hover:text-ink"
          >
            <RefreshCw className={`h-4 w-4 ${isFetching ? "animate-spin" : ""}`} />
          </button>
        </div>

        {isLoading ? (
          <TableSkeleton rows={8} cols={7} />
        ) : invoices.length === 0 ? (
          <EmptyState title="No invoices" description="Create an invoice against a received PO" />
        ) : (
          <>
            <table className="w-full">
              <thead>
                <tr className="border-b border-surface-border">
                  <th className="th text-left">Invoice #</th>
                  <th className="th text-left">Vendor Ref</th>
                  <th className="th text-left">Invoice Date</th>
                  <th className="th text-left">Due Date</th>
                  <th className="th text-right">Total</th>
                  <th className="th text-right">Paid</th>
                  <th className="th text-left">Status</th>
                  <th className="th" />
                </tr>
              </thead>
              <tbody>
                {invoices.map((inv: any) => {
                  const isOverdue = inv.due_date && new Date(inv.due_date) < new Date()
                    && !["PAID"].includes(inv.status);
                  return (
                    <tr key={inv.id}
                      onClick={() => navigate(`/invoices/${inv.id}`)}
                      className="border-b border-surface-border last:border-0 hover:bg-surface-hover cursor-pointer">
                      <td className="td font-mono text-xs text-brand-500 font-medium">{inv.invoice_number}</td>
                      <td className="td text-ink-muted text-xs">{inv.vendor_invoice_number ?? "—"}</td>
                      <td className="td text-ink-muted text-xs">{formatDate(inv.invoice_date)}</td>
                      <td className="td text-xs">
                        <span className={isOverdue ? "text-red-500 font-medium" : "text-ink-muted"}>
                          {inv.due_date ? formatDate(inv.due_date) : "—"}
                        </span>
                      </td>
                      <td className="td text-right tabular font-medium">
                        {formatCurrency(parseFloat(inv.total_amount), inv.currency)}
                      </td>
                      <td className="td text-right tabular text-ink-muted">
                        {formatCurrency(parseFloat(inv.paid_amount), inv.currency)}
                      </td>
                      <td className="td"><StatusBadge status={inv.status} /></td>
                      <td className="td"><ChevronRight className="h-4 w-4 text-ink-subtle" /></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>

            {meta?.total_pages > 1 && (
              <div className="flex items-center justify-between px-4 py-3 border-t border-surface-border">
                <p className="text-xs text-ink-muted">Page {meta.page} of {meta.total_pages}</p>
                <div className="flex gap-2">
                  <Button variant="secondary" size="sm" onClick={() => setPage(p => p - 1)} disabled={!meta.has_prev}>Previous</Button>
                  <Button variant="secondary" size="sm" onClick={() => setPage(p => p + 1)} disabled={!meta.has_next}>Next</Button>
                </div>
              </div>
            )}
          </>
        )}
      </Card>
    </div>
  );
}
