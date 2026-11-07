export type User = {
  id: string; first_name: string; last_name: string | null; username: string | null;
  telegram_id: number | null; google_email: string | null; photo_url: string | null;
  is_premium: boolean | null; allows_write_to_pm: boolean | null; added_to_attachment_menu: boolean | null;
  credits: number; referral_code: string; registered_at: string;
};
export type AuthProvider = "google" | "telegram";
export type AuthChallenge = { nonce: string; client_id: string; expires_in: number };
export type UserSession = { user: User; expires_in: number; is_new_user: boolean };
export type Lora = { id: string; name: string; description: string | null; preview_urls: string[]; is_nsfw: boolean };
export type Workflow = { id: string; name: string; description: string | null; generation_credits: number; loras: Lora[]; recommended_strengths?: Record<string, number> };
export type Generation = {
  id: string; workflow_id: string; prompt: string; negative_prompt: string; loras_strength: Record<string, number>;
  uploaded_images: number;
  status: "pending" | "queued" | "processing" | "completed" | "failed" | "cancelled" | "timed_out";
  seed: string | null; error: string | null; credits_spent: number | null;
  completed_at: string | null; created_at: string;
};
export type GenerationInput = { workflow_id: string; prompt: string; negative_prompt?: string; images?: string[]; loras_strength?: Record<string, number>; seed?: string };
export type PresetType = "user" | "admin";
export type GenerationPreset = {
  id: string; user_id: string | null; type: PresetType;
  name: string; workflow_id: string; prompt: string; negative_prompt: string; description: string;
  loras_strength: Record<string, number>; seed: string | null;
  is_public: boolean; preview_urls: string[];
  favorites_count: number; is_favorite: boolean;
  likes_count: number; is_liked: boolean; is_saved: boolean;
  created_at: string | null; updated_at: string | null;
};
export type PresetFavorite = { favorites_count: number; is_favorite: boolean };
export type PresetLike = { likes_count: number; is_liked: boolean };
export type PresetSave = { is_saved: boolean };
export type PresetPreview = { id: string; url: string };
export type PresetInput = {
  name: string; workflow_id: string; prompt: string; negative_prompt: string;
  description?: string;
  loras_strength: Record<string, number>; seed?: string;
  is_public?: boolean; preview_urls?: string[];
};
export type PaymentProvider = "atlos" | "telegram_stars";
export type Payment = {
  id: string; provider: PaymentProvider;
  status: "pending" | "processing" | "succeeded" | "failed" | "expired" | "cancelled" | "refunded";
  credits: number; amount: string; currency: string; checkout_url: string | null;
  expires_at: string | null; paid_at: string | null; created_at: string;
};
export type PaymentPrices = { crypto_price_per_credit: string | null; crypto_currency: string; stars_price_per_credit: number | null; crypto_min_amount: string; stars_min_amount: number };
export type ReferralStats = { referral_code: string; invited_count: number; credits_earned: number; referrer_credits: number; invitee_credits: number; pending_count: number };
export type PromoRedemption = { code: string; credits: number; balance: number };
