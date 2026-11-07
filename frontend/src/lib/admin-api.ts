import { ApiError, presetBody } from "./api";
import type {
  AdminGenerationPage, AdminLoraPage, AdminLora, AdminOverview, AdminPaymentPage,
  AdminPresetPage, AdminPromoCode, AdminRedemptionPage, AdminSession, AdminTeamPage,
  AdminUserPage, SystemSetting, Workflow,
} from "./admin-types";
import type { GenerationPreset, PresetPreview } from "./api-types";

const base = (process.env.NEXT_PUBLIC_API_URL || "/api").replace(/\/$/, "");
const csrfHeader = process.env.NEXT_PUBLIC_CSRF_HEADER_NAME || "X-CSRF-Token";

let csrf: string | null = null;
let bootstrapping: Promise<void> | null = null;
let refreshing: Promise<void> | null = null;

type Options = { method?: string; json?: unknown; body?: string; formData?: FormData; signal?: AbortSignal; retry?: boolean };

async function raw(path: string, options: Options = {}) {
  const method = options.method ?? "GET";
  const headers = new Headers();
  if (options.json !== undefined || options.body !== undefined) headers.set("Content-Type", "application/json");
  if (csrf && !["GET", "HEAD", "OPTIONS"].includes(method)) headers.set(csrfHeader, csrf);
  const response = await fetch(`${base}${path}`, {
    method,
    headers,
    credentials: "include",
    cache: "no-store",
    signal: options.signal,
    body: options.formData ?? options.body ?? (options.json === undefined ? undefined : JSON.stringify(options.json)),
  });
  const token = response.headers.get(csrfHeader);
  if (token) csrf = token;
  return response;
}

async function ensureCsrf(force = false) {
  if (csrf && !force) return;
  bootstrapping ??= (async () => {
    // Any response carries a fresh CSRF token; 401 is fine for a signed-out admin.
    await raw("/admins/me");
  })().finally(() => { bootstrapping = null; });
  await bootstrapping;
}

async function parse<T>(response: Response): Promise<T> {
  if (response.status === 204) return undefined as T;
  const text = await response.text();
  let value: unknown;
  try { value = text ? JSON.parse(text) : undefined; } catch { value = undefined; }
  if (!response.ok) {
    const detail = value && typeof value === "object" && "detail" in value ? (value as { detail?: unknown }).detail : null;
    const message = typeof detail === "string" ? detail
      : Array.isArray(detail) && detail.length ? "Please check the highlighted fields."
      : response.status === 401 ? "Session expired. Sign in again."
      : response.status === 403 ? "This action requires owner rights."
      : response.status === 429 ? "Too many requests. Please wait a moment."
      : `The request could not be completed (${response.status}).`;
    throw new ApiError(response.status, message);
  }
  if (value === undefined) throw new ApiError(502, "The API returned an invalid response.");
  return value as T;
}

async function refreshSession() {
  refreshing ??= (async () => {
    await ensureCsrf();
    const response = await raw("/admins/auth/refresh", { method: "POST" });
    if (!response.ok) throw new ApiError(response.status, "Session expired. Sign in again.");
  })().finally(() => { refreshing = null; });
  await refreshing;
}

async function request<T>(path: string, options: Options = {}): Promise<T> {
  const method = options.method ?? "GET";
  const mutating = !["GET", "HEAD", "OPTIONS"].includes(method);
  if (mutating) await ensureCsrf();
  let response = await raw(path, options);
  if (response.status === 401 && path !== "/admins/auth/login" && path !== "/admins/auth/refresh" && options.retry !== false) {
    await refreshSession();
    response = await raw(path, options);
  }
  if (response.status === 403 && mutating && !options.retry) {
    const clone = await response.clone().json().catch(() => null);
    if (clone?.detail === "CSRF validation failed") {
      await ensureCsrf(true);
      return request<T>(path, { ...options, retry: true });
    }
  }
  return parse<T>(response);
}

const query = (values: Record<string, string | number | undefined | null>) => {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(values)) {
    if (value !== undefined && value !== null && value !== "") search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : "";
};

export const adminApi = {
  login: (username: string, password: string) => request<AdminSession>("/admins/auth/login", { method: "POST", json: { username, password }, retry: false }),
  logout: () => request<void>("/admins/auth/logout", { method: "POST", retry: false }),
  me: () => request<AdminSession["admin"]>("/admins/me"),
  overview: (signal?: AbortSignal) => request<AdminOverview>("/admins/overview", { signal }),
  users: (values: { query?: string; state?: string; offset?: number; limit?: number }, signal?: AbortSignal) =>
    request<AdminUserPage>(`/admins/users${query({ ...values, limit: values.limit ?? 25 })}`, { signal }),
  setBlocked: (userId: string, isBlocked: boolean) =>
    request<{ user_id: string; is_blocked: boolean }>(`/admins/users/${encodeURIComponent(userId)}`, { method: "PATCH", json: { is_blocked: isBlocked } }),
  adjustCredits: (userId: string, amount: number, description: string) =>
    request<{ user_id: string; credits: number }>(`/admins/users/${encodeURIComponent(userId)}/credits`, { method: "POST", json: { amount, description } }),
  generations: (values: { state?: string; query?: string; offset?: number; limit?: number }, signal?: AbortSignal) =>
    request<AdminGenerationPage>(`/admins/generations${query({ ...values, limit: values.limit ?? 25 })}`, { signal }),
  payments: (values: { state?: string; provider?: string; offset?: number; limit?: number }, signal?: AbortSignal) =>
    request<AdminPaymentPage>(`/admins/payments${query({ ...values, limit: values.limit ?? 25 })}`, { signal }),
  promoCodes: (signal?: AbortSignal) => request<AdminPromoCode[]>("/admins/promo-codes?limit=100&offset=0", { signal }),
  createPromoCode: (values: { code: string; credits: number; max_redemptions: number | null; expires_at: string | null; is_active: boolean }) =>
    request<AdminPromoCode>("/admins/promo-codes", { method: "POST", json: values }),
  setPromoActive: (id: string, isActive: boolean) =>
    request<AdminPromoCode>(`/admins/promo-codes/${encodeURIComponent(id)}`, { method: "PATCH", json: { is_active: isActive } }),
  redemptions: (id: string, offset = 0, signal?: AbortSignal) =>
    request<AdminRedemptionPage>(`/admins/promo-codes/${encodeURIComponent(id)}/redemptions?limit=25&offset=${offset}`, { signal }),
  settings: (signal?: AbortSignal) => request<SystemSetting[]>("/admins/settings", { signal }),
  saveSetting: (key: string, value: unknown) =>
    request<SystemSetting>(`/admins/settings/${encodeURIComponent(key)}`, { method: "PATCH", json: { value } }),
  resetSetting: (key: string) =>
    request<SystemSetting>(`/admins/settings/${encodeURIComponent(key)}`, { method: "DELETE" }),
  workflows: async () => {
    const all: Workflow[] = [];
    for (let offset = 0; ; offset += 100) {
      const page = await request<Workflow[]>(`/admins/workflows?limit=100&offset=${offset}`);
      all.push(...page);
      if (page.length < 100) return all;
    }
  },
  setWorkflowCredits: (id: string, credits: number) =>
    request<Workflow>(`/admins/workflows/${encodeURIComponent(id)}/credits`, { method: "PATCH", json: { generation_credits: credits } }),
  createWorkflow: (values: { name: string; description: string | null; generation_credits: number; is_active: boolean }) =>
    request<Workflow>("/admins/workflows", { method: "POST", json: values }),
  updateWorkflow: (id: string, values: { description?: string | null; generation_credits?: number; is_active?: boolean }) =>
    request<Workflow>(`/admins/workflows/${encodeURIComponent(id)}`, { method: "PATCH", json: values }),
  deleteWorkflow: (id: string) =>
    request<void>(`/admins/workflows/${encodeURIComponent(id)}`, { method: "DELETE" }),
  setWorkflowLoras: (id: string, items: { lora_id: string; recommended_strength: number | null }[]) =>
    request<Workflow>(`/admins/workflows/${encodeURIComponent(id)}/loras`, { method: "PUT", json: { items } }),
  loras: (values: { query?: string; offset?: number; limit?: number }, signal?: AbortSignal) =>
    request<AdminLoraPage>(`/admins/loras${query({ ...values, limit: values.limit ?? 25 })}`, { signal }),
  allLoras: async () => {
    const all: AdminLora[] = [];
    for (let offset = 0; ; offset += 100) {
      const page = await request<AdminLoraPage>(`/admins/loras?limit=100&offset=${offset}`);
      all.push(...page.items);
      if (page.items.length < 100) return all;
    }
  },
  presets: (values: { query?: string; offset?: number; limit?: number }, signal?: AbortSignal) =>
    request<AdminPresetPage>(`/admins/presets${query({ ...values, limit: values.limit ?? 25 })}`, { signal }),
  createPreset: (values: { name: string; workflow_id: string; prompt: string; negative_prompt: string; description?: string; loras_strength: Record<string, number>; seed: string | null; is_public: boolean; preview_urls: string[] }) =>
    request<GenerationPreset>("/admins/presets", { method: "POST", body: presetBody(values) }),
  updatePreset: (id: string, values: { name?: string; workflow_id?: string; prompt?: string; negative_prompt?: string; description?: string; loras_strength?: Record<string, number>; seed?: string | null; is_public?: boolean; preview_urls?: string[] }) =>
    request<GenerationPreset>(`/admins/presets/${encodeURIComponent(id)}`, { method: "PATCH", body: presetBody(values) }),
  deletePreset: (id: string) =>
    request<void>(`/admins/presets/${encodeURIComponent(id)}`, { method: "DELETE" }),
  uploadPresetPreview: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<PresetPreview>("/admins/presets/previews", { method: "POST", formData: form });
  },
  uploadLoraPreview: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<PresetPreview>("/admins/loras/previews", { method: "POST", formData: form });
  },
  createLora: (values: { name: string; description: string | null; preview_urls: string[]; is_nsfw: boolean }) =>
    request<AdminLora>("/admins/loras", { method: "POST", json: values }),
  updateLora: (id: string, values: { description?: string | null; preview_urls?: string[]; is_nsfw?: boolean }) =>
    request<AdminLora>(`/admins/loras/${encodeURIComponent(id)}`, { method: "PATCH", json: values }),
  deleteLora: (id: string) =>
    request<void>(`/admins/loras/${encodeURIComponent(id)}`, { method: "DELETE" }),
  team: (signal?: AbortSignal) => request<AdminTeamPage>("/admins/team", { signal }),
  createTeamMember: (values: { username: string; password: string; is_owner: boolean }) =>
    request<AdminTeamPage["items"][number]>("/admins/team", { method: "POST", json: values }),
};
