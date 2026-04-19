import { useAuthStore } from "../store/authStore";

export default function DashboardPage() {
  const { user, logout } = useAuthStore();

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center gap-4">
      <h1 className="text-2xl font-bold text-slate-900">
        Welcome, {user?.first_name || user?.username}
      </h1>
      <p className="text-slate-500 text-sm">Dashboard — coming soon.</p>
      <button
        onClick={logout}
        className="mt-4 px-4 py-2 text-sm font-medium text-slate-600 border border-slate-300 rounded-lg hover:bg-slate-100 transition"
      >
        Sign out
      </button>
    </div>
  );
}
