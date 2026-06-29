/**
 * Login page — uses shadcn/ui Card, Button, Input components.
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

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

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
          <Card className="shadow-lg shadow-black/20">
            <CardHeader className="text-center">
              <CardTitle>Sign in to continue</CardTitle>
              <CardDescription>
                Enter your credentials to access the dashboard.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleLogin} className="space-y-4">
                <div>
                  <label
                    htmlFor="username"
                    className="mb-1.5 block text-sm font-medium text-foreground"
                  >
                    Username
                  </label>
                  <Input
                    id="username"
                    type="text"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    required
                    placeholder="admin"
                  />
                </div>

                <div>
                  <label
                    htmlFor="password"
                    className="mb-1.5 block text-sm font-medium text-foreground"
                  >
                    Password
                  </label>
                  <Input
                    id="password"
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    placeholder="********"
                  />
                </div>

                {error && (
                  <div className="flex items-center gap-2 rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">
                    <AlertCircle className="h-4 w-4 shrink-0" />
                    {error}
                  </div>
                )}

                <Button
                  type="submit"
                  disabled={isLoading}
                  className="w-full"
                  size="lg"
                >
                  {isLoading ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <LogIn className="h-4 w-4" />
                  )}
                  {isLoading ? "Signing in..." : "Sign In"}
                </Button>
              </form>

              <p className="mt-4 text-center text-xs text-muted-foreground">
                GitHub OAuth coming soon. Use admin / admin123 for now.
              </p>
            </CardContent>
          </Card>
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
        <Card className="shadow-lg shadow-black/20">
          <CardHeader>
            <CardTitle className="text-sm">Connect a Repository</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleConnectRepo} className="space-y-3">
              <Input
                type="url"
                value={repoUrl}
                onChange={(e) => setRepoUrl(e.target.value)}
                placeholder="https://github.com/org/repo"
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

              <Button
                type="submit"
                variant="outline"
                disabled={repoLoading || !repoUrl.trim()}
                className="w-full"
              >
                {repoLoading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Plus className="h-4 w-4" />
                )}
                Connect Repository
              </Button>
            </form>
          </CardContent>
        </Card>

        {/* Go to dashboard */}
        <Button
          onClick={handleGoToDashboard}
          className="w-full"
          size="lg"
        >
          Go to Dashboard
        </Button>
      </div>
    </div>
  );
}
