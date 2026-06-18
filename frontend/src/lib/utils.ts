// src/lib/utils.ts
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatCurrency(
  amount: number | string,
  currency = "INR"
): string {
  const num = typeof amount === "string" ? parseFloat(amount) : amount;
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(num);
}

export function formatDate(date: string | Date): string {
  return new Intl.DateTimeFormat("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(new Date(date));
}

export function formatDateTime(date: string | Date): string {
  return new Intl.DateTimeFormat("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(date));
}

export function statusBadgeClass(status: string): string {
  const s = status?.toLowerCase();
  const map: Record<string, string> = {
    draft: "badge-draft",
    submitted: "badge-pending",
    pending_approval: "badge-pending",
    approved: "badge-approved",
    rejected: "badge-rejected",
    released: "badge-released",
    sent: "badge-released",
    partially_received: "badge-received",
    received: "badge-received",
    invoiced: "badge-matched",
    matched: "badge-matched",
    disputed: "badge-disputed",
    paid: "badge-paid",
    cancelled: "badge-cancelled",
    closed: "badge-approved",
    po_created: "badge-approved",
    posted: "badge-received",
  };
  return map[s] ?? "badge-draft";
}

export function truncate(str: string, len = 40): string {
  return str.length > len ? str.slice(0, len) + "…" : str;
}
