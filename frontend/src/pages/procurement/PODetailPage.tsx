import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Send, CheckCircle, X, Package, FileText } from "lucide-react";
import { poApi } from "@/api/procurement";
import { formatCurrency, formatDate, formatDateTime } from "@/lib/utils";
import { Button, Card, CardHeader, StatusBadge, Skeleton } from "@/components/ui";

export default function PODetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();

  const { data: po, isLoading } = useQuery({
    queryKey: ["po", id],
    queryFn: () => poApi.get(id!),
    enabled: !!id,
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["po", id] });
    qc.invalidateQueries({ queryKey: ["pos"] });
  };

  const submitMutation = useMutation({ mutationFn: () => poApi.submit(id!), onSuccess: invalidate });
  const releaseMutation = useMutation({ mutationFn: () => poApi.release(id!), onSuccess: invalidate });
  const cancelMutation = useMutation({ mutationFn: () => poApi.cancel(id!), onSuccess: invalidate });

  if (isLoading) return (
    <div className="max-w-4xl space-y-4">
      <Skeleton className="h-8 w-56" />
      <Skeleton className="h-64 rounded-lg" />
      <Skeleton className="h-40 rounded-lg" />
    </div>
  );

  if (!po) return <div className="text-ink-muted text-sm p-4">PO not found.</div>;

  const canSubmit = po.status === "DRAFT";
  const canRelease = po.status === "APPROVED";
  const canCancel = ["DRAFT", "APPROVED"].includes(po.status);

  const subtotal = parseFloat(po.subtotal);
  const tax = parseFloat(po.tax_amount);
  const discount = parseFloat(po.discount_amount);
  const total = parseFloat(po.total_amount);

  return (
    <div className="max-w-5xl space-y-4">
      {/* Header bar */}
      <div className="flex items-center gap-3">
        <button onClick={() => navigate("/procurement/po")} className="text-ink-muted hover:text-ink">
          <ArrowLeft className="h-5 w-5" />
        </button>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="text-lg font-semibold text-ink font-mono">{po.po_number}</h1>
            <StatusBadge status={po.status} />
          </div>
          <p className="text-xs text-ink-muted mt-0.5">
            {po.po_type} · {po.currency} · Created {formatDate(po.created_at)}
          </p>
        </div>
        <div className="flex gap-2">
          {canCancel && (
            <Button variant="secondary" size="sm" loading={cancelMutation.isPending}
              onClick={() => cancelMutation.mutate()}>
              <X className="h-3.5 w-3.5" /> Cancel
            </Button>
          )}
          {canSubmit && (
            <Button size="sm" loading={submitMutation.isPending}
              onClick={() => submitMutation.mutate()}>
              <Send className="h-3.5 w-3.5" /> Submit for approval
            </Button>
          )}
          {canRelease && (
            <Button size="sm" loading={releaseMutation.isPending}
              onClick={() => releaseMutation.mutate()}>
              <CheckCircle className="h-3.5 w-3.5" /> Release to vendor
            </Button>
          )}
        </div>
      </div>

      {/* Info grid */}
      <Card>
        <CardHeader title="Order Details" />
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 p-5">
          {[
            { label: "Vendor ID", value: po.vendor_id.slice(0, 12) + "…" },
            { label: "PR Reference", value: po.pr_id ? po.pr_id.slice(0, 12) + "…" : "—" },
            { label: "Order Date", value: formatDate(po.order_date) },
            { label: "Delivery Date", value: po.delivery_date ? formatDate(po.delivery_date) : "—" },
            { label: "Payment Terms", value: po.payment_terms ?? "—" },
            { label: "Order Type", value: po.po_type },
            { label: "Currency", value: po.currency },
            { label: "Total Value", value: formatCurrency(total, po.currency), bold: true },
          ].map(({ label, value, bold }) => (
            <div key={label}>
              <p className="text-2xs text-ink-muted uppercase tracking-widest">{label}</p>
              <p className={`mt-0.5 text-sm ${bold ? "font-bold text-ink" : "text-ink"}`}>{value}</p>
            </div>
          ))}
        </div>
        {po.notes && (
          <div className="px-5 pb-4 border-t border-surface-border pt-4">
            <p className="text-2xs text-ink-muted uppercase tracking-widest mb-1">Notes</p>
            <p className="text-sm text-ink">{po.notes}</p>
          </div>
        )}
      </Card>

      {/* Line items */}
      <Card>
        <CardHeader title="Line Items" subtitle={`${po.items.length} items`} />
        <table className="w-full">
          <thead>
            <tr className="border-b border-surface-border">
              <th className="th text-left w-8">#</th>
              <th className="th text-left">Description</th>
              <th className="th text-right">Qty</th>
              <th className="th text-right">Unit Price</th>
              <th className="th text-right">Disc%</th>
              <th className="th text-right">Tax%</th>
              <th className="th text-right">Net Value</th>
              <th className="th text-right">Received</th>
              <th className="th text-left">Status</th>
            </tr>
          </thead>
          <tbody>
            {po.items.map((item) => (
              <tr key={item.id} className="border-b border-surface-border last:border-0 hover:bg-surface-hover">
                <td className="td text-ink-muted text-xs">{item.line_number}</td>
                <td className="td text-ink">
                  <div>{item.description}</div>
                  {item.delivery_date && (
                    <div className="text-2xs text-ink-muted">Deliver by {formatDate(item.delivery_date)}</div>
                  )}
                </td>
                <td className="td text-right tabular">{item.quantity}</td>
                <td className="td text-right tabular text-ink-muted">
                  {formatCurrency(parseFloat(item.unit_price), po.currency)}
                </td>
                <td className="td text-right tabular text-ink-muted">{item.discount_pct}%</td>
                <td className="td text-right tabular text-ink-muted">{item.tax_pct}%</td>
                <td className="td text-right tabular font-medium">
                  {formatCurrency(parseFloat(item.net_value), po.currency)}
                </td>
                <td className="td text-right tabular">
                  <span className={parseFloat(item.qty_received) >= parseFloat(item.quantity)
                    ? "text-emerald-600 font-medium" : "text-ink-muted"}>
                    {item.qty_received} / {item.quantity}
                  </span>
                </td>
                <td className="td"><StatusBadge status={item.status} /></td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="border-t-2 border-surface-border bg-surface">
              <td colSpan={6} className="td text-right text-ink-muted">Subtotal</td>
              <td className="td text-right tabular">{formatCurrency(subtotal, po.currency)}</td>
              <td colSpan={2} />
            </tr>
            {discount > 0 && (
              <tr className="bg-surface">
                <td colSpan={6} className="td text-right text-ink-muted">Discount</td>
                <td className="td text-right tabular text-emerald-600">−{formatCurrency(discount, po.currency)}</td>
                <td colSpan={2} />
              </tr>
            )}
            {tax > 0 && (
              <tr className="bg-surface">
                <td colSpan={6} className="td text-right text-ink-muted">Tax</td>
                <td className="td text-right tabular">{formatCurrency(tax, po.currency)}</td>
                <td colSpan={2} />
              </tr>
            )}
            <tr className="bg-surface border-t border-surface-border">
              <td colSpan={6} className="td text-right font-semibold text-ink">Total</td>
              <td className="td text-right tabular font-bold text-ink text-base">
                {formatCurrency(total, po.currency)}
              </td>
              <td colSpan={2} />
            </tr>
          </tfoot>
        </table>
      </Card>

      {/* Quick actions */}
      <div className="flex gap-3">
        <Button variant="secondary" size="sm"
          onClick={() => navigate(`/procurement/grn/new?po_id=${po.id}`)}>
          <Package className="h-3.5 w-3.5" /> Record Receipt
        </Button>
        <Button variant="secondary" size="sm"
          onClick={() => navigate(`/invoices/new?po_id=${po.id}`)}>
          <FileText className="h-3.5 w-3.5" /> Create Invoice
        </Button>
      </div>
    </div>
  );
}
