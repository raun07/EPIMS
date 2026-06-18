import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { authApi } from "@/api/auth";
import { useAuthStore } from "@/store/authStore";
import { Button, Input } from "@/components/ui";

interface LoginForm {
  email: string;
  password: string;
}

export default function LoginPage() {
  const navigate = useNavigate();
  const { setTokens, setUser } = useAuthStore();
  const [serverError, setServerError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginForm>();

  const onSubmit = async (data: LoginForm) => {
    setServerError(null);
    try {
      const result = await authApi.login(data);
      setTokens(result.access_token, result.refresh_token);
      setUser(result.user);
      navigate("/");
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ?? "Invalid email or password";
      setServerError(String(msg));
    }
  };

  return (
    <div className="min-h-screen bg-surface flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="flex items-center gap-3 mb-8">
          <div className="h-9 w-9 rounded-lg bg-brand-500 flex items-center justify-center text-white font-bold">
            EP
          </div>
          <div>
            <div className="font-semibold text-ink text-lg leading-tight">EPIMS</div>
            <div className="text-xs text-ink-muted">Procurement & Inventory</div>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow-card border border-surface-border p-6">
          <h1 className="text-xl font-semibold text-ink mb-1">Sign in</h1>
          <p className="text-sm text-ink-muted mb-6">Access your procurement workspace</p>

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <Input
              label="Work email"
              type="email"
              placeholder="you@company.com"
              error={errors.email?.message}
              {...register("email", {
                required: "Email is required",
                pattern: {
                  value: /^[^@\s]+@[^@\s]+\.[^@\s]+$/,
                  message: "Enter a valid email",
                },
              })}
            />

            <Input
              label="Password"
              type="password"
              placeholder="••••••••"
              error={errors.password?.message}
              {...register("password", { required: "Password is required" })}
            />

            {serverError && (
              <p className="text-xs text-red-500 bg-red-50 px-3 py-2 rounded">
                {serverError}
              </p>
            )}

            <Button
              type="submit"
              className="w-full"
              loading={isSubmitting}
              disabled={isSubmitting}
            >
              Sign in
            </Button>
          </form>
        </div>

        <p className="text-center text-xs text-ink-subtle mt-4">
          EPIMS v1.0 · Enterprise Procurement System
        </p>
      </div>
    </div>
  );
}
