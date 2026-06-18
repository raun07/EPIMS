import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Sparkles, RefreshCw, CheckCircle, AlertTriangle, Loader2, ThumbsUp, ThumbsDown } from "lucide-react";
import { aiApi } from "@/api/ai";
import { Button } from "@/components/ui";

interface ApprovalSummaryCardProps {
  prId: string;
  prStatus: string;
}

export function ApprovalSummaryCard({ prId, prStatus }: ApprovalSummaryCardProps) {
  const qc = useQueryClient();
  const [feedbackGiven, setFeedbackGiven] = useState<"up" | "down" | null>(null);

  const { data: summary, isLoading, isError } = useQuery({
    queryKey: ["approval-summary", prId],
    queryFn: () => aiApi.approvalSummary(prId),
    enabled: ["PENDING_APPROVAL", "APPROVED", "SUBMITTED"].includes(prStatus),
    retry: 1,
  });

  const regenMutation = useMutation({
    mutationFn: () => aiApi.regenerateApprovalSummary(prId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["approval-summary", prId] }),
  });

  const feedbackMutation = useMutation({
    mutationFn: ({ score }: { score: number }) =>
      aiApi.submitFeedback(summary.interaction_id, score),
  });

  if (!["PENDING_APPROVAL", "APPROVED", "SUBMITTED"].includes(prStatus)) return null;

  const recColor = {
    APPROVE: "text-emerald-600 bg-emerald-50 border-emerald-200",
    REVIEW: "text-amber-600 bg-amber-50 border-amber-200",
    ESCALATE: "text-red-600 bg-red-50 border-red-200",
  }[summary?.recommendation as string] ?? "text-ink-muted bg-surface border-surface-border";

  return (
    <div className="border border-surface-border rounded-lg overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 bg-gradient-to-r from-brand-50 to-white border-b border-surface-border">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-brand-500" />
          <span className="text-sm font-semibold text-ink">AI Approval Summary</span>
          {summary?.from_cache && (
            <span className="text-2xs text-ink-subtle">cached</span>
          )}
        </div>
        <button
          onClick={() => regenMutation.mutate()}
          disabled={regenMutation.isPending}
          className="text-ink-muted hover:text-ink transition-colors"
          title="Regenerate summary"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${regenMutation.isPending ? "animate-spin" : ""}`} />
        </button>
      </div>

      {/* Loading */}
      {(isLoading || regenMutation.isPending) && (
        <div className="flex items-center gap-3 px-4 py-5">
          <Loader2 className="h-4 w-4 animate-spin text-brand-400" />
          <p className="text-sm text-ink-muted">Generating approval summary…</p>
        </div>
      )}

      {/* Error */}
      {(isError || summary?.error) && !isLoading && (
        <div className="px-4 py-4 flex items-center gap-2 text-sm text-amber-600">
          <AlertTriangle className="h-4 w-4 flex-shrink-0" />
          AI summary unavailable. Manual review required.
        </div>
      )}

      {/* Summary content */}
      {summary && !summary.error && !isLoading && (
        <div className="p-4 space-y-3">
          {/* Headline */}
          {summary.headline && (
            <p className="text-sm font-medium text-ink">{summary.headline}</p>
          )}

          {/* Recommendation badge */}
          {summary.recommendation && (
            <div className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-xs font-semibold ${recColor}`}>
              {summary.recommendation === "APPROVE" && <CheckCircle className="h-3.5 w-3.5" />}
              {summary.recommendation === "REVIEW" && <AlertTriangle className="h-3.5 w-3.5" />}
              AI Recommendation: {summary.recommendation}
            </div>
          )}

          {/* Three columns */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {summary.purchase_rationale && (
              <div className="bg-surface rounded-lg p-3">
                <p className="text-2xs text-ink-muted uppercase tracking-widest mb-1">Why</p>
                <p className="text-xs text-ink">{summary.purchase_rationale}</p>
              </div>
            )}
            {summary.cost_impact && (
              <div className="bg-surface rounded-lg p-3">
                <p className="text-2xs text-ink-muted uppercase tracking-widest mb-1">Cost Impact</p>
                <p className="text-xs text-ink">{summary.cost_impact}</p>
              </div>
            )}
            {summary.business_value && (
              <div className="bg-surface rounded-lg p-3">
                <p className="text-2xs text-ink-muted uppercase tracking-widest mb-1">Business Value</p>
                <p className="text-xs text-ink">{summary.business_value}</p>
              </div>
            )}
          </div>

          {/* Risk flags */}
          {summary.risk_flags?.length > 0 && (
            <div className="space-y-1.5">
              {summary.risk_flags.map((flag: any, i: number) => (
                <div key={i} className={`flex items-start gap-2 px-3 py-2 rounded border text-xs ${
                  flag.severity === "HIGH" ? "bg-red-50 border-red-200 text-red-700" :
                  flag.severity === "MEDIUM" ? "bg-amber-50 border-amber-200 text-amber-700" :
                  "bg-surface border-surface-border text-ink-muted"
                }`}>
                  <AlertTriangle className="h-3.5 w-3.5 flex-shrink-0 mt-0.5" />
                  <span><strong>{flag.flag}:</strong> {flag.detail}</span>
                </div>
              ))}
            </div>
          )}

          {/* Comparable purchases */}
          {summary.comparable_purchases?.length > 0 && (
            <div>
              <p className="text-2xs text-ink-muted uppercase tracking-widest mb-1">Similar Past PRs</p>
              <div className="space-y-1">
                {summary.comparable_purchases.slice(0, 2).map((cp: any, i: number) => (
                  <div key={i} className="flex justify-between text-xs text-ink-muted bg-surface rounded px-3 py-1.5">
                    <span className="font-mono text-brand-500">{cp.pr_number}</span>
                    <span>{cp.title?.slice(0, 30)}</span>
                    <span className="tabular font-medium">{cp.total_value?.toLocaleString("en-IN") ? `₹${Number(cp.total_value).toLocaleString("en-IN")}` : "—"}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Feedback */}
          {summary.interaction_id && (
            <div className="flex items-center gap-2 pt-1 border-t border-surface-border">
              <span className="text-2xs text-ink-muted">Helpful?</span>
              <button
                onClick={() => { setFeedbackGiven("up"); feedbackMutation.mutate({ score: 5 }); }}
                className={`h-6 w-6 flex items-center justify-center rounded hover:bg-emerald-50 transition-colors ${feedbackGiven === "up" ? "text-emerald-500" : "text-ink-subtle"}`}
              >
                <ThumbsUp className="h-3.5 w-3.5" />
              </button>
              <button
                onClick={() => { setFeedbackGiven("down"); feedbackMutation.mutate({ score: 2 }); }}
                className={`h-6 w-6 flex items-center justify-center rounded hover:bg-red-50 transition-colors ${feedbackGiven === "down" ? "text-red-500" : "text-ink-subtle"}`}
              >
                <ThumbsDown className="h-3.5 w-3.5" />
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Policy Check Widget ───────────────────────────────────────────────────────

interface PolicyCheckWidgetProps {
  prId: string;
  prStatus: string;
}

export function PolicyCheckWidget({ prId, prStatus }: PolicyCheckWidgetProps) {
  const [result, setResult] = useState<any>(null);
  const checkMutation = useMutation({
    mutationFn: () => aiApi.policyCheck(prId),
    onSuccess: (data) => setResult(data),
  });

  if (!["DRAFT"].includes(prStatus)) return null;

  const severityIcon = result?.overall_status === "PASS"
    ? <CheckCircle className="h-4 w-4 text-emerald-500" />
    : result?.overall_status === "BLOCK"
    ? <AlertTriangle className="h-4 w-4 text-red-500" />
    : <AlertTriangle className="h-4 w-4 text-amber-500" />;

  return (
    <div className="border border-surface-border rounded-lg overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-surface-border bg-surface">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-brand-500" />
          <span className="text-sm font-semibold text-ink">Policy Compliance Check</span>
        </div>
        {!result && (
          <Button size="sm" variant="secondary" loading={checkMutation.isPending}
            onClick={() => checkMutation.mutate()}>
            Run Check
          </Button>
        )}
      </div>

      {result && (
        <div className="p-4 space-y-3">
          <div className="flex items-center gap-2">
            {severityIcon}
            <span className="text-sm font-medium text-ink">{result.summary}</span>
          </div>

          {/* Violation counts */}
          {result.violation_count && (
            <div className="flex gap-3">
              {result.violation_count.BLOCK > 0 && (
                <span className="badge badge-rejected">
                  {result.violation_count.BLOCK} Blocking
                </span>
              )}
              {result.violation_count.WARN > 0 && (
                <span className="badge badge-pending">
                  {result.violation_count.WARN} Warnings
                </span>
              )}
              {result.violation_count.INFO > 0 && (
                <span className="badge badge-draft">
                  {result.violation_count.INFO} Info
                </span>
              )}
            </div>
          )}

          {/* Violations */}
          {result.violations?.map((v: any, i: number) => (
            <div key={i} className={`px-3 py-2.5 rounded border text-xs space-y-1 ${
              v.severity === "BLOCK" ? "bg-red-50 border-red-200" :
              v.severity === "WARN" ? "bg-amber-50 border-amber-200" :
              "bg-surface border-surface-border"
            }`}>
              <div className="flex items-center gap-1.5">
                <span className={`font-semibold uppercase text-2xs ${
                  v.severity === "BLOCK" ? "text-red-600" :
                  v.severity === "WARN" ? "text-amber-600" : "text-ink-muted"
                }`}>{v.severity}</span>
                <span className="font-medium text-ink">{v.rule_name}</span>
              </div>
              <p className="text-ink-muted">{v.explanation}</p>
              <p className="text-ink">💡 {v.suggested_fix}</p>
            </div>
          ))}

          {result.auto_approvable && (
            <div className="flex items-center gap-2 text-xs text-emerald-600">
              <CheckCircle className="h-3.5 w-3.5" />
              This PR may qualify for auto-approval (no blocking violations)
            </div>
          )}
        </div>
      )}
    </div>
  );
}
