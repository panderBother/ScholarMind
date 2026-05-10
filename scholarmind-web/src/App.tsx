import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "@/components/layout/AppShell";
import { ChatPage } from "@/pages/ChatPage";
import { DocumentsPage } from "@/pages/DocumentsPage";
import { EvalDashboardPage } from "@/pages/EvalDashboardPage";
import { KnowledgeBasesPage } from "@/pages/KnowledgeBasesPage";
import { LoginPage } from "@/pages/LoginPage";
import { ReportPage } from "@/pages/ReportPage";
import { ReportsIndexPage } from "@/pages/ReportsIndexPage";
import { SettingsPage } from "@/pages/SettingsPage";
import { ToolsPage } from "@/pages/ToolsPage";

/**
 * 顶层路由：
 * - 登录页独立全屏布局
 * - 其余业务页共用 AppShell（左侧主导航 + 内容区）
 */
export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<AppShell />}>
        <Route path="/" element={<Navigate to="/chat" replace />} />
        <Route path="/chat" element={<ChatPage />} />
        <Route path="/knowledge-bases" element={<KnowledgeBasesPage />} />
        <Route path="/documents" element={<DocumentsPage />} />
        <Route path="/reports" element={<ReportsIndexPage />} />
        <Route path="/reports/:id" element={<ReportPage />} />
        <Route path="/evaluation" element={<EvalDashboardPage />} />
        <Route path="/tools" element={<ToolsPage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/chat" replace />} />
    </Routes>
  );
}
