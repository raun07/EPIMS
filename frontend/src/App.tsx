import { Navigate, Route, Routes } from "react-router-dom";
import { useAuthStore } from "@/store/authStore";
import { AppShell } from "@/components/layout/AppShell";

// Pages
import LoginPage from "@/pages/LoginPage";
import DashboardPage from "@/pages/DashboardPage";

// Procurement
import PRListPage from "@/pages/procurement/PRListPage";
import PRDetailPage from "@/pages/procurement/PRDetailPage";
import PRCreatePage from "@/pages/procurement/PRCreatePage";
import POListPage from "@/pages/procurement/POListPage";
import PODetailPage from "@/pages/procurement/PODetailPage";
import GRNCreatePage from "@/pages/procurement/GRNCreatePage";
import GRNDetailPage from "@/pages/procurement/GRNDetailPage";

// Invoice
import InvoiceListPage from "@/pages/invoice/InvoiceListPage";
import InvoiceDetailPage from "@/pages/invoice/InvoiceDetailPage";

// Inventory
import StockOverviewPage from "@/pages/inventory/StockOverviewPage";
import LowStockPage from "@/pages/inventory/LowStockPage";

// Reports
import ReportsDashboardPage from "@/pages/reports/ReportsDashboardPage";

// Master Data
import MaterialsPage from "@/pages/master/MaterialsPage";
import VendorsPage from "@/pages/master/VendorsPage";

// Approvals + Admin
import ApprovalQueuePage from "@/pages/approvals/ApprovalQueuePage";
import UsersPage from "@/pages/admin/UsersPage";

// AI Copilot
import AICopilotPage from "@/pages/ai/AICopilotPage";
import AIAnalyticsPage from "@/pages/ai/AIAnalyticsPage";
import AIDocumentsPage from "@/pages/ai/AIDocumentsPage";

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore();
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return <AppShell>{children}</AppShell>;
}

function R({ el }: { el: React.ReactNode }) {
  return <RequireAuth>{el}</RequireAuth>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      {/* Dashboard */}
      <Route path="/" element={<R el={<DashboardPage />} />} />

      {/* Procurement */}
      <Route path="/procurement/pr" element={<R el={<PRListPage />} />} />
      <Route path="/procurement/pr/new" element={<R el={<PRCreatePage />} />} />
      <Route path="/procurement/pr/:id" element={<R el={<PRDetailPage />} />} />
      <Route path="/procurement/po" element={<R el={<POListPage />} />} />
      <Route path="/procurement/po/:id" element={<R el={<PODetailPage />} />} />
      <Route path="/procurement/grn/new" element={<R el={<GRNCreatePage />} />} />
      <Route path="/procurement/grn/:id" element={<R el={<GRNDetailPage />} />} />

      {/* Invoices */}
      <Route path="/invoices" element={<R el={<InvoiceListPage />} />} />
      <Route path="/invoices/:id" element={<R el={<InvoiceDetailPage />} />} />

      {/* Inventory */}
      <Route path="/inventory/stock" element={<R el={<StockOverviewPage />} />} />
      <Route path="/inventory/alerts" element={<R el={<LowStockPage />} />} />

      {/* Reports */}
      <Route path="/reports/dashboard" element={<R el={<ReportsDashboardPage />} />} />

      {/* Master Data */}
      <Route path="/master/materials" element={<R el={<MaterialsPage />} />} />
      <Route path="/master/vendors" element={<R el={<VendorsPage />} />} />

      {/* Approvals */}
      <Route path="/approvals/queue" element={<R el={<ApprovalQueuePage />} />} />

      {/* Admin */}
      <Route path="/admin/users" element={<R el={<UsersPage />} />} />

      {/* AI Copilot */}
      <Route path="/ai/copilot" element={<R el={<AICopilotPage />} />} />
      <Route path="/ai/analytics" element={<R el={<AIAnalyticsPage />} />} />
      <Route path="/ai/documents" element={<R el={<AIDocumentsPage />} />} />

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
