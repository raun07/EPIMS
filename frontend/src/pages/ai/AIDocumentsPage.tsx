import { useState, useCallback } from "react";
import { useMutation } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { FileText, Upload, CheckCircle, AlertTriangle, Link2, Loader2 } from "lucide-react";
import { aiApi } from "@/api/ai";
import { formatCurrency, formatDate } from "@/lib/utils";
import { Button, Card, CardHeader } from "@/components/ui";

export default function AIDocumentsPage() {
  const navigate = useNavigate();
  const [dragOver, setDragOver] = useState(false);
  const [result, setResult] = useState<any>(null);

  const extractMutation = useMutation({
    mutationFn: (file: File) => aiApi.documentExtract(file),
    onSuccess: (data) => setResult(data),
  });

  const handleFile = useCallback((file: File) => {
    if (!file.type.includes("pdf") && !file.type.includes("image")) {
      alert("Only PDF and image files are supported");
      return;
    }
    setResult(null);
    extractMutation.mutate(file);
  }, []);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  };

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
  };

  const confidence = result?.confidence_score ?? 0;
  const confColor = confidence >= 0.8 ? "text-emerald-600" : confidence >= 0.6 ? "text-amber-500" : "text-red-500";
  const confLabel = confidence >= 0.8 ? "High" : confidence >= 0.6 ? "Medium" : "Low";

  return (
    <div className="max-w-4xl space-y-6">
      <div className="flex items-center gap-3">
        <div className="h-9 w-9 rounded-lg bg-brand-500 flex items-center justify-center">
          <FileText className="h-5 w-5 text-white" />
        </div>
        <div>
          <h1 className="text-xl font-semibold text-ink">Document Intelligence</h1>
          <p className="text-sm text-ink-muted">Upload PDF invoices — AI extracts structured data automatically</p>
        </div>
      </div>

      {/* Upload zone */}
      <Card
        className={`border-2 border-dashed transition-colors ${
          dragOver ? "border-brand-400 bg-brand-50" : "border-surface-border"
        }`}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
      >
        <div className="p-10 text-center">
          {extractMutation.isPending ? (
            <div className="flex flex-col items-center gap-3">
              <Loader2 className="h-10 w-10 text-brand-400 animate-spin" />
              <p className="text-sm font-medium text-ink">Extracting invoice data…</p>
              <p className="text-xs text-ink-muted">Claude is reading your document</p>
            </div>
          ) : (
            <>
              <Upload className="h-10 w-10 text-ink-subtle mx-auto mb-3" />
              <p className="text-sm font-medium text-ink mb-1">
                Drop a PDF invoice here or click to upload
              </p>
              <p className="text-xs text-ink-muted mb-4">
                Supports GST invoices, tax bills, pro-forma invoices · Max 10MB
              </p>
              <label className="cursor-pointer">
                <input type="file" accept=".pdf,image/*" onChange={handleFileInput} className="hidden" />
                <span className="inline-flex items-center gap-2 px-4 py-2 rounded bg-brand-500 text-white text-sm font-medium hover:bg-brand-600 transition-colors">
                  <Upload className="h-4 w-4" /> Choose File
                </span>
              </label>
            </>
          )}
        </div>
      </Card>

      {/* Extraction result */}
      {result && !result.error && (
        <div className="space-y-4">
          {/* Confidence header */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              {confidence >= 0.7
                ? <CheckCircle className="h-5 w-5 text-emerald-500" />
                : <AlertTriangle className="h-5 w-5 text-amber-500" />}
              <div>
                <p className="text-sm font-medium text-ink">
                  Extraction complete · {confLabel} confidence
                </p>
                <p className="text-xs text-ink-muted">
                  {result.latency_ms}ms · {result.model_used}
                </p>
              </div>
            </div>
            <span className={`text-2xl font-bold tabular ${confColor}`}>
              {Math.round(confidence * 100)}%
            </span>
          </div>

          {/* Core fields */}
          <Card>
            <CardHeader title="Extracted Invoice Fields" />
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4 p-5">
              {[
                { label: "Invoice Number", value: result.invoice_number },
                { label: "Vendor Name", value: result.vendor_name },
                { label: "GST Number", value: result.vendor_gstin },
                { label: "PO Reference", value: result.po_number },
                { label: "Invoice Date", value: result.invoice_date },
                { label: "Due Date", value: result.due_date },
                { label: "Currency", value: result.currency },
                { label: "Payment Terms", value: result.payment_terms },
                { label: "Total Amount", value: result.total_amount ? formatCurrency(result.total_amount) : null, bold: true },
              ].map(({ label, value, bold }) => (
                <div key={label}>
                  <p className="text-2xs text-ink-muted uppercase tracking-widest">{label}</p>
                  <p className={`mt-0.5 text-sm ${bold ? "font-bold text-ink" : "text-ink"} ${!value ? "text-ink-subtle italic" : ""}`}>
                    {value ?? "Not found"}
                  </p>
                </div>
              ))}
            </div>
          </Card>

          {/* Vendor match */}
          {result.vendor_match && (
            <div className="flex items-center gap-3 bg-emerald-50 border border-emerald-200 rounded-lg px-4 py-3">
              <CheckCircle className="h-4 w-4 text-emerald-500 flex-shrink-0" />
              <div className="flex-1">
                <p className="text-sm text-emerald-700 font-medium">
                  Vendor matched: <strong>{result.vendor_match.name}</strong>
                </p>
                <p className="text-xs text-emerald-600">{result.vendor_match.vendor_number}</p>
              </div>
            </div>
          )}

          {/* PO match */}
          {result.po_match && (
            <div className="flex items-center gap-3 bg-brand-50 border border-brand-200 rounded-lg px-4 py-3">
              <Link2 className="h-4 w-4 text-brand-500 flex-shrink-0" />
              <div className="flex-1">
                <p className="text-sm text-brand-700 font-medium">
                  PO matched: <strong>{result.po_match.po_number}</strong> ·{" "}
                  {formatCurrency(result.po_match.total_amount)}
                </p>
              </div>
              <button
                onClick={() => navigate(`/procurement/po/${result.po_match.id}`)}
                className="text-brand-500 text-xs hover:underline"
              >
                View PO →
              </button>
            </div>
          )}

          {/* Line items */}
          {result.line_items?.length > 0 && (
            <Card>
              <CardHeader title={`Line Items (${result.line_items.length})`} />
              <table className="w-full">
                <thead>
                  <tr className="border-b border-surface-border">
                    <th className="px-4 py-2 text-left text-2xs font-semibold text-ink-muted uppercase">#</th>
                    <th className="px-4 py-2 text-left text-2xs font-semibold text-ink-muted uppercase">Description</th>
                    <th className="px-4 py-2 text-right text-2xs font-semibold text-ink-muted uppercase">Qty</th>
                    <th className="px-4 py-2 text-right text-2xs font-semibold text-ink-muted uppercase">Unit Price</th>
                    <th className="px-4 py-2 text-right text-2xs font-semibold text-ink-muted uppercase">Amount</th>
                  </tr>
                </thead>
                <tbody>
                  {result.line_items.map((item: any, i: number) => (
                    <tr key={i} className="border-b border-surface-border last:border-0">
                      <td className="px-4 py-2 text-ink-muted text-xs">{item.line_number ?? i + 1}</td>
                      <td className="px-4 py-2 text-sm text-ink">{item.description}</td>
                      <td className="px-4 py-2 text-right tabular text-ink-muted text-sm">
                        {item.quantity} {item.unit}
                      </td>
                      <td className="px-4 py-2 text-right tabular text-ink-muted text-sm">
                        {item.unit_price ? formatCurrency(item.unit_price) : "—"}
                      </td>
                      <td className="px-4 py-2 text-right tabular font-medium text-ink text-sm">
                        {item.amount ? formatCurrency(item.amount) : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  {result.tax_total && (
                    <tr className="bg-surface">
                      <td colSpan={4} className="px-4 py-2 text-right text-ink-muted text-sm">Tax</td>
                      <td className="px-4 py-2 text-right tabular text-ink text-sm">
                        {formatCurrency(result.tax_total)}
                      </td>
                    </tr>
                  )}
                  <tr className="bg-surface border-t-2 border-surface-border">
                    <td colSpan={4} className="px-4 py-2 text-right font-semibold text-ink">Total</td>
                    <td className="px-4 py-2 text-right tabular font-bold text-ink">
                      {result.total_amount ? formatCurrency(result.total_amount) : "—"}
                    </td>
                  </tr>
                </tfoot>
              </table>
            </Card>
          )}

          {/* Extraction notes */}
          {result.extraction_notes?.length > 0 && (
            <div className="bg-amber-50 border border-amber-200 rounded-lg px-4 py-3">
              <p className="text-xs font-semibold text-amber-600 uppercase tracking-widest mb-1">
                AI Notes
              </p>
              <ul className="space-y-0.5">
                {result.extraction_notes.map((note: string, i: number) => (
                  <li key={i} className="text-xs text-amber-700">• {note}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Create invoice action */}
          {result.ready_to_create && (
            <div className="flex items-center justify-between bg-emerald-50 border border-emerald-200 rounded-lg px-4 py-3">
              <p className="text-sm text-emerald-700">
                Ready to create invoice with extracted data
              </p>
              <Button size="sm" onClick={() => navigate("/invoices/new")}>
                Create Invoice
              </Button>
            </div>
          )}
        </div>
      )}

      {/* Error state */}
      {result?.error && (
        <div className="flex items-start gap-3 bg-red-50 border border-red-200 rounded-lg p-4">
          <AlertTriangle className="h-5 w-5 text-red-500 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-red-700">Extraction Failed</p>
            <p className="text-xs text-red-500 mt-1">{result.error}</p>
          </div>
        </div>
      )}
    </div>
  );
}
