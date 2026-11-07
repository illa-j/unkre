import type { AuthChallenge, AuthProvider, Generation, GenerationInput, GenerationPreset, Payment, PaymentPrices, PaymentProvider, PresetFavorite, PresetInput, PresetLike, PresetPreview, PresetSave, PromoRedemption, ReferralStats, User, UserSession, Workflow } from "./api-types";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) { super(message); this.status = status; this.name = "ApiError"; }
}

export function errorMessage(error: unknown) {
  return error instanceof ApiError ? error.message : "Could not reach the studio. Please try again.";
}

export function parseApiJson(text: string): unknown {
  let previous = "";
  let seed = false;
  const normalized = text.replace(/"(?:\\.|[^"\\])*"|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|[{}\[\]:,]|true|false|null/g, token => {
    const isSeed = seed;
    seed = token === ":" && previous === '"seed"';
    previous = token;
    return isSeed && /^\d+$/.test(token) ? JSON.stringify(token) : token;
  });
  return JSON.parse(normalized);
}

export function presetBody<T extends { seed?: string | null }>(input: T) {
  const { seed, ...values } = input;
  const json = JSON.stringify(values);
  if (seed === undefined) return json;
  if (seed === null) return `${json.slice(0, -1)},"seed":null}`;
  if (!/^\d+$/.test(seed) || BigInt(seed) > BigInt("9223372036854775807")) {
    throw new ApiError(422, "Seed must be a whole number between 0 and 9223372036854775807.");
  }
  return `${json.slice(0, -1)},"seed":${BigInt(seed).toString()}}`;
}

export function generationBody<T extends { seed?: string }>(input: T) {
  const { seed, ...values } = input;
  if (seed !== undefined && (!/^\d+$/.test(seed) || BigInt(seed) > BigInt("9223372036854775807"))) {
    throw new ApiError(422, "Seed must be a whole number between 0 and 9223372036854775807.");
  }
  const json = JSON.stringify(values);
  return seed === undefined ? json : `${json.slice(0, -1)},"seed":${BigInt(seed).toString()}}`;
}

type Options = { method?: string; json?: unknown; body?: string; formData?: FormData; signal?: AbortSignal; authenticate?: boolean; csrf?: boolean };

export function createApiClient(baseUrl: string, fetcher: typeof fetch = (...args) => fetch(...args)) {
  const base = baseUrl.replace(/\/$/, "");
  const csrfHeader = process.env.NEXT_PUBLIC_CSRF_HEADER_NAME || "X-CSRF-Token";
  let csrf: string | null = null;
  let bootstrap: Promise<void> | null = null;
  let refresh: Promise<void> | null = null;
  let sessionVersion = 0;
  const url = (path: string) => `${base}${path}`;

  async function raw(path: string, options: Options = {}) {
    const method = options.method ?? "GET";
    const headers = new Headers();
    if (options.json !== undefined || options.body !== undefined) headers.set("Content-Type", "application/json");
    if (csrf && !["GET", "HEAD", "OPTIONS"].includes(method)) headers.set(csrfHeader, csrf);
    const response = await fetcher(url(path), {
      method, headers, credentials: "include", cache: "no-store", signal: options.signal,
      body: options.formData ?? options.body ?? (options.json !== undefined ? JSON.stringify(options.json) : undefined),
    });
    const token = response.headers.get(csrfHeader);
    if (token) csrf = token;
    return response;
  }

  async function ensureCsrf(force = false) {
    if (csrf && !force) return;
    bootstrap ??= (async () => {
      const response = await raw("/users/session");
      if (!response.ok && response.status !== 401) await unwrap(response);
    })().finally(() => { bootstrap = null; });
    await bootstrap;
  }

  async function unwrap<T>(response: Response): Promise<T> {
    if (response.status === 204) return undefined as T;
    const text = await response.text();
    let value: unknown;
    try { value = text ? parseApiJson(text) : undefined; } catch { value = undefined; }
    if (!response.ok) {
      const detail = value && typeof value === "object" && "detail" in value ? value.detail : null;
      const message = typeof detail === "string" ? detail : response.status === 422 ? "Please check the details and try again." : response.status === 429 ? "Too many requests. Please wait a moment." : `The request could not be completed (${response.status}).`;
      throw new ApiError(response.status, message);
    }
    if (value === undefined) throw new ApiError(502, "The studio returned an invalid response.");
    return value as T;
  }

  async function renewSession() {
    refresh ??= (async () => {
      await ensureCsrf();
      await unwrap<UserSession>(await raw("/users/auth/refresh", { method: "POST" }));
      sessionVersion += 1;
    })().finally(() => { refresh = null; });
    await refresh;
  }

  async function request<T>(path: string, options: Options = {}): Promise<T> {
    if (options.csrf !== false && options.method && !["GET", "HEAD", "OPTIONS"].includes(options.method)) await ensureCsrf();
    const version = sessionVersion;
    let response = await raw(path, options);
    if (response.status === 401 && options.authenticate !== false) {
      if (sessionVersion === version) await renewSession();
      response = await raw(path, options);
    }
    if (response.status === 403 && options.method && options.method !== "GET") {
      const value = await response.clone().json().catch(() => null);
      if (value?.detail === "CSRF validation failed") {
        await ensureCsrf(true);
        response = await raw(path, options);
      }
    }
    return unwrap<T>(response);
  }

  return {
    request, url,
    me: () => request<User>("/users/me"),
    session: () => request<User | null>("/users/session"),
    challenge: (provider: AuthProvider) => request<AuthChallenge>("/users/auth/challenge", { method: "POST", json: { provider }, authenticate: false }),
    login: (provider: AuthProvider, id_token: string, nonce: string, referral_code?: string) => request<UserSession>(`/users/auth/${provider}`, { method: "POST", json: { id_token, nonce, ...(referral_code ? { referral_code } : {}) }, authenticate: false }),
    miniappLogin: (init_data: string, referral_code?: string) => request<UserSession>("/users/auth/telegram-webapp", { method: "POST", json: { init_data, ...(referral_code ? { referral_code } : {}) }, authenticate: false, csrf: false }),
    linkAccount: (provider: AuthProvider, id_token: string, nonce: string) => request<User>(`/users/links/${provider}`, { method: "POST", json: { id_token, nonce } }),
    logout: () => request<void>("/users/auth/logout", { method: "POST", authenticate: false }),
    workflows: async () => {
      const all: Workflow[] = [];
      for (let offset = 0; ; offset += 100) {
        const page = await request<Workflow[]>(`/workflows?limit=100&offset=${offset}`);
        all.push(...page);
        if (page.length < 100) return all;
      }
    },
    generations: (offset = 0, signal?: AbortSignal) => request<Generation[]>(`/generations?limit=24&offset=${offset}`, { signal }),
    generation: (id: string) => request<Generation>(`/generations/${encodeURIComponent(id)}`),
    createGeneration: (input: GenerationInput) => request<Generation>("/generations", { method: "POST", body: generationBody(input) }),
    deleteGeneration: (id: string) => request<void>(`/generations/${encodeURIComponent(id)}`, { method: "DELETE" }),
    presets: () => request<GenerationPreset[]>("/presets?limit=100&offset=0"),
    preset: (id: string) => request<GenerationPreset>(`/presets/${encodeURIComponent(id)}`),
    favoritePreset: (id: string) => request<PresetFavorite>(`/presets/${encodeURIComponent(id)}/favorite`, { method: "PUT" }),
    unfavoritePreset: (id: string) => request<PresetFavorite>(`/presets/${encodeURIComponent(id)}/favorite`, { method: "DELETE" }),
    likePreset: (id: string) => request<PresetLike>(`/presets/${encodeURIComponent(id)}/like`, { method: "PUT" }),
    unlikePreset: (id: string) => request<PresetLike>(`/presets/${encodeURIComponent(id)}/like`, { method: "DELETE" }),
    savePreset: (id: string) => request<PresetSave>(`/presets/${encodeURIComponent(id)}/save`, { method: "PUT" }),
    unsavePreset: (id: string) => request<PresetSave>(`/presets/${encodeURIComponent(id)}/save`, { method: "DELETE" }),
    createPreset: (input: PresetInput) => request<GenerationPreset>("/presets", { method: "POST", body: generationBody(input) }),
    uploadPresetPreview: (file: File) => {
      const form = new FormData();
      form.append("file", file);
      return request<PresetPreview>("/presets/previews", { method: "POST", formData: form });
    },
    updatePreset: (id: string, input: Partial<Omit<PresetInput, "seed">> & { seed?: string | null }) => request<GenerationPreset>(`/presets/${encodeURIComponent(id)}`, { method: "PATCH", body: presetBody(input) }),
    deletePreset: (id: string) => request<void>(`/presets/${encodeURIComponent(id)}`, { method: "DELETE" }),
    image: async (id: string, signal?: AbortSignal) => {
      const path = `/generations/${encodeURIComponent(id)}/image`;
      let response = await raw(path, { signal });
      if (response.status === 401) { await renewSession(); response = await raw(path, { signal }); }
      if (!response.ok) await unwrap(response);
      return response.blob();
    },
    prices: () => request<PaymentPrices>("/payments/prices"),
    payments: (provider: PaymentProvider, offset = 0) => request<Payment[]>(`/payments?provider=${provider}&limit=20&offset=${offset}`),
    payment: (provider: PaymentProvider, id: string) => request<Payment>(`/payments/${encodeURIComponent(id)}?provider=${provider}`),
    createPayment: (provider: PaymentProvider, credits: number, idempotency_key: string) => request<Payment>(`/payments/${provider === "atlos" ? "crypto" : "stars"}`, { method: "POST", json: { credits, idempotency_key } }),
    referral: () => request<ReferralStats>("/referrals"),
    redeemPromo: (code: string) => request<PromoRedemption>("/promos/redeem", { method: "POST", json: { code } }),
  };
}

export const api = createApiClient(process.env.NEXT_PUBLIC_API_URL || "/api");
