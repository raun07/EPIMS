// ── Auth ──────────────────────────────────────────────────────────────────────

export interface LoginRequest {
  email: string;
  password: string;
}

export interface UserBrief {
  id: string;
  email: string;
  full_name: string;
  roles: string[];
  permissions: string[];
  is_superuser: boolean;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: UserBrief;
}

export interface UserResponse {
  id: string;
  employee_id: string;
  email: string;
  full_name: string;
  department: string | null;
  cost_center: string | null;
  manager_id: string | null;
  is_active: boolean;
  is_superuser: boolean;
  roles: string[];
}

// ── Shared ────────────────────────────────────────────────────────────────────

export interface PaginationMeta {
  page: number;
  per_page: number;
  total: number;
  total_pages: number;
  has_next: boolean;
  has_prev: boolean;
}

export interface PaginatedResponse<T> {
  success: boolean;
  data: T[];
  meta: PaginationMeta;
}

// ── Procurement ───────────────────────────────────────────────────────────────

export interface PRItemCreate {
  description: string;
  quantity: number;
  material_id?: string;
  uom_id?: string;
  estimated_price?: number;
  required_date?: string;
}

export interface PRCreate {
  title: string;
  description?: string;
  priority?: string;
  required_date?: string;
  cost_center?: string;
  department?: string;
  warehouse_id?: string;
  notes?: string;
  items: PRItemCreate[];
}

export interface PRItemResponse {
  id: string;
  line_number: number;
  description: string;
  quantity: string;
  estimated_price: string | null;
  estimated_value: string | null;
  currency: string;
  status: string;
  material_id: string | null;
  uom_id: string | null;
}

export interface PRResponse {
  id: string;
  pr_number: string;
  title: string;
  description: string | null;
  status: string;
  priority: string;
  required_date: string | null;
  cost_center: string | null;
  department: string | null;
  total_value: string;
  currency: string;
  notes: string | null;
  rejection_reason: string | null;
  submitted_at: string | null;
  approved_at: string | null;
  created_at: string;
  requested_by: string;
  items: PRItemResponse[];
}

export interface POItemCreate {
  description: string;
  quantity: number;
  unit_price: number;
  material_id?: string;
  uom_id?: string;
  pr_item_id?: string;
  discount_pct?: number;
  tax_pct?: number;
  delivery_date?: string;
}

export interface POCreate {
  vendor_id: string;
  pr_id?: string;
  po_type?: string;
  delivery_date?: string;
  warehouse_id?: string;
  payment_terms?: string;
  notes?: string;
  items: POItemCreate[];
}

export interface POItemResponse {
  id: string;
  line_number: number;
  description: string;
  quantity: string;
  unit_price: string;
  discount_pct: string;
  tax_pct: string;
  net_value: string;
  qty_received: string;
  qty_invoiced: string;
  status: string;
  material_id: string | null;
  delivery_date: string | null;
}

export interface POResponse {
  id: string;
  po_number: string;
  vendor_id: string;
  pr_id: string | null;
  status: string;
  po_type: string;
  order_date: string;
  delivery_date: string | null;
  payment_terms: string | null;
  currency: string;
  subtotal: string;
  tax_amount: string;
  discount_amount: string;
  total_amount: string;
  notes: string | null;
  created_by: string | null;
  created_at: string;
  items: POItemResponse[];
}

export interface GRNItemCreate {
  po_item_id?: string;
  material_id?: string;
  quantity_delivered: number;
  quantity_accepted?: number;
  storage_location_id?: string;
  batch_number?: string;
  inspection_note?: string;
  rejection_reason?: string;
}

export interface GRNCreate {
  po_id: string;
  warehouse_id: string;
  receipt_date?: string;
  delivery_note?: string;
  notes?: string;
  items: GRNItemCreate[];
}

export interface GRNItemResponse {
  id: string;
  line_number: number;
  material_id: string | null;
  quantity_delivered: string;
  quantity_accepted: string;
  quantity_rejected: string;
  unit_price: string | null;
  net_value: string | null;
  batch_number: string | null;
  storage_location_id: string | null;
  inspection_note: string | null;
  rejection_reason: string | null;
}

export interface GRNResponse {
  id: string;
  grn_number: string;
  po_id: string;
  vendor_id: string | null;
  warehouse_id: string;
  status: string;
  receipt_date: string;
  delivery_note: string | null;
  total_value: string;
  currency: string;
  posted_by: string | null;
  posted_at: string | null;
  created_at: string;
  items: GRNItemResponse[];
}

// ── Invoice ───────────────────────────────────────────────────────────────────

export interface InvoiceItemResponse {
  id: string;
  line_number: number;
  description: string | null;
  quantity: string;
  unit_price: string;
  net_value: string;
  match_flag: string | null;
  variance_pct: string | null;
}

export interface InvoiceResponse {
  id: string;
  invoice_number: string;
  vendor_invoice_number: string | null;
  vendor_id: string;
  po_id: string | null;
  status: string;
  invoice_date: string;
  due_date: string | null;
  currency: string;
  subtotal: string;
  tax_amount: string;
  total_amount: string;
  paid_amount: string;
  match_status: string | null;
  dispute_reason: string | null;
  notes: string | null;
  verified_at: string | null;
  created_at: string;
  items: InvoiceItemResponse[];
}

export interface ThreeWayMatchResponse {
  invoice_id: string;
  po_id: string | null;
  grn_id: string | null;
  match_result: string;
  price_variance: string | null;
  qty_variance: string | null;
  value_variance: string | null;
  tolerance_pct: string | null;
  notes: string | null;
  checked_at: string;
}

// ── Inventory ─────────────────────────────────────────────────────────────────

export interface StockResponse {
  id: string;
  material_id: string;
  warehouse_id: string;
  storage_location_id: string | null;
  batch_number: string | null;
  stock_type: string;
  quantity: string;
  valuation_price: string | null;
  currency: string;
  total_value: string;
  last_movement_date: string | null;
}

export interface StockMovementResponse {
  id: string;
  movement_number: string;
  movement_type: string;
  movement_date: string;
  material_id: string;
  quantity: string;
  unit_price: string | null;
  total_value: string | null;
  currency: string;
  reference_doc_type: string | null;
  reference_doc_id: string | null;
  batch_number: string | null;
  created_at: string;
}

export interface LowStockAlert {
  material_id: string;
  material_number: string | null;
  warehouse_id: string;
  warehouse_code: string | null;
  current_qty: number;
  reorder_point: number;
  deficit: number;
}

// ── Master Data ───────────────────────────────────────────────────────────────

export interface MaterialResponse {
  id: string;
  material_number: string;
  description: string;
  material_type: string;
  standard_price: string | null;
  moving_average_price: string | null;
  reorder_point: string | null;
  lead_time_days: number | null;
  is_active: boolean;
  currency: string;
}

export interface VendorResponse {
  id: string;
  vendor_number: string;
  name: string;
  short_name: string | null;
  vendor_type: string;
  gst_number: string | null;
  email: string | null;
  phone: string | null;
  payment_terms: string;
  credit_limit: string | null;
  currency: string;
  status: string;
  rating: string | null;
}

// ── Reports ───────────────────────────────────────────────────────────────────

export interface DashboardKPIs {
  pending_pr_approvals: number;
  open_po_value: number;
  overdue_invoices: number;
  low_stock_alerts: number;
}

export interface StatusBucket {
  status: string;
  count: number;
  total_value: number;
  avg_approval_hours?: number | null;
}

export interface PRSummary {
  by_status: StatusBucket[];
}

export interface POSummary {
  by_status: StatusBucket[];
}

export interface VendorPerformance {
  vendor_id: string;
  vendor_number: string;
  name: string;
  po_count: number;
  total_spend: number;
  avg_rating: number;
}

export interface WarehouseValuation {
  code: string;
  name: string;
  line_count: number;
  total_value: number;
}

export interface InventoryValuation {
  warehouses: WarehouseValuation[];
  grand_total: number;
}

export interface AgingEntry {
  invoice_number: string;
  invoice_date: string | null;
  due_date: string | null;
  balance: number;
  days_overdue: number;
}

export interface InvoiceAging {
  bucket: string;
  count: number;
  total_balance: number;
  invoices: AgingEntry[];
}
