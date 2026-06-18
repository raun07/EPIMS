import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Warehouse as WarehouseIcon, X } from "lucide-react";
import api from "@/lib/api";
import { Button, Card, EmptyState, TableSkeleton } from "@/components/ui";

export default function WarehousesPage() {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ code: "", name: "", warehouse_type: "STANDARD", address: "" });

  const { data, isLoading } = useQuery({
    queryKey: ["warehouses"],
    queryFn: () => api.get("/warehouses").then(r => r.data),
  });

  const createMutation = useMutation({
    mutationFn: (data: typeof form) =>
      api.post(`/warehouses?code=${encodeURIComponent(data.code)}&name=${encodeURIComponent(data.name)}&warehouse_type=${data.warehouse_type}${data.address ? `&address=${encodeURIComponent(data.address)}` : ""}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["warehouses"] });
      setShowForm(false);
      setForm({ code: "", name: "", warehouse_type: "STANDARD", address: "" });
    },
  });

  const warehouses = data?.data ?? [];

  return (
    <div className="max-w-5xl space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-ink">Warehouses</h1>
          <p className="text-sm text-ink-muted mt-0.5">
            {data?.meta ? `${data.meta.total} warehouses` : "Loading…"}
          </p>
        </div>
        <Button onClick={() => setShowForm(true)}>
          <Plus className="h-4 w-4" /> New Warehouse
        </Button>
      </div>

      {showForm && (
        <Card className="p-5 relative">
          <button onClick={() => setShowForm(false)}
            className="absolute top-4 right-4 text-ink-subtle hover:text-ink">
            <X className="h-4 w-4" />
          </button>
          <h2 className="font-semibold text-ink text-sm mb-4">New Warehouse</h2>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1">
              <label className="text-xs font-medium text-ink-muted uppercase">Code *</label>
              <input
                className="w-full h-9 rounded border border-surface-border px-3 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                placeholder="e.g. WH-DEL"
                value={form.code}
                onChange={e => setForm(f => ({ ...f, code: e.target.value.toUpperCase() }))}
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-ink-muted uppercase">Name *</label>
              <input
                className="w-full h-9 rounded border border-surface-border px-3 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                placeholder="e.g. Delhi Distribution Center"
                value={form.name}
                onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-ink-muted uppercase">Type</label>
              <select
                className="w-full h-9 rounded border border-surface-border px-3 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                value={form.warehouse_type}
                onChange={e => setForm(f => ({ ...f, warehouse_type: e.target.value }))}
              >
                <option value="STANDARD">Standard</option>
                <option value="COLD_STORAGE">Cold Storage</option>
                <option value="HAZMAT">Hazmat</option>
                <option value="TRANSIT">Transit Hub</option>
              </select>
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-ink-muted uppercase">Address</label>
              <input
                className="w-full h-9 rounded border border-surface-border px-3 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                placeholder="Optional"
                value={form.address}
                onChange={e => setForm(f => ({ ...f, address: e.target.value }))}
              />
            </div>
          </div>
          <div className="flex justify-end gap-2 mt-4">
            <Button variant="secondary" onClick={() => setShowForm(false)}>Cancel</Button>
            <Button
              loading={createMutation.isPending}
              disabled={!form.code || !form.name}
              onClick={() => createMutation.mutate(form)}
            >
              Create Warehouse
            </Button>
          </div>
        </Card>
      )}

      {isLoading ? (
        <TableSkeleton rows={4} cols={4} />
      ) : warehouses.length === 0 ? (
        <EmptyState
          icon={<WarehouseIcon className="h-10 w-10" />}
          title="No warehouses yet"
          description="Create your first warehouse to start managing inventory locations"
        />
      ) : (
        <div className="grid grid-cols-2 gap-4">
          {warehouses.map((w: any) => (
            <Card key={w.id} className="p-4">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-2xs text-ink-muted uppercase tracking-widest">{w.code}</p>
                  <h3 className="font-semibold text-ink mt-0.5">{w.name}</h3>
                </div>
                <span className={`text-2xs px-2 py-0.5 rounded ${w.is_active ? "bg-emerald-50 text-emerald-600" : "bg-surface text-ink-muted"}`}>
                  {w.is_active ? "Active" : "Inactive"}
                </span>
              </div>
              <div className="mt-3 flex items-center gap-4 text-xs text-ink-muted">
                <span>{w.warehouse_type.replace(/_/g, " ")}</span>
                <span>·</span>
                <span>{w.storage_location_count} storage location{w.storage_location_count !== 1 ? "s" : ""}</span>
              </div>
              {w.address && <p className="text-xs text-ink-muted mt-2">{w.address}</p>}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
