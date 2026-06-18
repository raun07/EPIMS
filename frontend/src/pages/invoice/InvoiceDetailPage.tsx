import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, CheckCircle, AlertTriangle, DollarSign, Shield } from "lucide-react";
import { invoiceApi } from "@/api/index";
import { formatCurrency, formatDate, formatDateTime } from "@/lib/utils";
import { Button, Card, CardHeader, StatusBadge, Skeleton } from "@/components/ui";

export default function InvoiceDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [overrideReason, setOverrideReason] = useState("");
  const [payAmount, setPayAmount] = useState("");
  const [showOverrideModal, setShowOverrideModal] = useState(false);
  const [showPayModal, setShowPayModal] = useState(false);
  const [matchResult, setMatchResult] = useState<any>(null);

  const { data: inv, isLoading } = useQuery({
    queryKey: ["invoice", id],
    queryFn: () => invoiceApi.get(id!),
    enabled: !!id,
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["invoice", id] });
    qc.invalidateQueries({ queryKey: ["invoices"] });
  };

  const verifyMutation = useMutation({
    mutationFn: () => invoiceApi.verify(id!),
    onSuccess: (data) => { setMatchResult(data); invalidate(); },
    onError: (err: any) => {
      // 400 means match failed — show result from error body
      if (err?.response?.status === 400) {
        setMatchResult({ match_result: "FAILED", notes: err.response?.data?.detail });
      }
      invalidate();
    },
  });

  const overrideMutation = useMutation({
    mutationFn: () => invoiceApi.override(id!, overrideReason),
    onSuccess: () => { invalidate(); setShowOverrideModal(false); },
  });

  const payMutation = useMutation({
    mutationFn: () => invoiceApi.markPaid(id!, parseFloat(payAmount)),
    onSuccess: () => { invalidate(); setShowPayModal(false); },
  });

  if (isLoading) return (
    <div className="max-w-4xl space-y-4">
      <Skeleton className="h-8 w-48" /> <Skeleton className="h-64 rounded-lg" />
    </div>
  );
  if (!inv) return <div className="text-ink-muted p-4">Invoice not found.</div>;

  const total = parseFloat(inv.total_amount);
  const paid = parseFloat(inv.paid_amount);
  const balance = total - paid;
  const canVerify = inv.status === "PENDING_VERIFICATION" && inv.po_id;
  const canOverride = inv.status === "DISPUTED";
  const canPay = ["MATCHED", "APPROVED"].includes(inv.status) && balance > 0;

  const matchFlagColor = (flag: string) => {
    if (flag === "MATCHED") return "text-emerald-600";
    if (flag === "PRICE_VARIANCE" || flag === "QTY_VARIANCE") return "text-amber-500";
    return "text-red-500";
  };

  return (
    <div className="max-w-4xl space-y-4">
      <div className="flex items-center gap-3">
        <button onClick={() => navigate("/invoices")} className="text-ink-muted hover:text-ink">
          <ArrowLeft className="h-5 w-5" />
        </button>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="text-lg font-semibold text-ink font-mono">{inv.invoice_number}</h1>
            <StatusBadge status={inv.status} />
          </div>
          <p className="text-xs text-ink-muted mt-0.5">
            {inv.vendor_invoice_number ? `Vendor ref: ${inv.vendor_invoice_number} · ` : ""}
            Invoice date: {formatDate(inv.invoice_date)}
          </p>
        </div>
        <div className="flex gap-2">
          {canVerify && (
            <Button size="sm" loading={verifyMutation.isPending} onClick={() => verifyMutation.mutate()}>
              <CheckCircle className="h-3.5 w-3.5" /> Run 3-Way Match
            </Button>
          )}
          {canOverride && (
            <Button variant="secondary" size="sm" onClick={() => setShowOverrideModal(true)}>
              <Shield className="h-3.5 w-3.5" /> Finance Override
            </Button>
          )}
          {canPay && (
            <Button size="sm" onClick={() => setShowPayModal(true)}>
              <DollarSign className="h-3.5 w-3.5" /> Record Payment
            </Button>
          )}
        </div>
      </div>

      {/* Financials */}
      <div className="grid grid-cols-3 gap-3">
        <Card className="p-4">
          <p className="text-2xs text-ink-muted uppercase tracking-widest">Total</p>
          <p className="text-xl font-bold tabular text-ink mt-1">{formatCurrency(total, inv.currency)}</p>
        </Card>
        <Card className="p-4">
          <p className="text-2xs text-ink-muted uppercase tracking-widest">Paid</p>
          <p className="text-xl font-bold tabular text-emerald-600 mt-1">{formatCurrency(paid, inv.currency)}</p>
        </Card>
        <Card className="p-4">
          <p className="text-2xs text-ink-muted uppercase tracking-widest">Balance Due</p>
          <p className={`text-xl font-bold tabular mt-1 ${balance > 0 ? "text-amber-500" : "text-ink-muted"}`}>
            {formatCurrency(balance, inv.currency)}
          </p>
        </Card>
      </div>

      {/* Match result banner */}
      {(matchResult || inv.dispute_reason) && (
        <Card className={`border-l-4 ${matchResult?.match_result === "FAILED" || inv.status === "DISPUTED"
          ? "border-red-400" : "border-emerald-400"}`}>
          <div className="p-4 flex items-start gap-3">
            {inv.status === "DISPUTED" || matchResult?.match_result === "FAILED"
              ? <AlertTriangle className="h-5 w-5 text-red-500 flex-shrink-0 mt-0.5" />
              : <CheckCircle className="h-5 w-5 text-emerald-500 flex-shrink-0 mt-0.5" />}
            <div>
              <p className="font-medium text-sm text-ink">
                3-Way Match: {matchResult?.match_result ?? (inv.match_status ?? "Not run")}
              </p>
              {(inv.dispute_reason || matchResult?.notes) && (
                <p className="text-xs text-ink-muted mt-1">
                  {inv.dispute_reason ?? matchResult?.notes}
                </p>
              )}
            </div>
          </div>
        </Card>
      )}

      {/* Invoice details */}
      <Card>
        <CardHeader title="Invoice Details" />
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 p-5">
          {[
            { label: "PO Reference", value: inv.po_id ? inv.po_id.slice(0, 12) + "…" : "—" },
            { label: "Vendor ID", value: inv.vendor_id.slice(0, 12) + "…" },
            { label: "Invoice Date", value: formatDate(inv.invoice_date) },
            { label: "Due Date", value: inv.due_date ? formatDate(inv.due_date) : "—" },
            { label: "Match Status", value: inv.match_status ?? "—" },
            { label: "Verified At", value: inv.verified_at ? formatDateTime(inv.verified_at) : "—" },
            { label: "Currency", value: inv.currency },
            { label: "Tax Amount", value: formatCurrency(parseFloat(inv.tax_amount), inv.currency) },
          ].map(({ label, value }) => (
            <div key={label}>
              <p className="text-2xs text-ink-muted uppercase tracking-widest">{label}</p>
              <p className="mt-0.5 text-sm text-ink">{value}</p>
            </div>
          ))}
        </div>
      </Card>

      {/* Line items */}
      <Card>
        <CardHeader title="Invoice Lines" subtitle={`${inv.items.length} items`} />
        <table className="w-full">
          <thead>
            <tr className="border-b border-surface-border">
              <th className="th text-left w-8">#</th>
              <th className="th text-left">Description</th>
              <th className="th text-right">Qty</th>
              <th className="th text-right">Unit Price</th>
              <th className="th text-right">Net Value</th>
              <th className="th text-left">Match</th>
              <th className="th text-right">Variance%</th>
            </tr>
          </thead>
          <tbody>
            {inv.items.map((item) => (
              <tr key={item.id} className="border-b border-surface-border last:border-0">
                <td className="td text-ink-muted text-xs">{item.line_number}</td>
                <td className="td text-ink">{item.description ?? "—"}</td>
                <td className="td text-right tabular">{item.quantity}</td>
                <td className="td text-right tabular text-ink-muted">
                  {formatCurrency(parseFloat(item.unit_price), inv.currency)}
                </td>
                <td className="td text-right tabular font-medium">
                  {formatCurrency(parseFloat(item.net_value), inv.currency)}
                </td>
                <td className="td">
                  {item.match_flag ? (
                    <span className={`text-2xs font-semibold uppercase ${matchFlagColor(item.match_flag)}`}>
                      {item.match_flag.replace(/_/g, " ")}
                    </span>
                  ) : <span className="text-ink-subtle text-2xs">—</span>}
                </td>
                <td className="td text-right tabular text-xs">
                  {item.variance_pct ? `${parseFloat(item.variance_pct).toFixed(2)}%` : "—"}
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="border-t-2 border-surface-border bg-surface">
              <td colSpan={4} className="td text-right font-semibold text-ink">Total</td>
              <td className="td text-right tabular font-bold text-ink">
                {formatCurrency(total, inv.currency)}
              </td>
              <td colSpan={2} />
            </tr>
          </tfoot>
        </table>
      </Card>

      {/* Override modal */}
      {showOverrideModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-lg shadow-xl p-6 w-full max-w-md mx-4">
            <h3 className="font-semibold text-ink mb-1">Finance Override</h3>
            <p className="text-sm text-ink-muted mb-4">
              Overriding a disputed invoice bypasses the match failure. Requires finance manager authority.
            </p>
            <textarea
              value={overrideReason}
              onChange={(e) => setOverrideReason(e.target.value)}
              placeholder="Business justification for override (min 10 chars)…"
              rows={3}
              className="w-full border border-surface-border rounded px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
            <div className="flex gap-2 mt-4 justify-end">
              <Button variant="secondary" size="sm" onClick={() => setShowOverrideModal(false)}>Cancel</Button>
              <Button size="sm"
                disabled={overrideReason.trim().length < 10}
                loading={overrideMutation.isPending}
                onClick={() => overrideMutation.mutate()}>
                Approve Override
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Payment modal */}
      {showPayModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-lg shadow-xl p-6 w-full max-w-sm mx-4">
            <h3 className="font-semibold text-ink mb-1">Record Payment</h3>
            <p className="text-sm text-ink-muted mb-4">
              Balance due: <strong>{formatCurrency(balance, inv.currency)}</strong>
            </p>
            <input
              type="number"
              step="0.01"
              min="0.01"
              max={balance}
              value={payAmount}
              onChange={(e) => setPayAmount(e.target.value)}
              placeholder={balance.toFixed(2)}
              className="w-full border border-surface-border rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
            <div className="flex gap-2 mt-4 justify-end">
              <Button variant="secondary" size="sm" onClick={() => setShowPayModal(false)}>Cancel</Button>
              <Button size="sm"
                disabled={!payAmount || parseFloat(payAmount) <= 0}
                loading={payMutation.isPending}
                onClick={() => payMutation.mutate()}>
                Record Payment
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
