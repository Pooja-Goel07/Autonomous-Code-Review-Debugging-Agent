/**
 * App root — React Router setup with auth protection.
 *
 * Routes:
 *   /login        — public, LoginPage
 *   /dashboard    — protected, DashboardPage
 *   /reviews/:id  — protected, ReviewDetailPage (placeholder)
 *   /analytics    — protected, AnalyticsPage (placeholder)
 *   /             — redirects to /dashboard
 */

import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "@/contexts/AuthContext";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { AppLayout } from "@/components/AppLayout";
import { LoginPage } from "@/pages/LoginPage";
import { DashboardPage } from "@/pages/DashboardPage";
import { ReviewDetailPage } from "@/pages/ReviewDetailPage";
import { AnalyticsPage } from "@/pages/AnalyticsPage";

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          {/* Public route */}
          <Route path="/login" element={<LoginPage />} />

          {/* Protected routes — wrapped in sidebar layout */}
          <Route element={<ProtectedRoute />}>
            <Route element={<AppLayout />}>
              <Route path="/dashboard" element={<DashboardPage />} />
              <Route path="/reviews/:id" element={<ReviewDetailPage />} />
              <Route path="/analytics" element={<AnalyticsPage />} />
            </Route>
          </Route>

          {/* Default redirect */}
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
