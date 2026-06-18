import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, RotateCcw, CheckCircle, Clock } from "lucide-react";
import { useState } from "react";
import { grnApi } from "@/api/procurement";
import { formatCurrency, formatDate, formatDateTime } from "@/lib/utils";
import { Button, Card, CardHeader, StatusBadge, Skeleton } from "@/components/ui";

export default function GRNDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [reverseReason, setReverseReason] = useState("");
  const [showReverseModal, setShowReverseModal] = useState(false);

  const { data: grn, isLoading } = useQuery({
    queryKey: ["grn", id],
    queryFn: () => grnApi.get(id!),
    enabled: !!id,
  });

  const invalidate = () => qc.invalidateQueries({ queryKey: ["grn", id] });

  const postMutation = useMutation({
    mutationFn: () => grnApi.post(id!),
    onSuccess: invalidate,
  });

  const reverseMutation = useMutation({
    mutationFn: (reason: string) => grnApi.reverse(id!, reason),
    onSuccess: () => { invalidate(); setShowReverseModal(false); },
  });

  if (isLoading) return (
    <div className="max-w-4xl space-y-4">
      <Skeleton className="h-8 w-48" />
      <Skeleton className="h-64 rounded-lg" />
    </div>
  );

  if (!grn) return <div className="text-ink-muted p-4">GRN not found.</div>;

  const isDraft = grn.status === "DRAFT";
  const isPosted = grn.status === "POSTED";

  const totalAccepted = grn.items.reduce((s, i) => s + parseFloat(i.quantity_accepted), 0);
  const totalRejected = grn.items.reduce((s, i) => s + parseFloat(i.quantity_rejected), 0);

  return (
    <div className="max-w-4xl space-y-4">
      <div className="flex items-center gap-3">
        <button onClick={() => navigate(-1)} className="text-ink-muted hover:text-ink">
          <ArrowLeft className="h-5 w-5" />
        </button>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="text-lg font-semibold text-ink font-mono">{grn.grn_number}</h1>
            <StatusBadge status={grn.status} />
          </div>
          <p className="text-xs text-ink-muted mt-0.5">
            Receipt Date: {formatDate(grn.receipt_date)} ·{" "}
            {grn.delivery_note ? `DN: ${grn.delivery_note}` : "No delivery note"}
          </p>
        </div>
        <div className="flex gap-2">
          {isDraft && (
            <Button size="sm" loading={postMutation.isPending} onClick={() => postMutation.mutate()}>
              <CheckCircle className="h-3.5 w-3.5" /> Post GRN
            </Button>
          )}
          {isPosted && (
            <Button variant="danger" size="sm" onClick={() => setShowReverseModal(true)}>
              <RotateCcw className="h-3.5 w-3.5" /> Reverse
            </Button>
          )}
        </div>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-3 gap-3">
        <Card className="p-4">
          <p className="text-2xs text-ink-muted uppercase tracking-widest">Total Value</p>
          <p className="text-xl font-bold tabular text-ink mt-1">
            {formatCurrency(parseFloat(grn.total_value), grn.currency)}
          </p>
        </Card>
        <Card className="p-4">
          <p className="text-2xs text-ink-muted uppercase tracking-widest">Total Accepted</p>
          <p className="text-xl font-bold tabular text-emerald-600 mt-1">
            {totalAccepted.toFixed(3)}
          </p>
        </Card>
        <Card className="p-4">
          <p className="text-2xs text-ink-muted uppercase tracking-widest">Total Rejected</p>
          <p className={`text-xl font-bold tabular mt-1 ${totalRejected > 0 ? "text-red-500" : "text-ink-muted"}`}>
            {totalRejected.toFixed(3)}
          </p>
        </Card>
      </div>

      {/* Header details */}
      <Card>
        <CardHeader title="GRN Details" />
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 p-5">
          {[
            { label: "Warehouse ID", value: grn.warehouse_id.slice(0, 14) + "…" },
            { label: "PO Reference", value: grn.po_id.slice(0, 14) + "…" },
            { label: "Posted By", value: grn.posted_by ? grn.posted_by.slice(0, 14) + "…" : "—" },
            { label: "Posted At", value: grn.posted_at ? formatDateTime(grn.posted_at) : "—" },
          ].map(({ label, value }) => (
            <div key={label}>
              <p className="text-2xs text-ink-muted uppercase tracking-widest">{label}</p>
              <p className="mt-0.5 text-sm text-ink font-mono">{value}</p>
            </div>
          ))}
        </div>

        {/* Post status banner */}
        {isDraft && (
          <div className="mx-4 mb-4 flex items-center gap-2 bg-amber-50 border border-amber-200 rounded px-4 py-3">
            <Clock className="h-4 w-4 text-amber-500 flex-shrink-0" />
            <p className="text-sm text-amber-700">
              This GRN is a draft. Stock will not be updated until you post it.
            </p>
          </div>
        )}
        {isPosted && (
          <div className="mx-4 mb-4 flex items-center gap-2 bg-emerald-50 border border-emerald-200 rounded px-4 py-3">
            <CheckCircle className="h-4 w-4 text-emerald-500 flex-shrink-0" />
            <p className="text-sm text-emerald-700">
              GRN posted — stock has been updated with movement type 101 (GR vs PO).
            </p>
          </div>
        )}
      </Card>

      {/* Line items */}
      <Card>
        <CardHeader title="Received Lines" />
        <table className="w-full">
          <thead>
            <tr className="border-b border-surface-border">
              <th className="th text-left w-8">#</th>
              <th className="th text-left">Material</th>
              <th className="th text-right">Delivered</th>
              <th className="th text-right">Accepted</th>
              <th className="th text-right">Rejected</th>
              <th className="th text-right">Unit Price</th>
              <th className="th text-right">Net Value</th>
              <th className="th text-left">Batch</th>
            </tr>
          </thead>
          <tbody>
            {grn.items.map((item) => {
              const rejected = parseFloat(item.quantity_rejected);
              return (
                <tr key={item.id} className="border-b border-surface-border last:border-0">
                  <td className="td text-ink-muted text-xs">{item.line_number}</td>
                  <td className="td">
                    <div className="text-xs font-mono text-brand-500">
                      {item.material_id?.slice(0, 10)}…
                    </div>
                    {item.inspection_note && (
                      <div className="text-2xs text-ink-muted">{item.inspection_note}</div>
                    )}
                    {item.rejection_reason && (
                      <div className="text-2xs text-red-500">{item.rejection_reason}</div>
                    )}
                  </td>
                  <td className="td text-right tabular">{item.quantity_delivered}</td>
                  <td className="td text-right tabular text-emerald-600 font-medium">
                    {item.quantity_accepted}
                  </td>
                  <td className="td text-right tabular">
                    <span className={rejected > 0 ? "text-red-500 font-medium" : "text-ink-subtle"}>
                      {item.quantity_rejected}
                    </span>
                  </td>
                  <td className="td text-right tabular text-ink-muted">
                    {item.unit_price ? formatCurrency(parseFloat(item.unit_price), grn.currency) : "—"}
                  </td>
                  <td className="td text-right tabular font-medium">
                    {item.net_value ? formatCurrency(parseFloat(item.net_value), grn.currency) : "—"}
                  </td>
                  <td className="td text-ink-muted text-xs font-mono">
                    {item.batch_number ?? "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
          <tfoot>
            <tr className="border-t-2 border-surface-border bg-surface">
              <td colSpan={6} className="td text-right font-semibold text-ink">Total Value</td>
              <td className="td text-right tabular font-bold text-ink">
                {formatCurrency(parseFloat(grn.total_value), grn.currency)}
              </td>
              <td />
            </tr>
          </tfoot>
        </table>
      </Card>

      {/* Reverse modal */}
      {showReverseModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-lg shadow-xl p-6 w-full max-w-md mx-4">
            <h3 className="font-semibold text-ink mb-1">Reverse GRN</h3>
            <p className="text-sm text-ink-muted mb-4">
              This will create reversal movements (type 122) and deduct stock.
              This action cannot be undone.
            </p>
            <textarea
              value={reverseReason}
              onChange={(e) => setReverseReason(e.target.value)}
              placeholder="Reason for reversal (min 10 characters)…"
              rows={3}
              className="w-full border border-surface-border rounded px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
            <div className="flex gap-2 mt-4 justify-end">
              <Button variant="secondary" size="sm" onClick={() => setShowReverseModal(false)}>
                Cancel
              </Button>
              <Button
                variant="danger"
                size="sm"
                disabled={reverseReason.trim().length < 10}
                loading={reverseMutation.isPending}
                onClick={() => reverseMutation.mutate(reverseReason)}
              >
                Confirm Reversal
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
