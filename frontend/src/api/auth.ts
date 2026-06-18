// src/api/auth.ts
import api from "@/lib/api";
import type { LoginRequest, TokenResponse, UserResponse } from "@/types";

export const authApi = {
  login: (data: LoginRequest) =>
    api.post<TokenResponse>("/auth/login", data).then((r) => r.data),

  refresh: (refreshToken: string) =>
    api
      .post<TokenResponse>("/auth/refresh", { refresh_token: refreshToken })
      .then((r) => r.data),

  logout: (refreshToken?: string) =>
    api.post("/auth/logout", { refresh_token: refreshToken }),

  me: () => api.get<UserResponse>("/auth/me").then((r) => r.data),

  changePassword: (oldPassword: string, newPassword: string) =>
    api.post("/auth/change-password", {
      old_password: oldPassword,
      new_password: newPassword,
    }),

  createUser: (data: unknown) =>
    api.post<UserResponse>("/auth/users", data).then((r) => r.data),

  updateUser: (id: string, data: unknown) =>
    api.put<UserResponse>(`/auth/users/${id}`, data).then((r) => r.data),

  assignRoles: (id: string, roleNames: string[]) =>
    api
      .post<UserResponse>(`/auth/users/${id}/roles`, { role_names: roleNames })
      .then((r) => r.data),
};
