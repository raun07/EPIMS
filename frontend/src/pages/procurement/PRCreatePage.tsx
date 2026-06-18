import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Plus, Trash2, ArrowLeft, Save } from "lucide-react";
import api from "@/lib/api";
import { Button, Card } from "@/components/ui";

interface LineItem {
  id: string;
  description: string;
  quantity: number;
  estimated_price: number;
  material_id: string;
}

const DEPARTMENTS = ["Engineering", "IT", "Finance", "Admin", "HR", "Operations", "Procurement", "Sales", "Marketing"];
const PRIORITIES = ["LOW", "NORMAL", "HIGH", "URGENT"];

export default function PRCreatePage() {
  const navigate = useNavigate();

  const [form, setForm] = useState({
    title: "",
    description: "",
    department: "",
    priority: "NORMAL",
    cost_center: "",
    required_date: "",
    notes: "",
  });

  const [items, setItems] = useState<LineItem[]>([
    { id: crypto.randomUUID(), description: "", quantity: 1, estimated_price: 0, material_id: "" }
  ]);

  // Load materials for dropdown
  const { data: materialsData } = useQuery({
    queryKey: ["materials-list"],
    queryFn: () => api.get("/materials?page=1&per_page=100").then(r => r.data),
  });
  const materials = materialsData?.data ?? [];

  const createMutation = useMutation({
    mutationFn: (data: any) => api.post("/purchase-requisitions", data).then(r => r.data),
    onSuccess: (data) => {
      navigate(`/procurement/pr/${data.id}`);
    },
  });

  const addItem = () => {
    setItems(prev => [...prev, {
      id: crypto.randomUUID(),
      description: "",
      quantity: 1,
      estimated_price: 0,
      material_id: ""
    }]);
  };

  const removeItem = (id: string) => {
    if (items.length === 1) return;
    setItems(prev => prev.filter(i => i.id !== id));
  };

  const updateItem = (id: string, field: keyof LineItem, value: any) => {
    setItems(prev => prev.map(i => i.id === id ? { ...i, [field]: value } : i));
  };

  const handleMaterialSelect = (itemId: string, materialId: string) => {
    const mat = materials.find((m: any) => m.id === materialId);
    if (mat) {
      setItems(prev => prev.map(i => i.id === itemId ? {
        ...i,
        material_id: materialId,
        description: mat.description || mat.name || "",
        estimated_price: parseFloat(mat.standard_price) || 0,
      } : i));
    } else {
      updateItem(itemId, "material_id", materialId);
    }
  };

  const totalValue = items.reduce((sum, i) => sum + (i.quantity * i.estimated_price), 0);

  const handleSubmit = (asDraft = true) => {
    if (!form.title.trim()) { alert("Title is required"); return; }
    if (items.some(i => !i.description.trim())) { alert("All line items need a description"); return; }

    createMutation.mutate({
      ...form,
      status: asDraft ? "DRAFT" : "SUBMITTED",
      items: items.map((i, idx) => ({
        line_number: idx + 1,
        description: i.description,
        quantity: Number(i.quantity),
        estimated_price: Number(i.estimated_price),
        material_id: i.material_id || null,
        currency: "INR",
      })),
    });
  };

  return (
    <div className="max-w-4xl space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <button onClick={() => navigate("/procurement/pr")}
          className="h-8 w-8 flex items-center justify-center rounded hover:bg-surface-hover text-ink-muted">
          <ArrowLeft className="h-4 w-4" />
        </button>
        <div>
          <h1 className="text-xl font-semibold text-ink">New Purchase Requisition</h1>
          <p className="text-sm text-ink-muted">Create a purchase request for approval</p>
        </div>
      </div>

      {/* Header fields */}
      <Card className="p-5 space-y-4">
        <h2 className="font-semibold text-ink text-sm">Requisition Header</h2>

        <div className="space-y-1">
          <label className="text-xs font-medium text-ink-muted uppercase tracking-wide">Title *</label>
          <input
            className="w-full h-9 rounded border border-surface-border px-3 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            placeholder="e.g. 25 Dell Laptops for Engineering Team"
            value={form.title}
            onChange={e => setForm(f => ({ ...f, title: e.target.value }))}
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-1">
            <label className="text-xs font-medium text-ink-muted uppercase tracking-wide">Department</label>
            <select
              className="w-full h-9 rounded border border-surface-border px-3 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              value={form.department}
              onChange={e => setForm(f => ({ ...f, department: e.target.value }))}
            >
              <option value="">Select department</option>
              {DEPARTMENTS.map(d => <option key={d} value={d}>{d}</option>)}
            </select>
          </div>

          <div className="space-y-1">
            <label className="text-xs font-medium text-ink-muted uppercase tracking-wide">Priority</label>
            <select
              className="w-full h-9 rounded border border-surface-border px-3 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              value={form.priority}
              onChange={e => setForm(f => ({ ...f, priority: e.target.value }))}
            >
              {PRIORITIES.map(p => <option key={p} value={p}>{p}</option>)}
            </select>
          </div>

          <div className="space-y-1">
            <label className="text-xs font-medium text-ink-muted uppercase tracking-wide">Cost Centre</label>
            <input
              className="w-full h-9 rounded border border-surface-border px-3 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              placeholder="e.g. CC001"
              value={form.cost_center}
              onChange={e => setForm(f => ({ ...f, cost_center: e.target.value }))}
            />
          </div>

          <div className="space-y-1">
            <label className="text-xs font-medium text-ink-muted uppercase tracking-wide">Required By</label>
            <input
              type="date"
              className="w-full h-9 rounded border border-surface-border px-3 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              value={form.required_date}
              onChange={e => setForm(f => ({ ...f, required_date: e.target.value }))}
            />
          </div>
        </div>

        <div className="space-y-1">
          <label className="text-xs font-medium text-ink-muted uppercase tracking-wide">Business Justification</label>
          <textarea
            rows={2}
            className="w-full rounded border border-surface-border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none"
            placeholder="Why is this purchase needed?"
            value={form.description}
            onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
          />
        </div>

        <div className="space-y-1">
          <label className="text-xs font-medium text-ink-muted uppercase tracking-wide">Notes</label>
          <input
            className="w-full h-9 rounded border border-surface-border px-3 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            placeholder="Additional notes for approver"
            value={form.notes}
            onChange={e => setForm(f => ({ ...f, notes: e.target.value }))}
          />
        </div>
      </Card>

      {/* Line Items */}
      <Card className="overflow-hidden">
        <div className="flex items-center justify-between px-5 py-3 border-b border-surface-border">
          <h2 className="font-semibold text-ink text-sm">Line Items</h2>
          <Button size="sm" variant="secondary" onClick={addItem}>
            <Plus className="h-3.5 w-3.5" /> Add Item
          </Button>
        </div>

        <table className="w-full">
          <thead>
            <tr className="border-b border-surface-border bg-surface">
              <th className="px-4 py-2 text-left text-2xs font-semibold text-ink-muted uppercase w-6">#</th>
              <th className="px-4 py-2 text-left text-2xs font-semibold text-ink-muted uppercase">Material</th>
              <th className="px-4 py-2 text-left text-2xs font-semibold text-ink-muted uppercase">Description *</th>
              <th className="px-4 py-2 text-right text-2xs font-semibold text-ink-muted uppercase w-24">Qty</th>
              <th className="px-4 py-2 text-right text-2xs font-semibold text-ink-muted uppercase w-32">Unit Price (₹)</th>
              <th className="px-4 py-2 text-right text-2xs font-semibold text-ink-muted uppercase w-32">Total (₹)</th>
              <th className="px-4 py-2 w-8"></th>
            </tr>
          </thead>
          <tbody>
            {items.map((item, idx) => (
              <tr key={item.id} className="border-b border-surface-border last:border-0">
                <td className="px-4 py-2 text-ink-muted text-xs">{idx + 1}</td>
                <td className="px-4 py-2">
                  <select
                    className="w-full h-8 rounded border border-surface-border px-2 text-xs focus:outline-none focus:ring-1 focus:ring-brand-500"
                    value={item.material_id}
                    onChange={e => handleMaterialSelect(item.id, e.target.value)}
                  >
                    <option value="">-- Select material --</option>
                    {materials.map((m: any) => (
                      <option key={m.id} value={m.id}>{m.material_number} — {m.description}</option>
                    ))}
                  </select>
                </td>
                <td className="px-4 py-2">
                  <input
                    className="w-full h-8 rounded border border-surface-border px-2 text-xs focus:outline-none focus:ring-1 focus:ring-brand-500"
                    placeholder="Item description"
                    value={item.description}
                    onChange={e => updateItem(item.id, "description", e.target.value)}
                  />
                </td>
                <td className="px-4 py-2">
                  <input
                    type="number"
                    min="1"
                    className="w-full h-8 rounded border border-surface-border px-2 text-xs text-right focus:outline-none focus:ring-1 focus:ring-brand-500"
                    value={item.quantity}
                    onChange={e => updateItem(item.id, "quantity", parseFloat(e.target.value) || 1)}
                  />
                </td>
                <td className="px-4 py-2">
                  <input
                    type="number"
                    min="0"
                    className="w-full h-8 rounded border border-surface-border px-2 text-xs text-right focus:outline-none focus:ring-1 focus:ring-brand-500"
                    value={item.estimated_price}
                    onChange={e => updateItem(item.id, "estimated_price", parseFloat(e.target.value) || 0)}
                  />
                </td>
                <td className="px-4 py-2 text-right text-xs font-medium text-ink tabular">
                  ₹{(item.quantity * item.estimated_price).toLocaleString("en-IN")}
                </td>
                <td className="px-4 py-2">
                  <button onClick={() => removeItem(item.id)}
                    className="h-6 w-6 flex items-center justify-center rounded hover:bg-red-50 text-ink-subtle hover:text-red-500">
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="border-t-2 border-surface-border bg-surface">
              <td colSpan={5} className="px-4 py-3 text-right font-semibold text-ink text-sm">Total Estimated Value</td>
              <td className="px-4 py-3 text-right font-bold text-ink tabular">
                ₹{totalValue.toLocaleString("en-IN")}
              </td>
              <td />
            </tr>
          </tfoot>
        </table>
      </Card>

      {/* Actions */}
      <div className="flex items-center justify-between">
        <button onClick={() => navigate("/procurement/pr")}
          className="text-sm text-ink-muted hover:text-ink">
          Cancel
        </button>
        <div className="flex gap-3">
          <Button variant="secondary" loading={createMutation.isPending}
            onClick={() => handleSubmit(true)}>
            <Save className="h-4 w-4" /> Save as Draft
          </Button>
          <Button loading={createMutation.isPending}
            onClick={() => handleSubmit(false)}>
            Submit for Approval
          </Button>
        </div>
      </div>

      {createMutation.isError && (
        <p className="text-sm text-red-500 text-right">
          Failed to create PR. Please check all fields and try again.
        </p>
      )}
    </div>
  );
}
