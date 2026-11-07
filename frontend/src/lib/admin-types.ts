import type { GenerationPreset } from "./api-types";

export type AdminAccount = { id: string; username: string; is_owner: boolean; created_at: string };
export type AdminSession = { admin: AdminAccount; expires_in: number };

export type OverviewPoint = { date: string; users: number; generations: number; credits_spent: number };
export type AdminOverview = {
  users_total: number; users_blocked: number; users_new_24h: number; users_new_7d: number; users_new_30d: number;
  generations_total: number; generations_24h: number; generations_7d: number; generations_active: number;
  generations_by_status: Record<string, number>;
  credits_spent_24h: number; credits_spent_7d: number;
  revenue_total: string; revenue_30d: string; credits_sold_30d: number;
  payments_pending: number; promo_redemptions: number; daily: OverviewPoint[];
};

export type AdminUser = {
  id: string; first_name: string; last_name: string | null; username: string | null;
  google_email: string | null; telegram_id: number | null; photo_url: string | null;
  credits: number; is_blocked: boolean; registered_at: string; last_active_at: string | null;
  generations: number; credits_spent: number;
};
export type AdminUserPage = { items: AdminUser[]; total: number };

export type AdminGeneration = {
  id: string; user_id: string; user_name: string; user_email: string | null;
  workflow: string; prompt: string; status: string; credits_spent: number | null;
  seed: number | null; error: string | null; created_at: string; completed_at: string | null;
};
export type AdminGenerationPage = { items: AdminGeneration[]; total: number };

export type AdminPayment = {
  id: string; user_id: string; user_name: string; provider: string; status: string;
  credits: number; amount: string; paid_amount: string | null; currency: string;
  created_at: string; paid_at: string | null;
};
export type AdminPaymentPage = { items: AdminPayment[]; total: number };

export type AdminPromoCode = {
  id: string; code: string; credits: number; max_redemptions: number | null;
  redeemed_count: number; expires_at: string | null; is_active: boolean;
  created_at: string | null;
};

export type AdminRedemption = {
  id: string; user_id: string; user_name: string; user_email: string | null;
  credits: number; created_at: string;
};
export type AdminRedemptionPage = { items: AdminRedemption[]; total: number };

export type SystemSetting = {
  key: string; value: unknown; default: unknown; description: string;
  source: "default" | "database"; updated_at: string | null; updated_by: string | null;
};

export type AdminLora = {
  id: string; name: string; description: string | null;
  preview_urls: string[]; is_nsfw: boolean; workflow_count: number;
};
export type AdminLoraPage = { items: AdminLora[]; total: number };

export type Workflow = {
  id: string; name: string; description: string | null; generation_credits: number;
  is_active?: boolean;
  recommended_strengths?: Record<string, number>;
  loras: { id: string; name: string; description: string | null; preview_urls: string[]; is_nsfw: boolean }[];
};

export type AdminTeamPage = { items: AdminAccount[] };
export type AdminPresetPage = { items: GenerationPreset[]; total: number };
