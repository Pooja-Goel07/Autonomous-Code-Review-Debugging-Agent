/**
 * PR Review Detail — Stage 6a header + 6b diff viewer.
 *
 * Fetches real review data from GET /reviews/{id}.
 * Header: PR title, repo/branch, status badge, confidence mini-meter,
 *         and Re-run Review button (wired to POST /reviews/{id}/rerun).
 * Left column: DiffViewer showing proposed_fix.diff_text.
 * Center/Right columns: placeholders for Stages 6c–6d.
 */

import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  RefreshCw,
  Loader2,
  GitPullRequest,
  AlertCircle,
} from "lucide-react";
import type { ReviewDetailResponse } from "@/api/types";
import * as api from "@/api/client";
import { cn } from "@/lib/utils";
import { DiffViewer } from "@/components/DiffViewer";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

// Decision → badge style
function getDecisionBadge(decision: string) {
  switch (decision) {
    case "accepted":
      return {
        label: "ACCEPTED",
        className:
          "bg-status-accepted/15 text-status-accepted border-status-accepted/30",
      };
    case "needs_human_review":
      return {
        label: "NEEDS REVIEW",
        className:
          "bg-status-review/15 text-status-review border-status-review/30",
      };
    case "error":
      return {
        label: "FAILED",
        className:
          "bg-status-error/15 text-status-error border-status-error/30",
      };
    default:
      return {
        label: decision.toUpperCase(),
        className: "bg-muted text-muted-foreground border-border",
      };
  }
}

// Extract repo short name from GitHub URL
function repoShortName(url: string): string {
  try {
    const parts = url.replace(/\.git$/, "").split("/");
    return parts.slice(-2).join("/");
  } catch {
    return url;
  }
}

// Relative time helper
function timeAgo(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);

  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins}m ago`;

  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;

  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 7) return `${diffDays}d ago`;

  return date.toLocaleDateString();
}

/**
 * Circular confidence mini-meter.
 * Renders a ring with a colored arc proportional to the confidence score.
 */
function ConfidenceMeter({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const radius = 20;
  const stroke = 4;
  const circumference = 2 * Math.PI * radius;
  const dashOffset = circumference * (1 - score);

  const color =
    score >= 0.8
      ? "var(--color-status-accepted)"
      : score >= 0.5
        ? "var(--color-status-review)"
        : "var(--color-status-error)";

  return (
    <div className="relative flex items-center justify-center" title={`${pct}% confidence`}>
      <svg width="52" height="52" className="-rotate-90">
        {/* Background ring */}
        <circle
          cx="26"
          cy="26"
          r={radius}
          fill="none"
          stroke="var(--color-secondary)"
          strokeWidth={stroke}
        />
        {/* Filled arc */}
        <circle
          cx="26"
          cy="26"
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={dashOffset}
          className="transition-all duration-500"
        />
      </svg>
      <span className="absolute text-xs font-bold text-foreground">{pct}%</span>
    </div>
  );
}

export function ReviewDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const reviewId = Number(id);

  // Review data
  const [review, setReview] = useState<ReviewDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Rerun state
  const [rerunning, setRerunning] = useState(false);
  const [rerunMessage, setRerunMessage] = useState<string | null>(null);

  // Fetch review
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    api
      .getReview(reviewId)
      .then((data) => {
        if (!cancelled) {
          setReview(data);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof api.ApiError ? err.message : "Failed to load review");
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [reviewId]);

  // Handle rerun
  async function handleRerun() {
    setRerunning(true);
    setRerunMessage(null);
    try {
      const result = await api.rerunReview(reviewId);
      setRerunMessage(result.message || "Re-run queued successfully");
    } catch (err) {
      setRerunMessage(
        err instanceof api.ApiError ? err.message : "Re-run failed"
      );
    } finally {
      setRerunning(false);
    }
  }

  // Loading state
  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  // Error state
  if (error || !review) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-4">
        <AlertCircle className="h-10 w-10 text-destructive" />
        <p className="text-sm text-muted-foreground">{error ?? "Review not found"}</p>
        <Button variant="outline" onClick={() => navigate("/dashboard")}>
          <ArrowLeft className="h-4 w-4" />
          Back to Dashboard
        </Button>
      </div>
    );
  }

  const badge = getDecisionBadge(review.decision);

  return (
    <div className="flex h-full flex-col overflow-hidden">
      {/* ===== Header ===== */}
      <header className="shrink-0 border-b border-border bg-card px-6 py-4">
        {/* Back link */}
        <Button
          variant="ghost"
          size="sm"
          className="mb-3 -ml-2 text-muted-foreground"
          onClick={() => navigate("/dashboard")}
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Dashboard
        </Button>

        <div className="flex items-start justify-between gap-4">
          {/* Left: PR info */}
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-3">
              <GitPullRequest className="h-5 w-5 shrink-0 text-primary" />
              <h1 className="truncate text-lg font-bold text-foreground">
                {review.pr_title}
              </h1>
            </div>

            <div className="mt-1.5 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
              <span className="font-mono">#{review.pr_number}</span>
              <span className="text-border">•</span>
              <span>{repoShortName(review.repo_name)}</span>
              <span className="text-border">•</span>
              <span>{timeAgo(review.created_at)}</span>
              <span className="text-border">•</span>
              <span>
                {review.findings.length} finding{review.findings.length !== 1 ? "s" : ""}
              </span>
              <span className="text-border">•</span>
              <span>
                {review.test_runs.length} test run{review.test_runs.length !== 1 ? "s" : ""}
              </span>
            </div>

            {/* Rerun feedback */}
            {rerunMessage && (
              <p className="mt-2 text-xs text-muted-foreground">{rerunMessage}</p>
            )}
          </div>

          {/* Right: confidence meter + status badge + rerun button */}
          <div className="flex items-center gap-4">
            <ConfidenceMeter score={review.confidence_score} />

            <Badge
              variant="outline"
              className={cn(
                "text-[10px] font-bold tracking-wider",
                badge.className
              )}
            >
              {badge.label}
            </Badge>

            <Button
              variant="outline"
              size="sm"
              onClick={handleRerun}
              disabled={rerunning}
            >
              {rerunning ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <RefreshCw className="h-4 w-4" />
              )}
              {rerunning ? "Running..." : "Re-run Review"}
            </Button>
          </div>
        </div>
      </header>

      {/* ===== Three-column body ===== */}
      <div className="flex-1 overflow-auto p-6">
        <div className="grid grid-cols-3 gap-4" style={{ minHeight: "400px" }}>
          {/* Column 1: Diff Viewer (Stage 6b) */}
          <DiffViewer proposedFixes={review.proposed_fixes} />

          {/* Column 2: Reasoning Trace */}
          <Card className="flex flex-col">
            <CardHeader>
              <CardTitle className="text-sm">Reasoning Trace</CardTitle>
              <CardDescription>Stage 6c</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-1 items-center justify-center">
              <p className="text-center text-xs text-muted-foreground">
                Step-by-step LLM reasoning chain and decision explanation will be
                built in Stage 6c.
              </p>
            </CardContent>
          </Card>

          {/* Column 3: Findings / Tests / Call Graph */}
          <Card className="flex flex-col">
            <CardHeader>
              <CardTitle className="text-sm">
                Findings / Tests / Call Graph
              </CardTitle>
              <CardDescription>Stage 6d</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-1 items-center justify-center">
              <p className="text-center text-xs text-muted-foreground">
                Findings list, test results, proposed fixes, and call graph
                visualization will be built in Stage 6d.
              </p>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
