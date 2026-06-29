/**
 * Analytics page — placeholder for Stage 7.
 */

import { BarChart3 } from "lucide-react";

export function AnalyticsPage() {
  return (
    <div className="p-6">
      <div className="rounded-xl border border-border bg-card p-12 text-center">
        <BarChart3 className="mx-auto mb-4 h-10 w-10 text-muted-foreground" />
        <h1 className="text-lg font-bold text-foreground">
          Analytics Dashboard
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          This page will be built in Stage 7. It will show bugs caught per week,
          fix acceptance rate trends, confidence vs outcome scatter, and
          time-to-review comparisons.
        </p>
      </div>
    </div>
  );
}
