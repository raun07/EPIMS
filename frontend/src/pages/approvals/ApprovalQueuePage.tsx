import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import api from "@/lib/api";
import { formatCurrency, formatDateTime } from "@/lib/utils";
import { Button, Card, CardHeader, EmptyState, TableSkeleton } from "@/components/ui";
import { CheckCircle, XCircle, Forward, Inbox } from "lucide-react";
import { useState } from "react";

interface ApprovalInstance {
  id: string;
  document_type: string;
  document_id: string;
  document_number: string;
  document_value: number;
  currency: string;
  current_step: number;
  total_steps: number;
  requester_name: string;
  started_at: string;
  status: string;
}

async function fetchApprovalQueue(): Promise<ApprovalInstance[]> {
  const r = await api.get("/approvals/queue");
  return r.data;
}

async function processApproval(instanceId: string, action: string, comments: string) {
  const r = await api.post(`/approvals/${instanceId}/action`, { action, comments });
  return r.data;
}

export default function ApprovalQueuePage() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [activeId, setActiveId] = useState<string | null>(null);
  const [comments, setComments] = useState("");
  const [actionType, setActionType] = useState<"APPROVED" | "REJECTED" | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["approval-queue"],
    queryFn: fetchApprovalQueue,
    refetchInterval: 30_000,
  });

  const actionMutation = useMutation({
    mutationFn: ({ id, action, comments }: { id: string; action: string; comments: string }) =>
      processApproval(id, action, comments),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["approval-queue"] });
      setActiveId(null);
      setComments("");
      setActionType(null);
    },
  });

  const openAction = (id: string, action: "APPROVED" | "REJECTED") => {
    setActiveId(id);
    setActionType(action);
    setComments("");
  };

  const docPath = (type: string, docId: string) => {
    if (type === "PR") return `/procurement/pr/${docId}`;
    if (type === "PO") return `/procurement/po/${docId}`;
    return "#";
  };

  return (
    <div className="max-w-5xl space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-ink">Approval Queue</h1>
        <p className="text-sm text-ink-muted mt-0.5">
          {data ? `${data.length} item${data.length !== 1 ? "s" : ""} awaiting your decision` : "Loading…"}
        </p>
      </div>

      <Card>
        <CardHeader title="Pending Approvals" />
        {isLoading ? (
          <TableSkeleton rows={5} cols={6} />
        ) : !data || data.length === 0 ? (
          <EmptyState
            icon={<Inbox className="h-10 w-10" />}
            title="Queue is empty"
            description="No documents are currently awaiting your approval."
          />
        ) : (
          <table className="w-full">
            <thead>
              <tr className="border-b border-surface-border">
                <th className="th text-left">Document</th>
                <th className="th text-left">Type</th>
                <th className="th text-left">Requested by</th>
                <th className="th text-right">Value</th>
                <th className="th text-left">Step</th>
                <th className="th text-left">Waiting since</th>
                <th className="th text-center">Actions</th>
              </tr>
            </thead>
            <tbody>
              {data.map((item) => (
                <tr key={item.id} className="border-b border-surface-border last:border-0 hover:bg-surface-hover">
                  <td className="td">
                    <button
                      onClick={() => navigate(docPath(item.document_type, item.document_id))}
                      className="font-mono text-xs text-brand-500 hover:underline font-medium"
                    >
                      {item.document_number}
                    </button>
                  </td>
                  <td className="td">
                    <span className="text-2xs font-semibold uppercase bg-brand-50 text-brand-600 px-2 py-0.5 rounded">
                      {item.document_type}
                    </span>
                  </td>
                  <td className="td text-ink text-sm">{item.requester_name}</td>
                  <td className="td text-right tabular font-medium">
                    {formatCurrency(item.document_value, item.currency)}
                  </td>
                  <td className="td text-ink-muted text-xs">
                    {item.current_step} / {item.total_steps}
                  </td>
                  <td className="td text-ink-muted text-xs">
                    {formatDateTime(item.started_at)}
                  </td>
                  <td className="td">
                    <div className="flex items-center justify-center gap-2">
                      <button
                        title="Approve"
                        onClick={() => openAction(item.id, "APPROVED")}
                        className="h-7 w-7 flex items-center justify-center rounded hover:bg-emerald-50 text-emerald-500 hover:text-emerald-600 transition-colors"
                      >
                        <CheckCircle className="h-4 w-4" />
                      </button>
                      <button
                        title="Reject"
                        onClick={() => openAction(item.id, "REJECTED")}
                        className="h-7 w-7 flex items-center justify-center rounded hover:bg-red-50 text-red-400 hover:text-red-500 transition-colors"
                      >
                        <XCircle className="h-4 w-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      {/* Action modal */}
      {activeId && actionType && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-lg shadow-xl p-6 w-full max-w-md mx-4">
            <h3 className={`font-semibold mb-1 ${actionType === "APPROVED" ? "text-emerald-700" : "text-red-600"}`}>
              {actionType === "APPROVED" ? "Approve document" : "Return for revision"}
            </h3>
            <p className="text-sm text-ink-muted mb-4">
              {actionType === "APPROVED"
                ? "The document will advance to the next approval step or be fully approved."
                : "The document will be returned to the requester with your comments."}
            </p>
            <textarea
              value={comments}
              onChange={(e) => setComments(e.target.value)}
              placeholder={actionType === "APPROVED" ? "Optional comments…" : "Reason for returning (required)…"}
              rows={3}
              className="w-full border border-surface-border rounded px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
            <div className="flex gap-2 mt-4 justify-end">
              <Button variant="secondary" size="sm" onClick={() => setActiveId(null)}>Cancel</Button>
              <Button
                size="sm"
                variant={actionType === "REJECTED" ? "danger" : "primary"}
                disabled={actionType === "REJECTED" && comments.trim().length < 5}
                loading={actionMutation.isPending}
                onClick={() => actionMutation.mutate({ id: activeId, action: actionType, comments })}
              >
                {actionType === "APPROVED" ? "Approve" : "Return"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
