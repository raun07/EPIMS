// src/components/ui/Badge.tsx
import { cn, statusBadgeClass } from "@/lib/utils";

interface BadgeProps {
  status: string;
  label?: string;
  className?: string;
}

export function StatusBadge({ status, label, className }: BadgeProps) {
  return (
    <span className={cn("badge", statusBadgeClass(status), className)}>
      {label ?? status.replace(/_/g, " ")}
    </span>
  );
}

// ── Button ────────────────────────────────────────────────────────────────────
import React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { Loader2 } from "lucide-react";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 rounded font-medium text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-1 disabled:opacity-50 disabled:pointer-events-none",
  {
    variants: {
      variant: {
        primary: "bg-brand-500 text-white hover:bg-brand-600 active:bg-brand-700",
        secondary: "bg-white border border-surface-border text-ink hover:bg-surface-hover",
        danger: "bg-red-500 text-white hover:bg-red-600",
        ghost: "text-ink-muted hover:bg-surface-hover hover:text-ink",
        link: "text-brand-500 underline-offset-4 hover:underline p-0 h-auto",
      },
      size: {
        sm: "h-7 px-3 text-xs",
        md: "h-9 px-4",
        lg: "h-10 px-5 text-base",
        icon: "h-8 w-8",
      },
    },
    defaultVariants: { variant: "primary", size: "md" },
  }
);

interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  loading?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, loading, children, disabled, ...props }, ref) => (
    <button
      ref={ref}
      className={cn(buttonVariants({ variant, size }), className)}
      disabled={disabled || loading}
      {...props}
    >
      {loading && <Loader2 className="h-4 w-4 animate-spin" />}
      {children}
    </button>
  )
);
Button.displayName = "Button";

// ── Card ──────────────────────────────────────────────────────────────────────

export function Card({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("bg-surface-card rounded-lg shadow-card border border-surface-border", className)}>
      {children}
    </div>
  );
}

export function CardHeader({
  title,
  subtitle,
  action,
}: {
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex items-start justify-between px-5 py-4 border-b border-surface-border">
      <div>
        <h3 className="font-semibold text-ink text-base">{title}</h3>
        {subtitle && <p className="text-xs text-ink-muted mt-0.5">{subtitle}</p>}
      </div>
      {action && <div className="ml-4 flex-shrink-0">{action}</div>}
    </div>
  );
}

// ── Input ─────────────────────────────────────────────────────────────────────

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, className, id, ...props }, ref) => {
    const fieldId = id ?? label?.toLowerCase().replace(/\s+/g, "-");
    return (
      <div className="flex flex-col gap-1">
        {label && (
          <label htmlFor={fieldId} className="text-xs font-medium text-ink-muted">
            {label}
          </label>
        )}
        <input
          id={fieldId}
          ref={ref}
          className={cn(
            "h-9 w-full rounded border border-surface-border bg-white px-3 text-sm text-ink",
            "placeholder:text-ink-subtle",
            "focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent",
            "disabled:opacity-50 disabled:bg-surface",
            error && "border-red-400 focus:ring-red-400",
            className
          )}
          {...props}
        />
        {error && <p className="text-xs text-red-500">{error}</p>}
      </div>
    );
  }
);
Input.displayName = "Input";

// ── Select ────────────────────────────────────────────────────────────────────

interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  error?: string;
  options: { value: string; label: string }[];
  placeholder?: string;
}

export const Select = React.forwardRef<HTMLSelectElement, SelectProps>(
  ({ label, error, options, placeholder, className, id, ...props }, ref) => {
    const fieldId = id ?? label?.toLowerCase().replace(/\s+/g, "-");
    return (
      <div className="flex flex-col gap-1">
        {label && (
          <label htmlFor={fieldId} className="text-xs font-medium text-ink-muted">
            {label}
          </label>
        )}
        <select
          id={fieldId}
          ref={ref}
          className={cn(
            "h-9 w-full rounded border border-surface-border bg-white px-3 text-sm text-ink",
            "focus:outline-none focus:ring-2 focus:ring-brand-500",
            "disabled:opacity-50",
            error && "border-red-400",
            className
          )}
          {...props}
        >
          {placeholder && <option value="">{placeholder}</option>}
          {options.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
        {error && <p className="text-xs text-red-500">{error}</p>}
      </div>
    );
  }
);
Select.displayName = "Select";

// ── KPI Card ──────────────────────────────────────────────────────────────────

interface KPICardProps {
  label: string;
  value: string | number;
  icon: React.ReactNode;
  trend?: string;
  accent?: string;
}

export function KPICard({ label, value, icon, trend, accent = "brand" }: KPICardProps) {
  return (
    <Card className="p-5">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium text-ink-muted uppercase tracking-widest">{label}</p>
          <p className="mt-2 text-2xl font-bold tabular text-ink">{value}</p>
          {trend && <p className="mt-1 text-xs text-ink-muted">{trend}</p>}
        </div>
        <div className={cn("p-2.5 rounded-lg", accent === "amber" ? "bg-amber-50 text-amber-500" : "bg-brand-50 text-brand-500")}>
          {icon}
        </div>
      </div>
    </Card>
  );
}

// ── Empty state ───────────────────────────────────────────────────────────────

export function EmptyState({
  title,
  description,
  action,
  icon,
}: {
  title: string;
  description?: string;
  action?: React.ReactNode;
  icon?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      {icon && <div className="text-ink-subtle mb-4">{icon}</div>}
      <h3 className="font-semibold text-ink">{title}</h3>
      {description && <p className="text-sm text-ink-muted mt-1 max-w-xs">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

// ── Loading skeleton ──────────────────────────────────────────────────────────

export function Skeleton({ className }: { className?: string }) {
  return (
    <div className={cn("animate-pulse rounded bg-surface-border", className)} />
  );
}

export function TableSkeleton({ rows = 5, cols = 5 }: { rows?: number; cols?: number }) {
  return (
    <div className="space-y-3 p-4">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex gap-4">
          {Array.from({ length: cols }).map((_, j) => (
            <Skeleton key={j} className="h-4 flex-1" />
          ))}
        </div>
      ))}
    </div>
  );
}

// ── Toast (simple) ────────────────────────────────────────────────────────────

export { cn };
