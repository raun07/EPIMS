import { create } from "zustand";
import { persist } from "zustand/middleware";

interface UserBrief {
  id: string;
  email: string;
  full_name: string;
  roles: string[];
  permissions: string[];
  is_superuser: boolean;
}

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  user: UserBrief | null;
  isAuthenticated: boolean;

  setTokens: (access: string, refresh: string) => void;
  setUser: (user: UserBrief) => void;
  logout: () => void;
  hasPermission: (resource: string, action: string) => boolean;
  hasRole: (...roles: string[]) => boolean;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      accessToken: null,
      refreshToken: null,
      user: null,
      isAuthenticated: false,

      setTokens: (access, refresh) =>
        set({ accessToken: access, refreshToken: refresh, isAuthenticated: true }),

      setUser: (user) => set({ user }),

      logout: () =>
        set({
          accessToken: null,
          refreshToken: null,
          user: null,
          isAuthenticated: false,
        }),

      hasPermission: (resource, action) => {
        const { user } = get();
        if (!user) return false;
        if (user.is_superuser) return true;
        return (
          user.permissions.includes(`${resource}:${action}`) ||
          user.permissions.includes(`${resource}:*`) ||
          user.permissions.includes("*:*")
        );
      },

      hasRole: (...roles) => {
        const { user } = get();
        if (!user) return false;
        if (user.is_superuser) return true;
        return roles.some((r) => user.roles.includes(r));
      },
    }),
    {
      name: "epims-auth",
      partialize: (state) => ({
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
        user: state.user,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
);
