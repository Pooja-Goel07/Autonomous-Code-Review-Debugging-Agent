/**
 * Login page — matches the wireframe centered auth card.
 *
 * Shows a username/password form (placeholder for GitHub OAuth).
 * After successful login, shows a "Connect Repository" panel.
 * Calls POST /auth/login and POST /repos from Stage 4.
 */

import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { Zap, LogIn, Loader2, CheckCircle, AlertCircle, Plus } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import * as api from "@/api/client";

export function LoginPage() {
  const { isAuthenticated, login, isLoading, error } = useAuth();
  const navigate = useNavigate();

  // Login form state
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  // Connect repo state
  const [repoUrl, setRepoUrl] = useState("");
  const [repoLoading, setRepoLoading] = useState(false);
  const [repoSuccess, setRepoSuccess] = useState<string | null>(null);
  const [repoError, setRepoError] = useState<string | null>(null);

  async function handleLogin(e: FormEvent) {
    e.preventDefault();
    try {
      await login(username, password);
    } catch {
      // Error is already set in AuthContext
    }
  }

  async function handleConnectRepo(e: FormEvent) {
    e.preventDefault();
    if (!repoUrl.trim()) return;

    setRepoLoading(true);
    setRepoError(null);
    setRepoSuccess(null);
    try {
      const repo = await api.createRepo(repoUrl.trim());
      setRepoSuccess(`Connected: ${repo.github_url}`);
      setRepoUrl("");
    } catch (err) {
      if (err instanceof api.ApiError) {
        setRepoError(err.message);
      } else {
        setRepoError("Failed to connect repository");
      }
    } finally {
      setRepoLoading(false);
    }
  }

  function handleGoToDashboard() {
    navigate("/dashboard");
  }

  // ---- Not logged in: show login form ----
  if (!isAuthenticated) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background px-4">
        <div className="w-full max-w-md space-y-8">
          {/* Logo + tagline */}
          <div className="text-center">
            <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/20">
              <Zap className="h-7 w-7 text-primary" />
            </div>
            <h1 className="text-2xl font-bold text-foreground">
              Autonomous Agent
            </h1>
            <p className="mt-1 text-lg font-semibold text-foreground">
              Code Quality, Automated.
            </p>
            <p className="mt-2 text-sm text-muted-foreground">
              High-fidelity pull request analysis and autonomous debugging
              for modern engineering teams.
            </p>
          </div>

          {/* Login card */}
          <div className="rounded-xl border border-border bg-card p-6 shadow-lg shadow-black/20">
            <h2 className="mb-1 text-center text-lg font-semibold text-foreground">
              Sign in to continue
            </h2>
            <p className="mb-6 text-center text-sm text-muted-foreground">
              Enter your credentials to access the dashboard.
            </p>

            <form onSubmit={handleLogin} className="space-y-4">
              <div>
                <label
                  htmlFor="username"
                  className="mb-1 block text-sm font-medium text-foreground"
                >
                  Username
                </label>
                <input
                  id="username"
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                  placeholder="admin"
                  className="w-full rounded-lg border border-input bg-secondary px-3 py-2.5 text-sm text-foreground placeholder-muted-foreground outline-none transition-colors focus:border-primary focus:ring-1 focus:ring-primary"
                />
              </div>

              <div>
                <label
                  htmlFor="password"
                  className="mb-1 block text-sm font-medium text-foreground"
                >
                  Password
                </label>
                <input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  placeholder="********"
                  className="w-full rounded-lg border border-input bg-secondary px-3 py-2.5 text-sm text-foreground placeholder-muted-foreground outline-none transition-colors focus:border-primary focus:ring-1 focus:ring-primary"
                />
              </div>

              {error && (
                <div className="flex items-center gap-2 rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">
                  <AlertCircle className="h-4 w-4 shrink-0" />
                  {error}
                </div>
              )}

              <button
                type="submit"
                disabled={isLoading}
                className="flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-50"
              >
                {isLoading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <LogIn className="h-4 w-4" />
                )}
                {isLoading ? "Signing in..." : "Sign In"}
              </button>
            </form>

            <p className="mt-4 text-center text-xs text-muted-foreground">
              GitHub OAuth coming soon. Use admin / admin123 for now.
            </p>
          </div>
        </div>
      </div>
    );
  }

  // ---- Logged in: show Connect Repo + Go to Dashboard ----
  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="w-full max-w-md space-y-6">
        {/* Success header */}
        <div className="text-center">
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-status-accepted/20">
            <CheckCircle className="h-6 w-6 text-status-accepted" />
          </div>
          <h1 className="text-xl font-bold text-foreground">Welcome back!</h1>
          <p className="text-sm text-muted-foreground">
            You're signed in. Connect a repository or go to the dashboard.
          </p>
        </div>

        {/* Connect repo card */}
        <div className="rounded-xl border border-border bg-card p-6 shadow-lg shadow-black/20">
          <h2 className="mb-4 text-sm font-semibold text-foreground">
            Connect a Repository
          </h2>

          <form onSubmit={handleConnectRepo} className="space-y-3">
            <input
              type="url"
              value={repoUrl}
              onChange={(e) => setRepoUrl(e.target.value)}
              placeholder="https://github.com/org/repo"
              className="w-full rounded-lg border border-input bg-secondary px-3 py-2.5 text-sm text-foreground placeholder-muted-foreground outline-none transition-colors focus:border-primary focus:ring-1 focus:ring-primary"
            />

            {repoError && (
              <div className="flex items-center gap-2 rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">
                <AlertCircle className="h-4 w-4 shrink-0" />
                {repoError}
              </div>
            )}

            {repoSuccess && (
              <div className="flex items-center gap-2 rounded-lg bg-status-accepted/10 px-3 py-2 text-sm text-status-accepted">
                <CheckCircle className="h-4 w-4 shrink-0" />
                {repoSuccess}
              </div>
            )}

            <button
              type="submit"
              disabled={repoLoading || !repoUrl.trim()}
              className="flex w-full items-center justify-center gap-2 rounded-lg border border-border bg-secondary px-4 py-2.5 text-sm font-medium text-foreground transition-colors hover:bg-accent disabled:opacity-50"
            >
              {repoLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Plus className="h-4 w-4" />
              )}
              Connect Repository
            </button>
          </form>
        </div>

        {/* Go to dashboard */}
        <button
          onClick={handleGoToDashboard}
          className="flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-4 py-3 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90"
        >
          Go to Dashboard
        </button>
      </div>
    </div>
  );
}
