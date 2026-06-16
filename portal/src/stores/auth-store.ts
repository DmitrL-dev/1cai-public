import { create } from "zustand"
import { persist } from "zustand/middleware"

interface User {
  user_id: string
  username: string
  roles: string[]
  permissions: string[]
  full_name?: string
  email?: string
}

interface AuthState {
  token: string | null
  user: User | null
  isAuthenticated: boolean
  setAuth: (token: string, user: User) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      user: null,
      isAuthenticated: false,
      setAuth: (token, user) =>
        set({ token, user, isAuthenticated: true }),
      logout: () =>
        set({ token: null, user: null, isAuthenticated: false }),
    }),
    { name: "1cai-auth" },
  ),
)
