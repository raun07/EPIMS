import api from "@/lib/api";
import type {
  InvoiceResponse,
  ThreeWayMatchResponse,
  StockResponse,
  StockMovementResponse,
  LowStockAlert,
  MaterialResponse,
  VendorResponse,
  DashboardKPIs,
  PRSummary,
  POSummary,
  VendorPerformance,
  InventoryValuation,
  InvoiceAging,
} from "@/types";

// ── Inventory ─────────────────────────────────────────────────────────────────

export const inventoryApi = {
  materialStock: (materialId: string) =>
    api.get<StockResponse[]>(`/inventory/materials/${materialId}/stock`).then((r) => r.data),

  warehouseStock: (warehouseId: string) =>
    api.get<StockResponse[]>(`/inventory/warehouses/${warehouseId}/stock`).then((r) => r.data),

  lowStockAlerts: () =>
    api.get<LowStockAlert[]>("/inventory/alerts/low-stock").then((r) => r.data),

  movements: (materialId: string, params?: { page?: number; per_page?: number }) =>
    api
      .get<StockMovementResponse[]>(`/inventory/materials/${materialId}/movements`, { params })
      .then((r) => r.data),

  transfer: (data: unknown) =>
    api.post<StockMovementResponse>("/inventory/transfer", data).then((r) => r.data),

  issue: (data: unknown) =>
    api.post<StockMovementResponse>("/inventory/issue", data).then((r) => r.data),

  initialStock: (data: unknown) =>
    api.post<StockMovementResponse>("/inventory/initial-stock", data).then((r) => r.data),
};

// ── Invoices ──────────────────────────────────────────────────────────────────

export const invoiceApi = {
  list: (params?: { page?: number; per_page?: number; status?: string; vendor_id?: string }) =>
    api.get<{ data: InvoiceResponse[]; meta: unknown }>("/invoices", { params }).then((r) => r.data),

  get: (id: string) =>
    api.get<InvoiceResponse>(`/invoices/${id}`).then((r) => r.data),

  create: (data: unknown) =>
    api.post<InvoiceResponse>("/invoices", data).then((r) => r.data),

  verify: (id: string, force = false) =>
    api
      .post<ThreeWayMatchResponse>(`/invoices/${id}/verify`, null, { params: { force } })
      .then((r) => r.data),

  override: (id: string, reason: string) =>
    api.post<InvoiceResponse>(`/invoices/${id}/override`, { reason }).then((r) => r.data),

  markPaid: (id: string, paidAmount: number) =>
    api
      .post<InvoiceResponse>(`/invoices/${id}/payment`, { paid_amount: paidAmount })
      .then((r) => r.data),
};

// ── Master Data ───────────────────────────────────────────────────────────────

export const masterApi = {
  materials: {
    list: (params?: { page?: number; per_page?: number; q?: string }) =>
      api.get<{ data: MaterialResponse[]; meta: unknown }>("/materials", { params }).then((r) => r.data),
    get: (id: string) =>
      api.get<MaterialResponse>(`/materials/${id}`).then((r) => r.data),
    create: (data: unknown) =>
      api.post<MaterialResponse>("/materials", data).then((r) => r.data),
    update: (id: string, data: unknown) =>
      api.put<MaterialResponse>(`/materials/${id}`, data).then((r) => r.data),
  },
  vendors: {
    list: (params?: { page?: number; per_page?: number; q?: string; status?: string }) =>
      api.get<{ data: VendorResponse[]; meta: unknown }>("/vendors", { params }).then((r) => r.data),
    get: (id: string) =>
      api.get<VendorResponse>(`/vendors/${id}`).then((r) => r.data),
    create: (data: unknown) =>
      api.post<VendorResponse>("/vendors", data).then((r) => r.data),
    update: (id: string, data: unknown) =>
      api.put<VendorResponse>(`/vendors/${id}`, data).then((r) => r.data),
    block: (id: string, reason: string) =>
      api.post<VendorResponse>(`/vendors/${id}/block`, { reason }).then((r) => r.data),
    unblock: (id: string) =>
      api.post<VendorResponse>(`/vendors/${id}/unblock`).then((r) => r.data),
  },
};

// ── Reports ───────────────────────────────────────────────────────────────────

export const reportsApi = {
  dashboard: () =>
    api.get<DashboardKPIs>("/reports/dashboard").then((r) => r.data),

  prSummary: (params?: { from_date?: string; to_date?: string; department?: string }) =>
    api.get<PRSummary>("/reports/pr-summary", { params }).then((r) => r.data),

  poSummary: (params?: { from_date?: string; to_date?: string }) =>
    api.get<POSummary>("/reports/po-summary", { params }).then((r) => r.data),

  vendorPerformance: (limit = 10) =>
    api.get<VendorPerformance[]>("/reports/vendor-performance", { params: { limit } }).then((r) => r.data),

  inventoryValuation: () =>
    api.get<InventoryValuation>("/reports/inventory-valuation").then((r) => r.data),

  invoiceAging: () =>
    api.get<InvoiceAging[]>("/reports/invoice-aging").then((r) => r.data),

  triggerExport: (reportType: string, format = "xlsx") =>
    api.post<{ task_id: string }>("/reports/exports", null, {
      params: { report_type: reportType, format },
    }).then((r) => r.data),
};
