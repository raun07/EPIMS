import { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  Sparkles, Send, Loader2, CheckCircle, AlertTriangle,
  ChevronRight, ThumbsUp, ThumbsDown, X, Bot, User
} from "lucide-react";
import { aiApi } from "@/api/ai";
import { formatCurrency } from "@/lib/utils";
import { Button, Card, CardHeader, StatusBadge } from "@/components/ui";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  data?: any;
  type?: "nl_to_pr" | "info" | "error";
  interactionId?: string;
}

const SUGGESTED_PROMPTS = [
  "Need 25 Dell laptops for new engineering team joining next month. Budget ₹15 lakh.",
  "Procure 3-year Microsoft 365 E3 licenses for 50 users",
  "Office chairs and desks for 10 new workstations in Bengaluru office",
  "Annual maintenance contract for 3 industrial air compressors",
];

export default function AICopilotPage() {
  const navigate = useNavigate();
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      role: "assistant",
      content: "Hi! I'm your **AI Procurement Copilot**. Tell me what you need to purchase in plain English — I'll convert it into a structured Purchase Requisition, check compliance, and recommend vendors.",
      type: "info",
    }
  ]);
  const [input, setInput] = useState("");
  const [sessionId] = useState(() => crypto.randomUUID());
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const { data: aiStatus } = useQuery({ queryKey: ["ai-status"], queryFn: aiApi.status });

  const nlMutation = useMutation({
    mutationFn: (text: string) => aiApi.nlToPr(text, sessionId),
    onSuccess: (data, text) => {
      const msg: Message = {
        id: crypto.randomUUID(),
        role: "assistant",
        type: "nl_to_pr",
        content: data.error ? data.error : "",
        data,
        interactionId: data.interaction_id,
      };
      setMessages(prev => [...prev, msg]);
    },
    onError: () => {
      setMessages(prev => [...prev, {
        id: crypto.randomUUID(),
        role: "assistant",
        type: "error",
        content: "Something went wrong. Please try again.",
      }]);
    }
  });

  const acceptMutation = useMutation({
    mutationFn: (draftId: string) => aiApi.acceptPrDraft(draftId),
    onSuccess: (data) => {
      setMessages(prev => [...prev, {
        id: crypto.randomUUID(),
        role: "assistant",
        type: "info",
        content: `✅ PR **${data.pr_number}** created in draft status. You can now edit and submit it for approval.`,
        data: { pr_id: data.pr_id, pr_number: data.pr_number },
      }]);
    }
  });

  const feedbackMutation = useMutation({
    mutationFn: ({ interactionId, score }: { interactionId: string; score: number }) =>
      aiApi.submitFeedback(interactionId, score),
  });

  const handleSend = () => {
    const text = input.trim();
    if (!text) return;
    setMessages(prev => [...prev, { id: crypto.randomUUID(), role: "user", content: text }]);
    setInput("");
    nlMutation.mutate(text);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const renderMessage = (msg: Message) => {
    if (msg.role === "user") {
      return (
        <div key={msg.id} className="flex items-start gap-3 justify-end">
          <div className="bg-brand-500 text-white rounded-2xl rounded-tr-sm px-4 py-3 max-w-lg text-sm">
            {msg.content}
          </div>
          <div className="h-8 w-8 rounded-full bg-brand-100 flex items-center justify-center flex-shrink-0">
            <User className="h-4 w-4 text-brand-600" />
          </div>
        </div>
      );
    }

    // Assistant message
    return (
      <div key={msg.id} className="flex items-start gap-3">
        <div className="h-8 w-8 rounded-full bg-brand-500 flex items-center justify-center flex-shrink-0">
          <Bot className="h-4 w-4 text-white" />
        </div>
        <div className="flex-1 max-w-2xl space-y-3">
          {/* Simple text message */}
          {msg.type === "info" && (
            <div className="bg-white rounded-2xl rounded-tl-sm px-4 py-3 border border-surface-border shadow-card text-sm text-ink">
              {msg.content.split("**").map((part, i) =>
                i % 2 === 1 ? <strong key={i}>{part}</strong> : part
              )}
              {msg.data?.pr_number && (
                <button
                  onClick={() => navigate(`/procurement/pr/${msg.data.pr_id}`)}
                  className="ml-2 text-brand-500 hover:underline text-xs font-medium"
                >
                  View PR →
                </button>
              )}
            </div>
          )}

          {/* NL→PR Draft card */}
          {msg.type === "nl_to_pr" && msg.data && !msg.data.error && (
            <PRDraftCard
              data={msg.data}
              onAccept={(draftId) => acceptMutation.mutate(draftId)}
              onFeedback={(score) => feedbackMutation.mutate({ interactionId: msg.interactionId!, score })}
              accepting={acceptMutation.isPending}
            />
          )}

          {/* Error */}
          {msg.type === "error" && (
            <div className="bg-red-50 border border-red-200 rounded-2xl rounded-tl-sm px-4 py-3 text-sm text-red-600">
              {msg.content}
            </div>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="max-w-4xl mx-auto h-[calc(100vh-8rem)] flex flex-col space-y-0">
      {/* Header */}
      <div className="flex items-center justify-between pb-4 flex-shrink-0">
        <div className="flex items-center gap-3">
          <div className="h-9 w-9 rounded-lg bg-brand-500 flex items-center justify-center">
            <Sparkles className="h-5 w-5 text-white" />
          </div>
          <div>
            <h1 className="text-xl font-semibold text-ink">AI Procurement Copilot</h1>
            <p className="text-xs text-ink-muted">
              {aiStatus?.api_key_configured
                ? `Powered by ${aiStatus.primary_model}`
                : "Configure ANTHROPIC_API_KEY to enable"}
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" size="sm" onClick={() => navigate("/ai/analytics")}>
            Analytics
          </Button>
          <Button variant="secondary" size="sm" onClick={() => navigate("/ai/documents")}>
            Document AI
          </Button>
        </div>
      </div>

      {/* AI not configured warning */}
      {aiStatus && !aiStatus.api_key_configured && (
        <div className="flex items-center gap-3 bg-amber-50 border border-amber-200 rounded-lg px-4 py-3 mb-3">
          <AlertTriangle className="h-4 w-4 text-amber-500 flex-shrink-0" />
          <p className="text-sm text-amber-700">
            Add <code className="font-mono bg-amber-100 px-1 rounded">ANTHROPIC_API_KEY=your-key</code> to{" "}
            <code className="font-mono bg-amber-100 px-1 rounded">.env</code> to enable AI features.
          </p>
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto space-y-4 py-2">
        {messages.map(renderMessage)}
        {nlMutation.isPending && (
          <div className="flex items-start gap-3">
            <div className="h-8 w-8 rounded-full bg-brand-500 flex items-center justify-center">
              <Bot className="h-4 w-4 text-white" />
            </div>
            <div className="bg-white rounded-2xl rounded-tl-sm px-4 py-3 border border-surface-border">
              <div className="flex items-center gap-2 text-sm text-ink-muted">
                <Loader2 className="h-4 w-4 animate-spin" />
                Analyzing your request…
              </div>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Suggested prompts */}
      {messages.length === 1 && (
        <div className="grid grid-cols-2 gap-2 py-3 flex-shrink-0">
          {SUGGESTED_PROMPTS.map((prompt) => (
            <button
              key={prompt}
              onClick={() => { setInput(prompt); }}
              className="text-left text-xs px-3 py-2.5 rounded-lg border border-surface-border hover:border-brand-300 hover:bg-brand-50 text-ink-muted transition-colors"
            >
              {prompt}
            </button>
          ))}
        </div>
      )}

      {/* Input */}
      <div className="flex-shrink-0 pt-3 border-t border-surface-border">
        <div className="flex items-end gap-3">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Describe what you need to purchase…"
            rows={2}
            className="flex-1 rounded-lg border border-surface-border px-4 py-3 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
          <Button
            onClick={handleSend}
            disabled={!input.trim() || nlMutation.isPending}
            loading={nlMutation.isPending}
            className="h-12 px-5"
          >
            <Send className="h-4 w-4" />
          </Button>
        </div>
        <p className="text-2xs text-ink-subtle mt-1.5">
          Press Enter to send · Shift+Enter for new line
        </p>
      </div>
    </div>
  );
}

// ── PR Draft Card ─────────────────────────────────────────────────────────────

function PRDraftCard({
  data, onAccept, onFeedback, accepting
}: {
  data: any;
  onAccept: (draftId: string) => void;
  onFeedback: (score: number) => void;
  accepting: boolean;
}) {
  const [feedbackGiven, setFeedbackGiven] = useState<"up" | "down" | null>(null);
  const confidence = data.confidence_score ?? 0;
  const confColor = confidence >= 0.8 ? "text-emerald-600" : confidence >= 0.65 ? "text-amber-500" : "text-red-500";

  return (
    <div className="bg-white rounded-2xl rounded-tl-sm border border-surface-border shadow-card overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-surface-border bg-brand-50">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-brand-500" />
            <span className="text-sm font-semibold text-ink">Draft PR Generated</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="text-2xs text-ink-muted">Confidence:</span>
            <span className={`text-xs font-semibold tabular ${confColor}`}>
              {Math.round(confidence * 100)}%
            </span>
          </div>
        </div>
      </div>

      <div className="p-4 space-y-3">
        {/* Title */}
        <div>
          <p className="text-2xs text-ink-muted uppercase tracking-widest mb-0.5">Title</p>
          <p className="text-sm font-medium text-ink">{data.title}</p>
        </div>

        {/* Meta row */}
        <div className="grid grid-cols-3 gap-3">
          {[
            { label: "Department", value: data.department ?? "Not detected" },
            { label: "Priority", value: data.priority ?? "NORMAL" },
            { label: "Required by", value: data.required_by_date ?? "Not specified" },
          ].map(({ label, value }) => (
            <div key={label}>
              <p className="text-2xs text-ink-muted uppercase tracking-widest">{label}</p>
              <p className="text-xs text-ink mt-0.5">{value}</p>
            </div>
          ))}
        </div>

        {/* Budget */}
        {data.estimated_budget && (
          <div>
            <p className="text-2xs text-ink-muted uppercase tracking-widest mb-0.5">Estimated Budget</p>
            <p className="text-sm font-semibold text-ink">{formatCurrency(data.estimated_budget)}</p>
          </div>
        )}

        {/* Line items */}
        <div>
          <p className="text-2xs text-ink-muted uppercase tracking-widest mb-1">
            Line Items ({data.items?.length ?? 0})
          </p>
          <div className="space-y-1">
            {(data.items ?? []).slice(0, 5).map((item: any, i: number) => (
              <div key={i} className="flex justify-between text-xs text-ink bg-surface rounded px-3 py-1.5">
                <span>{item.description}</span>
                <span className="tabular text-ink-muted">
                  × {item.quantity} {item.unit}
                  {item.estimated_unit_price && ` @ ${formatCurrency(item.estimated_unit_price)}`}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Business justification */}
        {data.business_justification && (
          <div className="bg-surface rounded px-3 py-2">
            <p className="text-2xs text-ink-muted uppercase tracking-widest mb-0.5">Business Justification</p>
            <p className="text-xs text-ink">{data.business_justification}</p>
          </div>
        )}

        {/* Ambiguities */}
        {data.ambiguities?.length > 0 && (
          <div className="bg-amber-50 border border-amber-200 rounded px-3 py-2">
            <p className="text-2xs text-amber-600 font-semibold uppercase tracking-widest mb-1">
              Needs Clarification
            </p>
            <ul className="space-y-0.5">
              {data.ambiguities.map((a: string, i: number) => (
                <li key={i} className="text-xs text-amber-700">• {a}</li>
              ))}
            </ul>
          </div>
        )}

        {/* Actions */}
        <div className="flex items-center justify-between pt-1">
          <div className="flex items-center gap-2">
            <span className="text-2xs text-ink-muted">Was this helpful?</span>
            <button
              onClick={() => { setFeedbackGiven("up"); onFeedback(5); }}
              className={`h-6 w-6 flex items-center justify-center rounded hover:bg-emerald-50 ${feedbackGiven === "up" ? "text-emerald-500" : "text-ink-subtle"}`}
            >
              <ThumbsUp className="h-3.5 w-3.5" />
            </button>
            <button
              onClick={() => { setFeedbackGiven("down"); onFeedback(2); }}
              className={`h-6 w-6 flex items-center justify-center rounded hover:bg-red-50 ${feedbackGiven === "down" ? "text-red-500" : "text-ink-subtle"}`}
            >
              <ThumbsDown className="h-3.5 w-3.5" />
            </button>
          </div>
          <div className="flex gap-2">
            {data.ready_to_create && data.draft_id && (
              <Button size="sm" loading={accepting} onClick={() => onAccept(data.draft_id)}>
                <CheckCircle className="h-3.5 w-3.5" /> Create PR
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
