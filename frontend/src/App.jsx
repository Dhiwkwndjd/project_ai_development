import { Navigate, Route, Routes } from "react-router-dom";

import { ProtectedRoute, PublicOnlyRoute, RoleRoute } from "./auth/ProtectedRoute";
import AdminLogsPage from "./pages/AdminLogsPage";
import AdminPage from "./pages/AdminPage";
import AdminReportsPage from "./pages/AdminReportsPage";
import BookDetailPage from "./pages/BookDetailPage";
import CatalogPage from "./pages/CatalogPage";
import HomePage from "./pages/HomePage";
import LibrarianPage from "./pages/LibrarianPage";
import LoginPage from "./pages/LoginPage";
import MyLoansPage from "./pages/MyLoansPage";
import MyQueuePage from "./pages/MyQueuePage";
import RegisterPage from "./pages/RegisterPage";

const READER_ROLES = ["reader"];
const STAFF_ROLES = ["librarian", "admin"];
const ADMIN_ROLES = ["admin"];

export default function App() {
  return (
    <Routes>
      <Route element={<PublicOnlyRoute />}>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
      </Route>

      <Route element={<ProtectedRoute />}>
        <Route path="/" element={<HomePage />} />
        <Route path="/catalog" element={<CatalogPage />} />
        <Route path="/books/:id" element={<BookDetailPage />} />
      </Route>

      <Route element={<RoleRoute roles={READER_ROLES} />}>
        <Route path="/my" element={<MyLoansPage />} />
        <Route path="/my/queue" element={<MyQueuePage />} />
      </Route>

      <Route element={<RoleRoute roles={STAFF_ROLES} />}>
        <Route path="/librarian" element={<LibrarianPage />} />
      </Route>

      <Route element={<RoleRoute roles={ADMIN_ROLES} />}>
        <Route path="/admin" element={<AdminPage />} />
        <Route path="/admin/reports" element={<AdminReportsPage />} />
        <Route path="/admin/logs" element={<AdminLogsPage />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
