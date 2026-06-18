import { useState, useRef } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  BarChart2, Send, Loader2, AlertTriangle, History, Code2
} from "lucide-react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  LineChart, Line, PieChart, Pie, Cell
} from "recharts";
import { aiApi } from "@/api/ai";
import { Card, Button } from "@/components/ui";

const EXAMPLE_QUESTIONS = [
  "Which vendors caused the most delivery delays this quarter?",
  "What was the total spend by department last month?",
  "Show materials below their reorder point",
  "Which categories had the highest invoice value this year?",
  "How many PRs are pending approval right now?",
  "What is the average PO approval time by department?",
];

const CHART_COLORS = ["#6366f1", "#f59e0b", "#10b981", "#0ea5e9", "#ef4444", "#8b5cf6", "#f97316"];

export default function AIAnalyticsPage() {
  const [question, setQuestion] = useState("");
  const [results, setResults] = useState<any[]>([]);

  const queryMutation = useMutation({
    mutationFn: (q: string) => aiApi.analyticsQuery(q),
    onSuccess: (data) => setResults(prev => [data, ...prev]),
  });

  const { data: history } = useQuery({
    queryKey: ["analytics-history"],
    queryFn: () => aiApi.analyticsHistory(10),
  });

  const handleAsk = () => {
    if (!question.trim()) return;
    queryMutation.mutate(question.trim());
    setQuestion("");
  };

  return (
    <div className="max-w-5xl space-y-6">
      <div className="flex items-center gap-3">
        <div className="h-9 w-9 rounded-lg bg-brand-500 flex items-center justify-center">
          <BarChart2 className="h-5 w-5 text-white" />
        </div>
        <div>
          <h1 className="text-xl font-semibold text-ink">Analytics Assistant</h1>
          <p className="text-sm text-ink-muted">Ask procurement questions in plain English</p>
        </div>
      </div>

      {/* Query input */}
      <Card className="p-4">
        <div className="flex gap-3">
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleAsk()}
            placeholder="e.g. Which vendors had the most delays this quarter?"
            className="flex-1 h-10 rounded border border-surface-border px-3 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
          <Button onClick={handleAsk} disabled={!question.trim() || queryMutation.isPending}
            loading={queryMutation.isPending}>
            <Send className="h-4 w-4" /> Ask
          </Button>
        </div>

        {/* Suggested questions */}
        <div className="mt-3 flex flex-wrap gap-2">
          {EXAMPLE_QUESTIONS.map((q) => (
            <button key={q} onClick={() => setQuestion(q)}
              className="text-2xs px-2.5 py-1 rounded-full border border-surface-border hover:border-brand-300 hover:bg-brand-50 text-ink-muted transition-colors">
              {q}
            </button>
          ))}
        </div>
      </Card>

      {/* Results */}
      {results.map((result, idx) => (
        <AnalyticsResult key={idx} result={result} />
      ))}

      {/* History */}
      {!results.length && history && history.length > 0 && (
        <Card>
          <CardHeader title="Recent Queries" />
          <div className="divide-y divide-surface-border">
            {history.map((h: any) => (
              <div key={h.id} className="px-4 py-3 flex items-center justify-between hover:bg-surface-hover">
                <div>
                  <p className="text-sm text-ink">{h.question}</p>
                  <p className="text-2xs text-ink-muted mt-0.5">
                    {h.intent} · {h.row_count} rows · {h.asked_at?.slice(0, 10)}
                  </p>
                </div>
                <button onClick={() => setQuestion(h.question)}
                  className="text-brand-500 text-xs hover:underline">
                  Re-run →
                </button>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}

function CardHeader({ title }: { title: string }) {
  return (
    <div className="px-4 py-3 border-b border-surface-border">
      <h3 className="font-semibold text-ink text-sm">{title}</h3>
    </div>
  );
}

function AnalyticsResult({ result }: { result: any }) {
  const [showSql, setShowSql] = useState(false);

  if (result.error) {
    return (
      <Card className="border-red-200">
        <div className="p-4 flex items-start gap-3">
          <AlertTriangle className="h-5 w-5 text-red-500 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-red-700">Query Failed</p>
            <p className="text-xs text-red-500 mt-1">{result.error}</p>
            {result.intent && <p className="text-2xs text-ink-muted mt-1">Intent: {result.intent}</p>}
          </div>
        </div>
      </Card>
    );
  }

  const rows = result.rows ?? [];
  const columns = result.columns ?? [];

  return (
    <Card>
      <div className="px-4 py-3 border-b border-surface-border">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-ink">{result.question}</p>
            <p className="text-2xs text-ink-muted mt-0.5">
              {result.intent?.replace(/_/g, " ")} · {result.row_count} rows ·{" "}
              {result.model_used} · {result.latency_ms}ms
            </p>
          </div>
          <button onClick={() => setShowSql(v => !v)}
            className="flex items-center gap-1 text-2xs text-ink-muted hover:text-ink border border-surface-border rounded px-2 py-1">
            <Code2 className="h-3 w-3" />
            {showSql ? "Hide SQL" : "View SQL"}
          </button>
        </div>
      </div>

      {showSql && (
        <div className="px-4 py-3 border-b border-surface-border bg-surface">
          <pre className="text-2xs font-mono text-ink-muted whitespace-pre-wrap overflow-x-auto">
            {result.sql}
          </pre>
        </div>
      )}

      {/* Chart */}
      {rows.length > 0 && (
        <div className="p-4">
          <ResultChart rows={rows} columns={columns} chartType={result.chart_type ?? "table"} />
        </div>
      )}

      {/* Table fallback */}
      {rows.length > 0 && result.chart_type === "table" && (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-surface-border bg-surface">
                {columns.map((col: string) => (
                  <th key={col} className="px-4 py-2 text-left font-semibold text-ink-muted uppercase tracking-wide text-2xs">
                    {col.replace(/_/g, " ")}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.slice(0, 50).map((row: any, i: number) => (
                <tr key={i} className="border-b border-surface-border last:border-0 hover:bg-surface-hover">
                  {columns.map((col: string) => (
                    <td key={col} className="px-4 py-2 tabular text-ink">
                      {typeof row[col] === "number" ? row[col].toLocaleString("en-IN") : String(row[col] ?? "—")}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          {rows.length > 50 && (
            <p className="text-center text-2xs text-ink-muted py-2">
              Showing 50 of {rows.length} rows
            </p>
          )}
        </div>
      )}

      {rows.length === 0 && (
        <div className="px-4 py-8 text-center text-sm text-ink-muted">
          No data found for this query.
        </div>
      )}
    </Card>
  );
}

function ResultChart({ rows, columns, chartType }: { rows: any[]; columns: string[]; chartType: string }) {
  if (chartType === "table" || rows.length === 0) return null;

  const numCols = columns.filter(c => rows.some(r => typeof r[c] === "number"));
  const strCols = columns.filter(c => rows.some(r => typeof r[c] === "string"));
  const labelKey = strCols[0] ?? columns[0];
  const valueKey = numCols[0] ?? columns[1];

  if (chartType === "number" && rows.length === 1) {
    const val = rows[0][valueKey];
    return (
      <div className="text-center py-4">
        <p className="text-4xl font-bold tabular text-brand-500">
          {typeof val === "number" ? val.toLocaleString("en-IN") : String(val)}
        </p>
        <p className="text-sm text-ink-muted mt-1">{labelKey.replace(/_/g, " ")}</p>
      </div>
    );
  }

  const data = rows.slice(0, 20).map(row => ({
    name: String(row[labelKey] ?? "").slice(0, 20),
    value: Number(row[valueKey] ?? 0),
  }));

  if (chartType === "bar") {
    return (
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={data} barCategoryGap="35%">
          <XAxis dataKey="name" tick={{ fontSize: 10, fill: "#9ca3af" }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fontSize: 10, fill: "#9ca3af" }} axisLine={false} tickLine={false} />
          <Tooltip contentStyle={{ fontSize: 11, borderRadius: 6, border: "1px solid #e4e7ec" }} />
          <Bar dataKey="value" radius={[4, 4, 0, 0]}>
            {data.map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    );
  }

  if (chartType === "pie") {
    return (
      <ResponsiveContainer width="100%" height={200}>
        <PieChart>
          <Pie data={data} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={70}
            label={({ name, percent }) => `${name} (${(percent * 100).toFixed(0)}%)`}>
            {data.map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
          </Pie>
          <Tooltip contentStyle={{ fontSize: 11 }} />
        </PieChart>
      </ResponsiveContainer>
    );
  }

  if (chartType === "line") {
    return (
      <ResponsiveContainer width="100%" height={200}>
        <LineChart data={data}>
          <XAxis dataKey="name" tick={{ fontSize: 10, fill: "#9ca3af" }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fontSize: 10, fill: "#9ca3af" }} axisLine={false} tickLine={false} />
          <Tooltip contentStyle={{ fontSize: 11, borderRadius: 6 }} />
          <Line type="monotone" dataKey="value" stroke="#6366f1" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    );
  }

  return null;
}
