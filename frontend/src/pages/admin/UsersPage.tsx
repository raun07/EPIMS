import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Users, Shield, UserCheck, UserX } from "lucide-react";
import api from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { Button, Card, CardHeader, EmptyState, TableSkeleton } from "@/components/ui";

async function fetchUsers() {
  const r = await api.get("/auth/users");
  return r.data as any[];
}

const ALL_ROLES = [
  "superuser", "procurement_manager", "buyer",
  "approver", "warehouse_manager", "accounts_payable", "viewer",
];

export default function UsersPage() {
  const qc = useQueryClient();
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showRolesModal, setShowRolesModal] = useState<{ userId: string; current: string[] } | null>(null);
  const [form, setForm] = useState({
    email: "", full_name: "", employee_id: "",
    password: "", department: "", role_names: [] as string[],
  });
  const [selectedRoles, setSelectedRoles] = useState<string[]>([]);

  const { data: users, isLoading } = useQuery({
    queryKey: ["users"],
    queryFn: fetchUsers,
  });

  const createMutation = useMutation({
    mutationFn: (data: typeof form) => api.post("/auth/users", data).then(r => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["users"] }); setShowCreateModal(false); },
  });

  const rolesMutation = useMutation({
    mutationFn: ({ userId, roles }: { userId: string; roles: string[] }) =>
      api.post(`/auth/users/${userId}/roles`, { role_names: roles }).then(r => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["users"] }); setShowRolesModal(null); },
  });

  const toggleActiveMutation = useMutation({
    mutationFn: ({ userId, active }: { userId: string; active: boolean }) =>
      api.put(`/auth/users/${userId}`, { is_active: active }).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["users"] }),
  });

  return (
    <div className="max-w-6xl space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-ink">User Management</h1>
          <p className="text-sm text-ink-muted mt-0.5">
            {users ? `${users.length} users registered` : "Loading…"}
          </p>
        </div>
        <Button onClick={() => setShowCreateModal(true)}>
          <Plus className="h-4 w-4" /> Add User
        </Button>
      </div>

      <Card>
        <CardHeader title="All Users" />
        {isLoading ? (
          <TableSkeleton rows={6} cols={7} />
        ) : !users || users.length === 0 ? (
          <EmptyState icon={<Users className="h-10 w-10" />} title="No users yet" />
        ) : (
          <table className="w-full">
            <thead>
              <tr className="border-b border-surface-border">
                <th className="th text-left">Name</th>
                <th className="th text-left">Email</th>
                <th className="th text-left">Employee ID</th>
                <th className="th text-left">Department</th>
                <th className="th text-left">Roles</th>
                <th className="th text-left">Status</th>
                <th className="th text-center">Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user: any) => (
                <tr key={user.id} className={`border-b border-surface-border last:border-0 ${!user.is_active ? "opacity-50" : ""}`}>
                  <td className="td">
                    <div className="flex items-center gap-2">
                      <div className="h-7 w-7 rounded-full bg-brand-100 text-brand-600 flex items-center justify-center text-xs font-semibold flex-shrink-0">
                        {user.full_name?.[0] ?? "?"}
                      </div>
                      <div>
                        <div className="text-sm font-medium text-ink">{user.full_name}</div>
                        {user.is_superuser && (
                          <div className="text-2xs text-amber-500 font-medium">Superuser</div>
                        )}
                      </div>
                    </div>
                  </td>
                  <td className="td text-ink-muted text-sm">{user.email}</td>
                  <td className="td font-mono text-xs text-ink-muted">{user.employee_id}</td>
                  <td className="td text-ink-muted text-sm">{user.department ?? "—"}</td>
                  <td className="td">
                    <div className="flex flex-wrap gap-1">
                      {(user.roles ?? []).map((r: string) => (
                        <span key={r} className="badge badge-released text-2xs">{r}</span>
                      ))}
                    </div>
                  </td>
                  <td className="td">
                    <span className={`badge ${user.is_active ? "badge-approved" : "badge-cancelled"}`}>
                      {user.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td className="td">
                    <div className="flex items-center justify-center gap-2">
                      <button
                        title="Edit roles"
                        onClick={() => { setShowRolesModal({ userId: user.id, current: user.roles ?? [] }); setSelectedRoles(user.roles ?? []); }}
                        className="h-7 w-7 flex items-center justify-center rounded hover:bg-brand-50 text-brand-400 hover:text-brand-600"
                      >
                        <Shield className="h-3.5 w-3.5" />
                      </button>
                      <button
                        title={user.is_active ? "Deactivate" : "Activate"}
                        onClick={() => toggleActiveMutation.mutate({ userId: user.id, active: !user.is_active })}
                        className={`h-7 w-7 flex items-center justify-center rounded ${user.is_active
                          ? "hover:bg-red-50 text-red-400 hover:text-red-500"
                          : "hover:bg-emerald-50 text-emerald-400 hover:text-emerald-500"}`}
                      >
                        {user.is_active ? <UserX className="h-3.5 w-3.5" /> : <UserCheck className="h-3.5 w-3.5" />}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      {/* Create user modal */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-lg shadow-xl p-6 w-full max-w-md mx-4 max-h-[90vh] overflow-y-auto">
            <h3 className="font-semibold text-ink mb-4">Add New User</h3>
            <div className="space-y-3">
              {[
                { label: "Full Name", key: "full_name", type: "text" },
                { label: "Email", key: "email", type: "email" },
                { label: "Employee ID", key: "employee_id", type: "text" },
                { label: "Password", key: "password", type: "password" },
                { label: "Department", key: "department", type: "text" },
              ].map(({ label, key, type }) => (
                <div key={key} className="flex flex-col gap-1">
                  <label className="text-xs font-medium text-ink-muted">{label}</label>
                  <input
                    type={type}
                    value={(form as any)[key]}
                    onChange={(e) => setForm(f => ({ ...f, [key]: e.target.value }))}
                    className="h-9 rounded border border-surface-border px-3 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                  />
                </div>
              ))}
              <div>
                <label className="text-xs font-medium text-ink-muted block mb-1">Roles</label>
                <div className="flex flex-wrap gap-2">
                  {ALL_ROLES.map((r) => (
                    <label key={r} className="flex items-center gap-1.5 text-sm cursor-pointer">
                      <input
                        type="checkbox"
                        checked={form.role_names.includes(r)}
                        onChange={(e) => setForm(f => ({
                          ...f,
                          role_names: e.target.checked
                            ? [...f.role_names, r]
                            : f.role_names.filter((x) => x !== r),
                        }))}
                      />
                      {r}
                    </label>
                  ))}
                </div>
              </div>
            </div>
            <div className="flex gap-2 mt-5 justify-end">
              <Button variant="secondary" size="sm" onClick={() => setShowCreateModal(false)}>Cancel</Button>
              <Button size="sm"
                loading={createMutation.isPending}
                disabled={!form.email || !form.password || !form.full_name || !form.employee_id}
                onClick={() => createMutation.mutate(form)}>
                Create User
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Edit roles modal */}
      {showRolesModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-lg shadow-xl p-6 w-full max-w-sm mx-4">
            <h3 className="font-semibold text-ink mb-3">Edit Roles</h3>
            <div className="space-y-2">
              {ALL_ROLES.map((r) => (
                <label key={r} className="flex items-center gap-2 text-sm cursor-pointer hover:text-ink">
                  <input
                    type="checkbox"
                    checked={selectedRoles.includes(r)}
                    onChange={(e) => setSelectedRoles(prev =>
                      e.target.checked ? [...prev, r] : prev.filter(x => x !== r)
                    )}
                    className="rounded accent-brand-500"
                  />
                  {r}
                </label>
              ))}
            </div>
            <div className="flex gap-2 mt-4 justify-end">
              <Button variant="secondary" size="sm" onClick={() => setShowRolesModal(null)}>Cancel</Button>
              <Button size="sm"
                loading={rolesMutation.isPending}
                onClick={() => rolesMutation.mutate({ userId: showRolesModal.userId, roles: selectedRoles })}>
                Save Roles
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
