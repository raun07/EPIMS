import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useQuery, useMutation } from "@tanstack/react-query";
import { useForm, useFieldArray } from "react-hook-form";
import { ArrowLeft, Plus, Trash2, CheckSquare } from "lucide-react";
import { poApi, grnApi } from "@/api/procurement";
import { formatCurrency } from "@/lib/utils";
import { Button, Card, CardHeader, Input } from "@/components/ui";

interface GRNLineForm {
  po_item_id: string;
  quantity_delivered: string;
  quantity_accepted: string;
  batch_number: string;
  inspection_note: string;
  rejection_reason: string;
}

interface GRNForm {
  po_id: string;
  warehouse_id: string;
  receipt_date: string;
  delivery_note: string;
  vehicle_number: string;
  driver_name: string;
  notes: string;
  items: GRNLineForm[];
}

export default function GRNCreatePage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const poId = searchParams.get("po_id") ?? "";
  const [postAfterCreate, setPostAfterCreate] = useState(true);

  const { data: po } = useQuery({
    queryKey: ["po", poId],
    queryFn: () => poApi.get(poId),
    enabled: !!poId,
  });

  const { register, handleSubmit, control, watch, setValue, formState: { errors } } =
    useForm<GRNForm>({
      defaultValues: {
        po_id: poId,
        warehouse_id: "",
        receipt_date: new Date().toISOString().slice(0, 10),
        delivery_note: "",
        vehicle_number: "",
        driver_name: "",
        notes: "",
        items: po?.items.map((item) => ({
          po_item_id: item.id,
          quantity_delivered: item.quantity,
          quantity_accepted: item.quantity,
          batch_number: "",
          inspection_note: "",
          rejection_reason: "",
        })) ?? [],
      },
    });

  // Pre-fill items once PO loads
  const { fields, replace } = useFieldArray({ control, name: "items" });

  // When PO data arrives, populate form lines
  if (po && fields.length === 0) {
    replace(
      po.items.map((item) => ({
        po_item_id: item.id,
        quantity_delivered: item.quantity,
        quantity_accepted: item.quantity,
        batch_number: "",
        inspection_note: "",
        rejection_reason: "",
      }))
    );
  }

  const createMutation = useMutation({
    mutationFn: async (data: GRNForm) => {
      const grn = await grnApi.create({
        po_id: data.po_id,
        warehouse_id: data.warehouse_id,
        receipt_date: data.receipt_date || undefined,
        delivery_note: data.delivery_note || undefined,
        vehicle_number: data.vehicle_number || undefined,
        driver_name: data.driver_name || undefined,
        notes: data.notes || undefined,
        items: data.items.map((i) => ({
          po_item_id: i.po_item_id || undefined,
          quantity_delivered: parseFloat(i.quantity_delivered),
          quantity_accepted: parseFloat(i.quantity_accepted),
          batch_number: i.batch_number || undefined,
          inspection_note: i.inspection_note || undefined,
          rejection_reason: i.rejection_reason || undefined,
        })),
      });

      if (postAfterCreate) {
        await grnApi.post(grn.id);
      }
      return grn;
    },
    onSuccess: (grn) => navigate(`/procurement/grn/${grn.id}`),
  });

  const watchedItems = watch("items");

  return (
    <div className="max-w-4xl space-y-4">
      <div className="flex items-center gap-3">
        <button onClick={() => navigate(-1)} className="text-ink-muted hover:text-ink">
          <ArrowLeft className="h-5 w-5" />
        </button>
        <div>
          <h1 className="text-xl font-semibold text-ink">Record Goods Receipt</h1>
          {po && (
            <p className="text-sm text-ink-muted mt-0.5">
              Against PO <span className="font-mono text-brand-500">{po.po_number}</span>
            </p>
          )}
        </div>
      </div>

      <form onSubmit={handleSubmit((d) => createMutation.mutate(d))} className="space-y-4">
        {/* Header */}
        <Card>
          <CardHeader title="Receipt Details" />
          <div className="p-5 grid grid-cols-2 gap-4">
            <Input
              label="Receipt Date"
              type="date"
              {...register("receipt_date")}
            />
            <Input
              label="Warehouse ID *"
              placeholder="warehouse UUID"
              error={errors.warehouse_id?.message}
              {...register("warehouse_id", { required: "Warehouse is required" })}
            />
            <Input label="Delivery Note / DO Number" placeholder="DN-12345" {...register("delivery_note")} />
            <Input label="Vehicle Number" placeholder="MH-01-AB-1234" {...register("vehicle_number")} />
            <Input label="Driver Name" placeholder="Driver's name" {...register("driver_name")} />
            <Input label="Notes" placeholder="Any additional notes" {...register("notes")} />
          </div>
        </Card>

        {/* Line items */}
        <Card>
          <CardHeader
            title="Received Items"
            subtitle={`${fields.length} lines from PO`}
          />
          {fields.length === 0 ? (
            <div className="p-8 text-center text-sm text-ink-muted">
              {poId ? "Loading PO lines…" : "No PO selected. Add a PO ID above."}
            </div>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="border-b border-surface-border">
                  <th className="th text-left">Description</th>
                  <th className="th text-right">Ordered</th>
                  <th className="th text-right">Delivered</th>
                  <th className="th text-right">Accepted</th>
                  <th className="th text-left">Batch</th>
                  <th className="th text-left">Note</th>
                </tr>
              </thead>
              <tbody>
                {fields.map((field, idx) => {
                  const poItem = po?.items.find((i) => i.id === field.po_item_id);
                  const delivered = parseFloat(watchedItems[idx]?.quantity_delivered ?? "0");
                  const accepted = parseFloat(watchedItems[idx]?.quantity_accepted ?? "0");
                  const rejected = Math.max(0, delivered - accepted);
                  return (
                    <tr key={field.id} className="border-b border-surface-border last:border-0 align-top">
                      <td className="td">
                        <div className="text-sm text-ink">{poItem?.description ?? "—"}</div>
                        {rejected > 0 && (
                          <div className="text-2xs text-red-500 mt-0.5">
                            {rejected.toFixed(3)} rejected
                          </div>
                        )}
                      </td>
                      <td className="td text-right tabular text-ink-muted pt-4">
                        {poItem?.quantity}
                      </td>
                      <td className="td pt-2">
                        <input
                          type="number"
                          step="0.001"
                          min="0"
                          className="w-24 text-right h-8 rounded border border-surface-border px-2 text-sm tabular focus:outline-none focus:ring-2 focus:ring-brand-500"
                          {...register(`items.${idx}.quantity_delivered`)}
                        />
                      </td>
                      <td className="td pt-2">
                        <input
                          type="number"
                          step="0.001"
                          min="0"
                          className="w-24 text-right h-8 rounded border border-surface-border px-2 text-sm tabular focus:outline-none focus:ring-2 focus:ring-brand-500"
                          {...register(`items.${idx}.quantity_accepted`)}
                        />
                      </td>
                      <td className="td pt-2">
                        <input
                          className="w-28 h-8 rounded border border-surface-border px-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                          placeholder="BATCH-01"
                          {...register(`items.${idx}.batch_number`)}
                        />
                      </td>
                      <td className="td pt-2">
                        <input
                          className="w-36 h-8 rounded border border-surface-border px-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                          placeholder="Inspection note"
                          {...register(`items.${idx}.inspection_note`)}
                        />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </Card>

        {/* Post toggle + submit */}
        <div className="flex items-center justify-between bg-white rounded-lg border border-surface-border px-5 py-4 shadow-card">
          <label className="flex items-center gap-2.5 cursor-pointer">
            <input
              type="checkbox"
              checked={postAfterCreate}
              onChange={(e) => setPostAfterCreate(e.target.checked)}
              className="w-4 h-4 rounded accent-brand-500"
            />
            <div>
              <span className="text-sm font-medium text-ink">Post immediately</span>
              <p className="text-xs text-ink-muted">
                Posting updates stock and creates movement documents
              </p>
            </div>
          </label>
          <div className="flex gap-3">
            <Button variant="secondary" type="button" onClick={() => navigate(-1)}>
              Discard
            </Button>
            <Button type="submit" loading={createMutation.isPending}>
              <CheckSquare className="h-4 w-4" />
              {postAfterCreate ? "Save & Post" : "Save Draft"}
            </Button>
          </div>
        </div>

        {createMutation.isError && (
          <p className="text-sm text-red-500 bg-red-50 rounded px-4 py-2">
            {(createMutation.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Failed to create GRN"}
          </p>
        )}
      </form>
    </div>
  );
}
