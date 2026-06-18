import api from "@/lib/api";

// ── ① NL→PR ──────────────────────────────────────────────────────────────────
export const aiApi = {
  // NL → PR extraction
  nlToPr: (requestText: string, sessionId?: string) =>
    api.post("/ai/nl-to-pr", { request_text: requestText, session_id: sessionId })
       .then(r => r.data),

  acceptPrDraft: (draftId: string) =>
    api.post(`/ai/nl-to-pr/${draftId}/accept`).then(r => r.data),

  // Vendor recommendations
  vendorRecommendations: (payload: {
    material_category: string;
    pr_id?: string;
    pr_title?: string;
    estimated_budget?: number;
    items_summary?: string;
    required_date?: string;
  }) => api.post("/ai/vendor-recommendations", payload).then(r => r.data),

  // Policy check
  policyCheck: (prId: string) =>
    api.post(`/ai/policy-check/${prId}`).then(r => r.data),

  // Approval summary
  approvalSummary: (prId: string) =>
    api.get(`/ai/approval-summary/${prId}`).then(r => r.data),

  regenerateApprovalSummary: (prId: string) =>
    api.post(`/ai/approval-summary/${prId}/regenerate`).then(r => r.data),

  // Analytics
  analyticsQuery: (question: string, sessionId?: string) =>
    api.post("/ai/analytics", { question, session_id: sessionId }).then(r => r.data),

  analyticsHistory: (limit = 20) =>
    api.get("/ai/analytics/history", { params: { limit } }).then(r => r.data),

  // Document intelligence
  documentExtract: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return api.post("/ai/document-extract", form, {
      headers: { "Content-Type": "multipart/form-data" },
    }).then(r => r.data);
  },

  linkExtraction: (extractionId: string, invoiceId: string) =>
    api.post(`/ai/document-extract/${extractionId}/link`, null, {
      params: { invoice_id: invoiceId },
    }).then(r => r.data),

  // Feedback
  submitFeedback: (interactionId: string, score: number, text?: string) =>
    api.patch(`/ai/feedback/${interactionId}`, { score, text }).then(r => r.data),

  // Status
  status: () => api.get("/ai/status").then(r => r.data),

  // Interaction history
  interactions: (capability?: string, limit = 20) =>
    api.get("/ai/interactions", { params: { capability, limit } }).then(r => r.data),
};
