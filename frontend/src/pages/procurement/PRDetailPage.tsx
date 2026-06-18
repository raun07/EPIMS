import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Send, X, RotateCcw, Printer } from "lucide-react";
import { prApi } from "@/api/procurement";
import { formatCurrency, formatDate, formatDateTime } from "@/lib/utils";
import { Button, Card, CardHeader, StatusBadge, Skeleton } from "@/components/ui";
import { useState } from "react";

export default function PRDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [rejectReason, setRejectReason] = useState("");
  const [showRejectModal, setShowRejectModal] = useState(false);

  const { data: pr, isLoading } = useQuery({
    queryKey: ["pr", id],
    queryFn: () => prApi.get(id!),
    enabled: !!id,
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["pr", id] });
    queryClient.invalidateQueries({ queryKey: ["prs"] });
  };

  const submitMutation = useMutation({
    mutationFn: () => prApi.submit(id!),
    onSuccess: invalidate,
  });

  const cancelMutation = useMutation({
    mutationFn: () => prApi.cancel(id!),
    onSuccess: invalidate,
  });

  const rejectMutation = useMutation({
    mutationFn: (reason: string) => prApi.reject(id!, reason),
    onSuccess: () => { invalidate(); setShowRejectModal(false); },
  });

  if (isLoading) {
    return (
      <div className="max-w-4xl space-y-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-64 rounded-lg" />
        <Skeleton className="h-40 rounded-lg" />
      </div>
    );
  }

  if (!pr) return <div className="text-ink-muted text-sm">PR not found</div>;

  const canSubmit = pr.status === "DRAFT";
  const canCancel = ["DRAFT", "SUBMITTED"].includes(pr.status);
  const canReject = pr.status === "PENDING_APPROVAL";

  return (
    <div className="max-w-4xl space-y-4">
      {/* Back + actions bar */}
      <div className="flex items-center gap-4">
        <button
          onClick={() => navigate("/procurement/pr")}
          className="text-ink-muted hover:text-ink"
        >
          <ArrowLeft className="h-5 w-5" />
        </button>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="text-lg font-semibold text-ink font-mono">{pr.pr_number}</h1>
            <StatusBadge status={pr.status} />
          </div>
          <p className="text-sm text-ink-muted mt-0.5">{pr.title}</p>
        </div>
        <div className="flex gap-2">
          {canReject && (
            <Button variant="danger" size="sm" onClick={() => setShowRejectModal(true)}>
              Return for revision
            </Button>
          )}
          {canCancel && (
            <Button
              variant="secondary"
              size="sm"
              loading={cancelMutation.isPending}
              onClick={() => cancelMutation.mutate()}
            >
              <X className="h-3.5 w-3.5" /> Cancel
            </Button>
          )}
          {canSubmit && (
            <Button
              size="sm"
              loading={submitMutation.isPending}
              onClick={() => submitMutation.mutate()}
            >
              <Send className="h-3.5 w-3.5" /> Submit for approval
            </Button>
          )}
        </div>
      </div>

      {/* Header info */}
      <Card>
        <CardHeader title="Requisition Details" />
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 p-5">
          {[
            { label: "Priority", value: pr.priority },
            { label: "Department", value: pr.department ?? "—" },
            { label: "Cost Centre", value: pr.cost_center ?? "—" },
            {
              label: "Required by",
              value: pr.required_date ? formatDate(pr.required_date) : "—",
            },
            {
              label: "Submitted",
              value: pr.submitted_at ? formatDateTime(pr.submitted_at) : "—",
            },
            {
              label: "Approved",
              value: pr.approved_at ? formatDateTime(pr.approved_at) : "—",
            },
            {
              label: "Total value",
              value: formatCurrency(parseFloat(pr.total_value), pr.currency),
              bold: true,
            },
            {
              label: "Created",
              value: formatDateTime(pr.created_at),
            },
          ].map(({ label, value, bold }) => (
            <div key={label}>
              <p className="text-2xs text-ink-muted uppercase tracking-widest">{label}</p>
              <p className={`mt-0.5 text-sm ${bold ? "font-semibold text-ink" : "text-ink"}`}>
                {value}
              </p>
            </div>
          ))}
        </div>

        {pr.notes && (
          <div className="px-5 pb-4 border-t border-surface-border pt-4">
            <p className="text-2xs text-ink-muted uppercase tracking-widest mb-1">Notes</p>
            <p className="text-sm text-ink">{pr.notes}</p>
          </div>
        )}

        {pr.rejection_reason && (
          <div className="px-5 pb-4 border-t border-surface-border pt-4 bg-red-50">
            <p className="text-2xs text-red-500 uppercase tracking-widest mb-1">
              Return reason
            </p>
            <p className="text-sm text-red-700">{pr.rejection_reason}</p>
          </div>
        )}
      </Card>

      {/* Line items */}
      <Card>
        <CardHeader
          title="Line Items"
          subtitle={`${pr.items.length} item${pr.items.length !== 1 ? "s" : ""}`}
        />
        <table className="w-full">
          <thead>
            <tr className="border-b border-surface-border">
              <th className="th text-left w-10">#</th>
              <th className="th text-left">Description</th>
              <th className="th text-right">Qty</th>
              <th className="th text-right">Est. Price</th>
              <th className="th text-right">Est. Value</th>
              <th className="th text-left">Status</th>
            </tr>
          </thead>
          <tbody>
            {pr.items.map((item) => (
              <tr
                key={item.id}
                className="border-b border-surface-border last:border-0"
              >
                <td className="td text-ink-muted text-xs">{item.line_number}</td>
                <td className="td text-ink">{item.description}</td>
                <td className="td text-right tabular">{item.quantity}</td>
                <td className="td text-right tabular text-ink-muted">
                  {item.estimated_price
                    ? formatCurrency(parseFloat(item.estimated_price), item.currency)
                    : "—"}
                </td>
                <td className="td text-right tabular font-medium">
                  {item.estimated_value
                    ? formatCurrency(parseFloat(item.estimated_value), item.currency)
                    : "—"}
                </td>
                <td className="td">
                  <StatusBadge status={item.status} />
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="border-t border-surface-border bg-surface">
              <td colSpan={4} className="td text-right font-semibold text-ink">
                Total
              </td>
              <td className="td text-right tabular font-bold text-ink">
                {formatCurrency(parseFloat(pr.total_value), pr.currency)}
              </td>
              <td className="td" />
            </tr>
          </tfoot>
        </table>
      </Card>

      {/* Reject modal */}
      {showRejectModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-lg shadow-xl p-6 w-full max-w-md mx-4">
            <h3 className="font-semibold text-ink mb-1">Return for revision</h3>
            <p className="text-sm text-ink-muted mb-4">
              The requester will be notified with your reason.
            </p>
            <textarea
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              placeholder="Explain what needs to be corrected…"
              rows={3}
              className="w-full border border-surface-border rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none"
            />
            <div className="flex gap-2 mt-4 justify-end">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setShowRejectModal(false)}
              >
                Cancel
              </Button>
              <Button
                variant="danger"
                size="sm"
                disabled={rejectReason.trim().length < 10}
                loading={rejectMutation.isPending}
                onClick={() => rejectMutation.mutate(rejectReason)}
              >
                Return PR
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
