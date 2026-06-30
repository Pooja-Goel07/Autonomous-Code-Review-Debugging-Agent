/**
 * DiffViewer — renders a unified diff with line-by-line coloring.
 *
 * - Lines starting with '+' → green (added)
 * - Lines starting with '-' → red (removed)
 * - All other lines → muted context
 *
 * Used in ReviewDetailPage for displaying proposed_fix.diff_text.
 */

import { FileCode2, FileQuestion } from "lucide-react";
import { cn } from "@/lib/utils";

import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { ProposedFixResponse } from "@/api/types";

interface DiffViewerProps {
  proposedFixes: ProposedFixResponse[];
}

function classifyLine(line: string) {
  if (line.startsWith("+")) return "added";
  if (line.startsWith("-")) return "removed";
  return "context";
}

function DiffBlock({ fix }: { fix: ProposedFixResponse }) {
  const lines = fix.diff_text.split("\n");

  return (
    <div className="space-y-3">
      {/* Reasoning */}
      {fix.reasoning_text && (
        <div className="rounded-lg bg-primary/5 px-3 py-2">
          <p className="text-xs font-medium text-primary">Agent reasoning:</p>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {fix.reasoning_text}
          </p>
        </div>
      )}

      {/* Acceptance status */}
      <div className="flex items-center gap-2">
        <span
          className={cn(
            "inline-flex rounded-full px-2 py-0.5 text-[10px] font-bold tracking-wider",
            fix.accepted
              ? "bg-status-accepted/15 text-status-accepted"
              : "bg-status-review/15 text-status-review"
          )}
        >
          {fix.accepted ? "ACCEPTED" : "PENDING"}
        </span>
      </div>

      {/* Diff lines */}
      <div className="overflow-hidden rounded-lg border border-border">
        <ScrollArea className="max-h-80">
          <div className="font-mono text-xs leading-relaxed">
            {lines.map((line, i) => {
              const type = classifyLine(line);
              return (
                <div
                  key={i}
                  className={cn(
                    "flex",
                    type === "added" && "bg-status-accepted/10",
                    type === "removed" && "bg-status-error/10"
                  )}
                >
                  {/* Line number gutter */}
                  <span className="w-8 shrink-0 select-none border-r border-border px-1.5 py-0.5 text-right text-muted-foreground/50">
                    {i + 1}
                  </span>

                  {/* Line content */}
                  <span
                    className={cn(
                      "flex-1 whitespace-pre px-3 py-0.5",
                      type === "added" && "text-status-accepted",
                      type === "removed" && "text-status-error",
                      type === "context" && "text-muted-foreground"
                    )}
                  >
                    {line}
                  </span>
                </div>
              );
            })}
          </div>
        </ScrollArea>
      </div>
    </div>
  );
}

export function DiffViewer({ proposedFixes }: DiffViewerProps) {
  // Empty state — no proposed fixes
  if (!proposedFixes || proposedFixes.length === 0) {
    return (
      <Card className="flex h-full flex-col">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-sm">
            <FileCode2 className="h-4 w-4 text-primary" />
            Diff Viewer
          </CardTitle>
        </CardHeader>
        <CardContent className="flex flex-1 flex-col items-center justify-center gap-3 py-8">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-muted">
            <FileQuestion className="h-6 w-6 text-muted-foreground" />
          </div>
          <div className="text-center">
            <p className="text-sm font-medium text-muted-foreground">
              No fix proposed yet
            </p>
            <p className="mt-1 text-xs text-muted-foreground/70">
              The agent didn't generate a proposed fix for this review.
              This may indicate the review is pending, errored, or the
              issues require human judgement.
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  // Has fixes — render each one
  return (
    <Card className="flex h-full flex-col">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <FileCode2 className="h-4 w-4 text-primary" />
          Proposed Fix{proposedFixes.length > 1 ? "es" : ""}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {proposedFixes.map((fix) => (
          <DiffBlock key={fix.id} fix={fix} />
        ))}
      </CardContent>
    </Card>
  );
}
