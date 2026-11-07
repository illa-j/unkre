"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { api, errorMessage } from "@/lib/api";
import type { Payment, PaymentProvider } from "@/lib/api-types";
import { creditsForPrice, multiplyPrice, safeCheckoutUrl } from "@/lib/payments";
import { useApiData } from "@/lib/use-api-data";
import { useSession } from "../session-provider";
import { useTelegramMiniApp } from "../telegram-miniapp";
import { SessionNotice } from "./session-notice";
import { StudioIcon } from "./studio-icon";
import { Select } from "@/components/ui/select";

const activePayment = (payment: Payment) => ["pending", "processing"].includes(payment.status);
const hasPendingPayments = (payments: Payment[]) => payments.some(activePayment);

export function Credits() {
  const session = useSession();
  const telegram = useTelegramMiniApp();
  const [provider, setProvider] = useState<PaymentProvider>("atlos");
  const [creditsInput, setCreditsInput] = useState("100");
  const [priceInput, setPriceInput] = useState("");
  const [offset, setOffset] = useState(0);
  const [invoice, setInvoice] = useState<{ user: string; payment: Payment } | null>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");
  const [promo, setPromo] = useState("");
  const [promoBusy, setPromoBusy] = useState(false);
  const [promoNote, setPromoNote] = useState("");
  const key = useRef<{ fingerprint: string; value: string } | null>(null);
  const submitting = useRef(false);
  const creditsRef = useRef(creditsInput);
  const prices = useApiData(session.user?.id ?? null, api.prices);
  const loadHistory = useCallback(() => api.payments(provider, offset), [provider, offset]);
  const history = useApiData(session.user ? `${session.user.id}:${provider}:${offset}` : null, loadHistory, 10000, hasPendingPayments);
  const activeInvoice = invoice && invoice.user === session.user?.id ? invoice.payment : null;
  const loadInvoice = useCallback(() => api.payment(activeInvoice!.provider, activeInvoice!.id), [activeInvoice]);
  const tracked = useApiData(activeInvoice && session.user ? `${session.user.id}:${activeInvoice.id}` : null, loadInvoice, 5000, activePayment);
  const current = tracked.data ?? activeInvoice;
  const paid = current?.status === "succeeded";
  const invoiceFinished = Boolean(current && !activePayment(current));
  const reloadUser = session.reloadUser;
  const reloadHistory = history.reload;
  useEffect(() => { if (paid) { void reloadUser(); reloadHistory(); } }, [paid, reloadUser, reloadHistory]);
  // Keep the key while an invoice is active so retries are idempotent. Once it
  // reaches a terminal state, the next purchase must be a new order.
  useEffect(() => { if (invoiceFinished) key.current = null; }, [invoiceFinished]);
  const unit = provider === "atlos" ? prices.data?.crypto_price_per_credit : prices.data?.stars_price_per_credit?.toString();
  const credits = Number(creditsInput);
  const creditsValid = Number.isSafeInteger(credits) && credits >= 1 && credits <= 1_000_000;
  const total = unit && creditsValid ? multiplyPrice(unit, credits) : null;
  const currency = provider === "atlos" ? prices.data?.crypto_currency ?? "" : "Stars";
  const minimum = provider === "atlos" ? prices.data?.crypto_min_amount ?? "1" : prices.data?.stars_min_amount ?? 100;
  const minimumLabel = `${minimum} ${currency}`;
  const meetsMinimum = total !== null && Number(total) >= Number(minimum);
  const checkout = current?.checkout_url ? safeCheckoutUrl(current.checkout_url) : null;
  useEffect(() => { creditsRef.current = creditsInput; }, [creditsInput]);
  useEffect(() => {
    const value = Number(creditsRef.current);
    setPriceInput(unit && Number.isSafeInteger(value) && value >= 1 && value <= 1_000_000 ? multiplyPrice(unit, value) ?? "" : "");
  }, [unit]);

  function changeCredits(value: string) {
    setCreditsInput(value);
    const next = Number(value);
    setPriceInput(unit && Number.isSafeInteger(next) && next >= 1 && next <= 1_000_000 ? multiplyPrice(unit, next) ?? "" : "");
  }

  function changePrice(value: string) {
    setPriceInput(value);
    if (!unit) { setCreditsInput(""); return; }
    const next = creditsForPrice(value, unit);
    setCreditsInput(next !== null && next <= 1_000_000 ? String(next) : "");
  }

  function normalizeCredits() {
    if (!creditsValid) return;
    setCreditsInput(String(credits));
    if (unit) setPriceInput(multiplyPrice(unit, credits) ?? "");
  }

  function normalizePrice() {
    if (unit && creditsValid) setPriceInput(multiplyPrice(unit, credits) ?? "");
  }

  async function redeemPromo(event: FormEvent) {
    event.preventDefault();
    if (!session.user) { session.openLogin(); return; }
    const code = promo.trim();
    if (!code || promoBusy) return;
    setPromoBusy(true); setPromoNote("");
    try {
      const result = await api.redeemPromo(code);
      setPromo("");
      setPromoNote(`${result.credits} credits added. Your balance is now ${result.balance}.`);
      await session.reloadUser();
    } catch (error) { setPromoNote(errorMessage(error)); }
    finally { setPromoBusy(false); }
  }

  function openCheckout(url: string, paymentProvider: PaymentProvider) {
    if (paymentProvider === "telegram_stars" && telegram.openInvoice(url, status => {
      if (status !== "paid") return;
      void session.reloadUser();
      history.reload();
    })) return;
    if (telegram.inTelegram && telegram.openLink(url)) return;
    window.location.assign(url);
  }

  async function purchase(event: FormEvent) {
    event.preventDefault();
    if (!session.user) { session.openLogin(); return; }
    if (!unit || !creditsValid || !meetsMinimum || submitting.current) return;
    const fingerprint = `${session.user.id}:${provider}:${credits}`;
    if (key.current?.fingerprint !== fingerprint) key.current = { fingerprint, value: crypto.randomUUID() };
    submitting.current = true; setBusy(true); setNote("");
    try {
      const payment = await api.createPayment(provider, credits, key.current.value);
      const checkoutUrl = payment.checkout_url ? safeCheckoutUrl(payment.checkout_url) : null;
      history.reload();
      if (checkoutUrl) {
        setInvoice({ user: session.user.id, payment });
        openCheckout(checkoutUrl, payment.provider);
        return;
      }
      setInvoice({ user: session.user.id, payment });
    } catch (error) { setNote(errorMessage(error)); }
    finally { submitting.current = false; setBusy(false); }
  }

  return <>
    <div className="studio-page-heading"><div><h1>Credits &amp; plans</h1><p>Check your balance, add credits and review payments.</p></div><Link className="studio-text-link" href="/studio/referrals">Invite friends <StudioIcon name="arrow" size={17} /></Link></div>
    <SessionNotice />
    <section className="studio-credit-overview"><div className="studio-credit-hero"><span className="studio-eyebrow">YOUR CREDIT BALANCE</span><div><strong>{session.loading ? "…" : session.user?.credits ?? "—"}</strong><span>credits<small>{session.user ? "Available in your account" : "Sign in to view your balance"}</small></span></div><p>Your balance updates after payment is confirmed.</p><span className="studio-credit-decoration" aria-hidden="true">✳</span></div><form className="studio-panel studio-credit-status" onSubmit={purchase}><h2>Keep creating.</h2><div className="studio-field"><span>Payment method</span><Select ariaLabel="Payment method" value={provider} disabled={busy} options={[{ value: "atlos", label: "Crypto — USDT, BTC, ETH" }, { value: "telegram_stars", label: "Telegram Stars — cards via Telegram" }]} onChange={value => { setProvider(value as PaymentProvider); setOffset(0); setNote(""); }} /></div><p className="studio-field-note">{provider === "atlos" ? "You’ll be redirected to the secure ATLOS checkout. Credits are added after the network confirms the transaction." : "Cards via Telegram: pay with a bank card, Apple Pay or Google Pay inside Telegram. Credits arrive as soon as Telegram confirms the payment."}</p><label className="studio-field"><span>Credits</span><input type="number" min="1" max="1000000" step="1" required value={creditsInput} disabled={busy} onChange={event => changeCredits(event.target.value)} onBlur={normalizeCredits} /></label>
      <label className="studio-field"><span>Price <small>Minimum {minimumLabel}</small></span><div className="studio-price-input"><input aria-label="Price" type="number" min={minimum} step={provider === "atlos" ? "any" : 1} inputMode="decimal" required value={priceInput} disabled={busy || !unit} onChange={event => changePrice(event.target.value)} onBlur={normalizePrice} /><span>{currency}</span></div></label>
      {prices.loading ? <p role="status">Loading prices…</p> : prices.error ? <p role="alert">{prices.error}</p> : <p className="studio-field-note studio-payment-summary">{unit ? `1 credit = ${unit} ${currency}.${total ? meetsMinimum ? ` You pay ${total} ${currency} for ${credits.toLocaleString("en-US")} credits.` : ` Minimum payment is ${minimumLabel}.` : " Enter a whole number of credits or a price."}` : session.user ? "This payment method is currently unavailable." : "Sign in to see current prices."}</p>}
      <button type="submit" className="studio-button studio-button-primary studio-button-full" disabled={busy || session.loading || Boolean(session.user && (!total || !meetsMinimum))}>{busy ? "Opening checkout…" : "Continue to payment"}<StudioIcon name="arrow" size={17} /></button>
    </form></section>
    {current && <section className="studio-panel studio-payment-invoice"><h2>{paid ? "Your credits are ready." : "Your payment"}</h2><span className="studio-tag">{current.status.replaceAll("_", " ")}</span><p>{current.credits} credits · {current.amount} {current.currency}</p>{current.expires_at && <p className="studio-field-note">Expires {new Date(current.expires_at).toLocaleString()}</p>}{checkout && ["pending", "processing"].includes(current.status) && (telegram.inTelegram
      ? <button type="button" className="studio-button studio-button-primary" onClick={() => openCheckout(checkout, current.provider)}>Continue payment <StudioIcon name="arrow" size={17} /></button>
      : <a className="studio-button studio-button-primary" href={checkout} target="_blank" rel="noopener noreferrer">Continue payment <StudioIcon name="arrow" size={17} /></a>)}{!paid && <p className="studio-field-note">Credits appear after payment confirmation. You can return to this page to check its status.</p>}{tracked.error && <p role="alert">{tracked.error}</p>}</section>}
    {note && <p className="studio-live-note" role="alert">{note}</p>}
    <section className="studio-panel studio-promo"><header><div><h2>Have a promo code?</h2><p>Add credits to your account.</p></div><span className="studio-tag">PROMO</span></header><form className="studio-promo-form" onSubmit={redeemPromo}><label className="studio-field"><span>Promo code</span><input value={promo} maxLength={64} autoComplete="off" spellCheck={false} placeholder="Enter your code" onChange={event => { setPromo(event.target.value); setPromoNote(""); }} /></label><button type="submit" className="studio-button studio-button-primary" disabled={promoBusy || !promo.trim()}>{promoBusy ? "Checking…" : session.user ? "Redeem code" : "Sign in to redeem"}<StudioIcon name="arrow" size={17} /></button></form><p className="studio-field-note">Each code can be used once per account. Codes are not case-sensitive.</p>{promoNote && <p className="studio-promo-note" role="status" aria-live="polite">{promoNote}</p>}</section>
    <section className="studio-panel studio-usage"><header><h2>Payment history</h2><button type="button" className="studio-text-button" disabled={!session.user} onClick={() => { history.reload(); void session.reloadUser(); }}>Refresh</button></header>
      {history.loading && <p className="studio-live-note" role="status">Loading payments…</p>}{history.error && <p className="studio-live-note" role="alert">{history.error}</p>}
      {history.data?.length ? <div className="studio-payment-list">{history.data.map(payment => {
        const url = payment.checkout_url ? safeCheckoutUrl(payment.checkout_url) : null;
        return <article key={payment.id}><div><strong>{payment.credits} credits</strong><p>{payment.amount} {payment.currency} · {new Date(payment.created_at).toLocaleDateString()}</p></div><span className="studio-tag">{payment.status.replaceAll("_", " ")}</span>{url && activePayment(payment) && <a className="studio-text-link" href={url} target="_blank" rel="noopener noreferrer" onClick={event => { if (telegram.inTelegram && telegram.openLink(url)) event.preventDefault(); }}>Continue ↗</a>}</article>;
      })}</div> : !history.loading && <div className="studio-usage-empty"><StudioIcon name="credits" size={25} /><h3>A blank page, for now.</h3><p>Your payments will appear here.</p></div>}
      {session.user && <div className="studio-pagination"><button className="studio-button" type="button" disabled={!offset} onClick={() => setOffset(value => Math.max(0, value - 20))}>Previous</button><button className="studio-button" type="button" disabled={(history.data?.length ?? 0) < 20} onClick={() => setOffset(value => value + 20)}>Next</button></div>}
    </section>
  </>;
}
