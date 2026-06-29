/**
 * PR Review Detail page — placeholder for Stage 6.
 */

import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft } from "lucide-react";

export function ReviewDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  return (
    <div className="p-6">
      <button
        onClick={() => navigate("/dashboard")}
        className="mb-6 flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Dashboard
      </button>

      <div className="rounded-xl border border-border bg-card p-12 text-center">
        <h1 className="text-lg font-bold text-foreground">
          Review #{id} — Detail View
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          This page will be built in Stage 6. It will show the full reasoning
          trace, diff viewer, call graph, and proposed fix.
        </p>
      </div>
    </div>
  );
}
