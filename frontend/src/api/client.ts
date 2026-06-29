/**
 * Typed API client wrapping fetch calls to the backend.
 *
 * JWT token is stored in a module-level variable (in-memory only).
 * No localStorage, sessionStorage, or cookies — per security practice.
 * The token is set by AuthContext on login and cleared on logout.
 */

import type {
  TokenResponse,
  UserResponse,
  RepoListResponse,
  RepoResponse,
  ReviewListResponse,
  ReviewDetailResponse,
} from "./types";

// In-memory token storage — never persisted to browser storage APIs
let _accessToken: string | null = null;

export function setToken(token: string | null) {
  _accessToken = token;
}

export function getToken(): string | null {
  return _accessToken;
}

// Base URL — Vite dev proxy rewrites /api/* to http://localhost:8000/*
const BASE_URL = "/api";

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> || {}),
  };

  if (_accessToken) {
    headers["Authorization"] = `Bearer ${_accessToken}`;
  }

  const response = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    const message = errorBody.detail || `Request failed: ${response.status}`;
    throw new ApiError(response.status, message);
  }

  return response.json() as Promise<T>;
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

// ---- Auth ----

export async function login(
  username: string,
  password: string
): Promise<TokenResponse> {
  return request<TokenResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
}

export async function getMe(): Promise<UserResponse> {
  return request<UserResponse>("/auth/me");
}

// ---- Repos ----

export async function listRepos(): Promise<RepoListResponse> {
  return request<RepoListResponse>("/repos");
}

export async function getRepo(id: number): Promise<RepoResponse> {
  return request<RepoResponse>(`/repos/${id}`);
}

export async function createRepo(githubUrl: string): Promise<RepoResponse> {
  return request<RepoResponse>("/repos", {
    method: "POST",
    body: JSON.stringify({ github_url: githubUrl }),
  });
}

// ---- Reviews ----

export interface ReviewFilters {
  repo_id?: number;
  decision?: string;
  min_confidence?: number;
  page?: number;
  page_size?: number;
}

export async function listReviews(
  filters: ReviewFilters = {}
): Promise<ReviewListResponse> {
  const params = new URLSearchParams();
  if (filters.repo_id != null) params.set("repo_id", String(filters.repo_id));
  if (filters.decision) params.set("decision", filters.decision);
  if (filters.min_confidence != null)
    params.set("min_confidence", String(filters.min_confidence));
  if (filters.page != null) params.set("page", String(filters.page));
  if (filters.page_size != null)
    params.set("page_size", String(filters.page_size));

  const qs = params.toString();
  return request<ReviewListResponse>(`/reviews${qs ? `?${qs}` : ""}`);
}

export async function getReview(id: number): Promise<ReviewDetailResponse> {
  return request<ReviewDetailResponse>(`/reviews/${id}`);
}

export async function rerunReview(
  id: number
): Promise<{ status: string; review_id: number; message: string }> {
  return request(`/reviews/${id}/rerun`, { method: "POST" });
}
