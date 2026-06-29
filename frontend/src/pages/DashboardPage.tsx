/**
 * Dashboard page — uses shadcn/ui Badge, Table, Button, Slider components.
 *
 * Left column: connected repos list (GET /repos)
 * Right column: reviews table (GET /reviews) with filters + pagination
 *
 * All data comes from real API calls — no mock/hardcoded data.
 */

import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  GitBranch,
  ChevronLeft,
  ChevronRight,
  Circle,
  Loader2,
} from "lucide-react";
import type { RepoResponse, ReviewListItem } from "@/api/types";
import * as api from "@/api/client";
import type { ReviewFilters } from "@/api/client";
import { cn } from "@/lib/utils";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

const PAGE_SIZE = 10;

// Status filter options
const STATUS_FILTERS = [
  { value: "", label: "All" },
  { value: "accepted", label: "Accepted" },
  { value: "needs_human_review", label: "Needs Review" },
  { value: "error", label: "Failed" },
] as const;

// Decision → badge variant + label map
function getDecisionBadge(decision: string) {
  switch (decision) {
    case "accepted":
      return {
        label: "ACCEPTED",
        className: "bg-status-accepted/15 text-status-accepted border-status-accepted/30",
      };
    case "needs_human_review":
      return {
        label: "NEEDS REVIEW",
        className: "bg-status-review/15 text-status-review border-status-review/30",
      };
    case "error":
      return {
        label: "FAILED",
        className: "bg-status-error/15 text-status-error border-status-error/30",
      };
    default:
      return {
        label: decision.toUpperCase(),
        className: "bg-muted text-muted-foreground border-border",
      };
  }
}

// Webhook status → dot color
function getWebhookDotColor(status: string) {
  switch (status) {
    case "active":
      return "text-status-accepted";
    case "pending":
    case "scanning":
      return "text-status-review";
    case "error":
      return "text-status-error";
    default:
      return "text-muted-foreground";
  }
}

// Format relative time
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

// Extract repo short name from GitHub URL
function repoShortName(url: string): string {
  try {
    const parts = url.replace(/\.git$/, "").split("/");
    return parts.slice(-2).join("/");
  } catch {
    return url;
  }
}

export function DashboardPage() {
  const navigate = useNavigate();

  // Repos state
  const [repos, setRepos] = useState<RepoResponse[]>([]);
  const [reposLoading, setReposLoading] = useState(true);
  const [selectedRepoId, setSelectedRepoId] = useState<number | null>(null);

  // Reviews state
  const [reviews, setReviews] = useState<ReviewListItem[]>([]);
  const [reviewsLoading, setReviewsLoading] = useState(true);
  const [totalReviews, setTotalReviews] = useState(0);
  const [page, setPage] = useState(1);

  // Filters
  const [statusFilter, setStatusFilter] = useState("");
  const [minConfidence, setMinConfidence] = useState(0);

  // Fetch repos
  useEffect(() => {
    let cancelled = false;
    setReposLoading(true);
    api.listRepos().then((data) => {
      if (!cancelled) {
        setRepos(data.repos);
        setReposLoading(false);
      }
    }).catch(() => {
      if (!cancelled) setReposLoading(false);
    });
    return () => { cancelled = true; };
  }, []);

  // Fetch reviews (reactive to filters/page/repo)
  const fetchReviews = useCallback(async () => {
    setReviewsLoading(true);
    try {
      const filters: ReviewFilters = {
        page,
        page_size: PAGE_SIZE,
      };
      if (selectedRepoId) filters.repo_id = selectedRepoId;
      if (statusFilter) filters.decision = statusFilter;
      if (minConfidence > 0) filters.min_confidence = minConfidence / 100;

      const data = await api.listReviews(filters);
      setReviews(data.reviews);
      setTotalReviews(data.total);
    } catch {
      // silently handle
    } finally {
      setReviewsLoading(false);
    }
  }, [page, selectedRepoId, statusFilter, minConfidence]);

  useEffect(() => {
    fetchReviews();
  }, [fetchReviews]);

  // Reset to page 1 when filters change
  useEffect(() => {
    setPage(1);
  }, [selectedRepoId, statusFilter, minConfidence]);

  const totalPages = Math.ceil(totalReviews / PAGE_SIZE) || 1;

  return (
    <div className="flex h-full">
      {/* ===== Left Column: Repos ===== */}
      <div className="w-64 shrink-0 border-r border-border bg-card">
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Connected Repos
          </h2>
          <Badge variant="secondary" className="text-[10px]">
            {repos.length}
          </Badge>
        </div>

        <div className="space-y-0.5 p-2">
          {reposLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
          ) : repos.length === 0 ? (
            <p className="px-3 py-8 text-center text-xs text-muted-foreground">
              No repositories connected yet.
            </p>
          ) : (
            <>
              {/* "All" option */}
              <button
                onClick={() => setSelectedRepoId(null)}
                className={cn(
                  "flex w-full items-center justify-between rounded-lg px-3 py-2.5 text-left text-sm transition-colors",
                  selectedRepoId === null
                    ? "bg-primary/10 text-primary"
                    : "text-muted-foreground hover:bg-secondary hover:text-foreground"
                )}
              >
                <div className="flex items-center gap-2">
                  <GitBranch className="h-3.5 w-3.5" />
                  <span className="font-medium">All Repositories</span>
                </div>
              </button>

              {repos.map((repo) => (
                <button
                  key={repo.id}
                  onClick={() => setSelectedRepoId(repo.id)}
                  className={cn(
                    "flex w-full items-center justify-between rounded-lg px-3 py-2.5 text-left text-sm transition-colors",
                    selectedRepoId === repo.id
                      ? "bg-primary/10 text-primary"
                      : "text-muted-foreground hover:bg-secondary hover:text-foreground"
                  )}
                >
                  <div className="flex items-center gap-2 overflow-hidden">
                    <Circle
                      className={cn(
                        "h-2 w-2 shrink-0 fill-current",
                        getWebhookDotColor(repo.webhook_status)
                      )}
                    />
                    <div className="min-w-0">
                      <p className="truncate font-medium">
                        {repoShortName(repo.github_url)}
                      </p>
                      <p className="text-[10px] capitalize text-muted-foreground">
                        {repo.webhook_status}
                      </p>
                    </div>
                  </div>
                  <span className="ml-2 shrink-0 text-xs text-muted-foreground">
                    {repo.pr_count}
                  </span>
                </button>
              ))}
            </>
          )}
        </div>
      </div>

      {/* ===== Right Column: Reviews ===== */}
      <div className="flex-1 overflow-auto">
        {/* Header */}
        <div className="border-b border-border px-6 py-5">
          <h1 className="text-xl font-bold text-foreground">Active PR Reviews</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Monitor and manage autonomous agent insights
            {selectedRepoId
              ? ` for ${repoShortName(repos.find((r) => r.id === selectedRepoId)?.github_url ?? "")}`
              : " across all repositories"}
            .
          </p>
        </div>

        {/* Filters bar */}
        <div className="flex flex-wrap items-center gap-4 border-b border-border px-6 py-3">
          {/* Status chips */}
          <div className="flex items-center gap-1.5">
            <span className="mr-1 text-xs font-medium text-muted-foreground">
              Status:
            </span>
            {STATUS_FILTERS.map((sf) => (
              <Button
                key={sf.value}
                variant={statusFilter === sf.value ? "default" : "secondary"}
                size="xs"
                className="rounded-full"
                onClick={() => setStatusFilter(sf.value)}
              >
                {sf.label}
              </Button>
            ))}
          </div>

          {/* Confidence slider */}
          <div className="flex items-center gap-3">
            <span className="text-xs font-medium text-muted-foreground">
              Min Confidence:
            </span>
            <Slider
              value={[minConfidence]}
              onValueChange={(v) => setMinConfidence(v[0])}
              min={0}
              max={100}
              step={5}
              className="w-28"
            />
            <span className="w-8 text-right text-xs font-mono text-primary">
              {minConfidence}%
            </span>
          </div>
        </div>

        {/* Reviews table */}
        <div className="px-6 py-4">
          {reviewsLoading ? (
            <div className="flex items-center justify-center py-16">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : reviews.length === 0 ? (
            <div className="py-16 text-center text-sm text-muted-foreground">
              No reviews found matching your filters.
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Pull Request</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Confidence</TableHead>
                  <TableHead>Findings</TableHead>
                  <TableHead>Tests</TableHead>
                  <TableHead>Time</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {reviews.map((review) => {
                  const badge = getDecisionBadge(review.decision);
                  return (
                    <TableRow
                      key={review.id}
                      onClick={() => navigate(`/reviews/${review.id}`)}
                      className="cursor-pointer"
                    >
                      {/* PR info */}
                      <TableCell>
                        <p className="text-sm font-medium text-foreground">
                          {review.pr_title}
                        </p>
                        <p className="mt-0.5 text-xs text-muted-foreground">
                          <span className="font-mono">#{review.pr_number}</span>
                          {" · "}
                          {repoShortName(review.repo_name)}
                        </p>
                      </TableCell>

                      {/* Status badge */}
                      <TableCell>
                        <Badge
                          variant="outline"
                          className={cn(
                            "text-[10px] font-bold tracking-wider",
                            badge.className
                          )}
                        >
                          {badge.label}
                        </Badge>
                      </TableCell>

                      {/* Confidence */}
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <div className="h-1.5 w-16 overflow-hidden rounded-full bg-secondary">
                            <div
                              className={cn(
                                "h-full rounded-full transition-all",
                                review.confidence_score >= 0.8
                                  ? "bg-status-accepted"
                                  : review.confidence_score >= 0.5
                                    ? "bg-status-review"
                                    : "bg-status-error"
                              )}
                              style={{
                                width: `${Math.round(review.confidence_score * 100)}%`,
                              }}
                            />
                          </div>
                          <span className="text-xs font-mono text-muted-foreground">
                            {Math.round(review.confidence_score * 100)}%
                          </span>
                        </div>
                      </TableCell>

                      {/* Findings */}
                      <TableCell>
                        <span className="text-sm text-muted-foreground">
                          {review.findings_count}
                        </span>
                      </TableCell>

                      {/* Tests */}
                      <TableCell>
                        <span
                          className={cn(
                            "text-sm font-mono",
                            review.tests_total === 0
                              ? "text-muted-foreground"
                              : review.tests_passed === review.tests_total
                                ? "text-status-accepted"
                                : "text-status-error"
                          )}
                        >
                          {review.tests_total > 0
                            ? `${review.tests_passed}/${review.tests_total}`
                            : "—"}
                        </span>
                      </TableCell>

                      {/* Time */}
                      <TableCell className="text-xs text-muted-foreground">
                        {timeAgo(review.created_at)}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}

          {/* Pagination */}
          {totalReviews > 0 && (
            <div className="mt-4 flex items-center justify-between border-t border-border pt-4">
              <p className="text-xs text-muted-foreground">
                Showing {(page - 1) * PAGE_SIZE + 1}–
                {Math.min(page * PAGE_SIZE, totalReviews)} of {totalReviews}
              </p>
              <div className="flex items-center gap-1">
                <Button
                  variant="ghost"
                  size="icon-sm"
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                >
                  <ChevronLeft className="h-4 w-4" />
                </Button>

                {Array.from({ length: totalPages }, (_, i) => i + 1).map(
                  (pageNum) => (
                    <Button
                      key={pageNum}
                      variant={pageNum === page ? "default" : "ghost"}
                      size="icon-sm"
                      onClick={() => setPage(pageNum)}
                    >
                      {pageNum}
                    </Button>
                  )
                )}

                <Button
                  variant="ghost"
                  size="icon-sm"
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages}
                >
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
