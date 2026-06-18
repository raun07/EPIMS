// src/pages/procurement/PRListPage.tsx
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Plus, Search, Filter, ChevronRight, RefreshCw } from "lucide-react";
import { prApi } from "@/api/procurement";
import { formatCurrency, formatDate } from "@/lib/utils";
import {
  Button,
  Card,
  CardHeader,
  StatusBadge,
  EmptyState,
  TableSkeleton,
  Input,
} from "@/components/ui";

const STATUS_OPTIONS = [
  { value: "", label: "All statuses" },
  { value: "DRAFT", label: "Draft" },
  { value: "SUBMITTED", label: "Submitted" },
  { value: "PENDING_APPROVAL", label: "Pending Approval" },
  { value: "APPROVED", label: "Approved" },
  { value: "REJECTED", label: "Rejected" },
  { value: "PO_CREATED", label: "PO Created" },
  { value: "CANCELLED", label: "Cancelled" },
];

export default function PRListPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState("");
  const [myPRs, setMyPRs] = useState(false);

  const { data, isLoading, isFetching } = useQuery({
    queryKey: ["prs", page, statusFilter, myPRs],
    queryFn: () =>
      prApi.list({ page, per_page: 20, status: statusFilter || undefined, my_prs: myPRs }),
    keepPreviousData: true,
  });

  const prs = data?.data ?? [];
  const meta = data?.meta;

  return (
    <div className="max-w-7xl space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-ink">Purchase Requisitions</h1>
          <p className="text-sm text-ink-muted mt-0.5">
            {meta ? `${meta.total} total` : "Loading…"}
          </p>
        </div>
        <Button onClick={() => navigate("/procurement/pr/new")}>
          <Plus className="h-4 w-4" />
          New PR
        </Button>
      </div>

      {/* Filters */}
      <Card>
        <div className="flex flex-wrap items-center gap-3 px-4 py-3 border-b border-surface-border">
          <select
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
            className="h-8 rounded border border-surface-border bg-white px-2 text-sm text-ink focus:outline-none focus:ring-2 focus:ring-brand-500"
          >
            {STATUS_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>

          <label className="flex items-center gap-2 text-sm text-ink-muted cursor-pointer">
            <input
              type="checkbox"
              checked={myPRs}
              onChange={(e) => { setMyPRs(e.target.checked); setPage(1); }}
              className="rounded"
            />
            My PRs only
          </label>

          <button
            onClick={() => queryClient.invalidateQueries({ queryKey: ["prs"] })}
            className="ml-auto text-ink-muted hover:text-ink"
            title="Refresh"
          >
            <RefreshCw className={`h-4 w-4 ${isFetching ? "animate-spin" : ""}`} />
          </button>
        </div>

        {isLoading ? (
          <TableSkeleton rows={8} cols={6} />
        ) : prs.length === 0 ? (
          <EmptyState
            title="No requisitions found"
            description="Create your first PR to get started"
            action={
              <Button size="sm" onClick={() => navigate("/procurement/pr/new")}>
                <Plus className="h-3.5 w-3.5" /> New PR
              </Button>
            }
          />
        ) : (
          <>
            <table className="w-full">
              <thead>
                <tr className="border-b border-surface-border">
                  <th className="th text-left">PR Number</th>
                  <th className="th text-left">Title</th>
                  <th className="th text-left">Priority</th>
                  <th className="th text-right">Value</th>
                  <th className="th text-left">Requested</th>
                  <th className="th text-left">Status</th>
                  <th className="th" />
                </tr>
              </thead>
              <tbody>
                {prs.map((pr) => (
                  <tr
                    key={pr.id}
                    onClick={() => navigate(`/procurement/pr/${pr.id}`)}
                    className="border-b border-surface-border last:border-0 hover:bg-surface-hover cursor-pointer"
                  >
                    <td className="td font-mono text-xs text-brand-500 font-medium">
                      {pr.pr_number}
                    </td>
                    <td className="td text-ink max-w-[200px]">
                      <div className="truncate">{pr.title}</div>
                      {pr.department && (
                        <div className="text-2xs text-ink-muted">{pr.department}</div>
                      )}
                    </td>
                    <td className="td">
                      <span className={`text-2xs font-medium ${
                        pr.priority === "URGENT" ? "text-red-500" :
                        pr.priority === "HIGH" ? "text-amber-500" :
                        "text-ink-muted"
                      }`}>
                        {pr.priority}
                      </span>
                    </td>
                    <td className="td text-right tabular text-ink font-medium">
                      {formatCurrency(parseFloat(pr.total_value), pr.currency)}
                    </td>
                    <td className="td text-ink-muted text-xs">
                      {formatDate(pr.created_at)}
                    </td>
                    <td className="td">
                      <StatusBadge status={pr.status} />
                    </td>
                    <td className="td">
                      <ChevronRight className="h-4 w-4 text-ink-subtle" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {/* Pagination */}
            {meta && meta.total_pages > 1 && (
              <div className="flex items-center justify-between px-4 py-3 border-t border-surface-border">
                <p className="text-xs text-ink-muted">
                  Page {meta.page} of {meta.total_pages} · {meta.total} items
                </p>
                <div className="flex gap-2">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => setPage((p) => p - 1)}
                    disabled={!meta.has_prev}
                  >
                    Previous
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => setPage((p) => p + 1)}
                    disabled={!meta.has_next}
                  >
                    Next
                  </Button>
                </div>
              </div>
            )}
          </>
        )}
      </Card>
    </div>
  );
}
