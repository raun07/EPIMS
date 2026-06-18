import api from "@/lib/api";
import type {
  PaginatedResponse,
  PRResponse,
  POResponse,
  GRNResponse,
  PRCreate,
  POCreate,
  GRNCreate,
} from "@/types";

// ── Purchase Requisitions ─────────────────────────────────────────────────────

export const prApi = {
  list: (params?: { page?: number; per_page?: number; status?: string; my_prs?: boolean }) =>
    api.get<PaginatedResponse<PRResponse>>("/purchase-requisitions", { params }).then((r) => r.data),

  get: (id: string) =>
    api.get<PRResponse>(`/purchase-requisitions/${id}`).then((r) => r.data),

  create: (data: PRCreate) =>
    api.post<PRResponse>("/purchase-requisitions", data).then((r) => r.data),

  update: (id: string, data: Partial<PRCreate>) =>
    api.put<PRResponse>(`/purchase-requisitions/${id}`, data).then((r) => r.data),

  submit: (id: string) =>
    api.post<PRResponse>(`/purchase-requisitions/${id}/submit`).then((r) => r.data),

  cancel: (id: string) =>
    api.post<PRResponse>(`/purchase-requisitions/${id}/cancel`).then((r) => r.data),

  reject: (id: string, reason: string) =>
    api
      .post<PRResponse>(`/purchase-requisitions/${id}/reject`, { reason })
      .then((r) => r.data),
};

// ── Purchase Orders ───────────────────────────────────────────────────────────

export const poApi = {
  list: (params?: { page?: number; per_page?: number; status?: string; vendor_id?: string }) =>
    api.get<PaginatedResponse<POResponse>>("/purchase-orders", { params }).then((r) => r.data),

  get: (id: string) =>
    api.get<POResponse>(`/purchase-orders/${id}`).then((r) => r.data),

  create: (data: POCreate) =>
    api.post<POResponse>("/purchase-orders", data).then((r) => r.data),

  update: (id: string, data: unknown) =>
    api.put<POResponse>(`/purchase-orders/${id}`, data).then((r) => r.data),

  submit: (id: string) =>
    api.post<POResponse>(`/purchase-orders/${id}/submit`).then((r) => r.data),

  release: (id: string) =>
    api.post<POResponse>(`/purchase-orders/${id}/release`).then((r) => r.data),

  cancel: (id: string) =>
    api.post<POResponse>(`/purchase-orders/${id}/cancel`).then((r) => r.data),
};

// ── Goods Receipts ────────────────────────────────────────────────────────────

export const grnApi = {
  list: (params?: { po_id?: string; page?: number; per_page?: number }) =>
    api.get<PaginatedResponse<GRNResponse>>("/goods-receipts", { params }).then((r) => r.data),

  get: (id: string) =>
    api.get<GRNResponse>(`/goods-receipts/${id}`).then((r) => r.data),

  create: (data: GRNCreate) =>
    api.post<GRNResponse>("/goods-receipts", data).then((r) => r.data),

  post: (id: string) =>
    api.post<GRNResponse>(`/goods-receipts/${id}/post`).then((r) => r.data),

  reverse: (id: string, reason: string) =>
    api
      .post<GRNResponse>(`/goods-receipts/${id}/reverse`, { reason })
      .then((r) => r.data),
};
