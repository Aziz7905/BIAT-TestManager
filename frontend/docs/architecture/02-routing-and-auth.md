# 02 — Routing and Auth

**React Router setup. JWT flow. Hydration. Role-based redirects.**

---

## 1. The route tree

```
/login                                                  (public)
/projects                                               (protected)
/projects/:id                                           (protected)
  ├─ Repository tab                (default)
  ├─ Specifications tab
  ├─ Test Runs tab
  ├─ Automation tab
  └─ AI tab                        (planned)
/projects/:id/automation/executions/:executionId/live   (protected, full-screen)
/profile                                                (protected)
/admin/users                                            (admin only)
/admin/teams                                            (admin only)
```

---

## 2. The guards

### 2.1 `ProtectedRoute`
Wraps any route that requires authentication.

```tsx
// Pseudo-implementation
function ProtectedRoute({ children }) {
  const { isAuthenticated, hasHydrated } = useAuthStore();

  if (!hasHydrated) {
    return <FullscreenSpinner />;  // wait for localStorage hydration
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ reason: "not-authenticated" }} />;
  }

  return children;
}
```

**Critical:** the guard waits for `hasHydrated` before deciding. Without this, a page reload causes a flash of `/login` before the auth state restores.

### 2.2 `AdminRoute`
Same pattern but checks `organization_role` for `platform_owner` or `org_admin`. Non-admins redirect to `/projects`.

---

## 3. JWT authentication flow

### 3.1 Token storage
- `biat_access` in `localStorage` — short-lived JWT access token (~15 min)
- `biat_refresh` in `localStorage` — long-lived refresh token (~7 days)

### 3.2 The bootstrap (on app load)
```
App.tsx mounts
       ↓
Calls authStore.bootstrap()
       ↓
bootstrap() reads tokens from localStorage
       ↓
If no tokens: hasHydrated = true, isAuthenticated = false
If tokens exist:
  GET /api/me/ with the access token
  On success: user data set, isAuthenticated = true
  On 401: try refresh, retry /api/me/
  On final failure: clear tokens, set sessionExpired = true
       ↓
hasHydrated = true (always, regardless of result)
       ↓
Routes can now decide
```

### 3.3 Login flow
```
User submits credentials → authStore.login({ identifier, password })
       ↓
POST /api/login/ with { identifier, password }
identifier accepts email OR username
       ↓
Response: { access, refresh, user }
       ↓
Store tokens in localStorage
       ↓
Set user, isAuthenticated = true
       ↓
authStore.login() resolves
       ↓
Component navigates to role-based destination
```

If login fails, `login()` throws. The component catches and renders an error message — `authStore` doesn't store error state.

### 3.4 The Axios request interceptor
Every outgoing request gets the access token automatically:
```typescript
client.interceptors.request.use((config) => {
  const token = localStorage.getItem('biat_access');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});
```

### 3.5 Silent refresh on 401
The response interceptor handles 401 transparently:
```
Original request → 401
       ↓
Response interceptor: try POST /api/refresh/ with refresh token
       ↓
If refresh succeeds:
  Update biat_access in localStorage
  Retry the original request (once)
If refresh fails:
  Clear tokens
  Dispatch a global event biat-auth-expired
  Reject the original request
       ↓
App.tsx listens for biat-auth-expired:
  authStore.clearSession({ sessionExpired: true })
  Navigation: redirect to /login with state { reason: "expired" }
```

A pending-queue pattern prevents multiple concurrent 401s from triggering parallel refresh calls.

### 3.6 Logout
```
authStore.logout()
       ↓
POST /api/logout/ with refresh token (best-effort, blacklists on backend)
       ↓
Clear tokens from localStorage
       ↓
Clear user state
       ↓
Navigate to /login
```

---

## 4. Role-based redirects after login

The redirect destination depends on `user.profile.organization_role`:

| Role | Destination |
|---|---|
| `platform_owner` | `/admin/users` |
| `org_admin` | `/admin/users` |
| `member` | `/projects` |

The login page handles the redirect. After `authStore.login()` resolves, it reads `user.profile.organization_role` and navigates.

---

## 5. The session-expired UX

When silent refresh fails, the user is redirected to `/login` with `location.state.reason = "expired"`.

`LoginPage` reads this and shows a banner:
> *Your session has expired. Please sign in again.*

**Why this matters:** without the banner, the user sees an unexplained logout — confusing. The reason in location state is the cleanest way to convey "this wasn't your action; your token expired."

---

## 6. The AdminRoute pattern

`AdminRoute` is hydration-aware (same as `ProtectedRoute`):

```tsx
function AdminRoute({ children }) {
  const { user, isAuthenticated, hasHydrated } = useAuthStore();
  const role = user?.profile?.organization_role;

  if (!hasHydrated) return <FullscreenSpinner />;
  if (!isAuthenticated) return <Navigate to="/login" />;
  if (role !== 'platform_owner' && role !== 'org_admin') {
    return <Navigate to="/projects" />;
  }

  return children;
}
```

Non-admins who try to navigate to `/admin/*` go to `/projects`. They don't see an error — admin pages just don't exist for them.

---

## 7. Session expiry across tabs

Today: each tab has its own state. If the user logs out in one tab, others continue with stale state until the next 401.

Future enhancement (low priority): listen for `storage` events on `biat_access`. If another tab clears it, this tab clears its session too. Worth doing if reports of "I'm seeing stale data after logout in another tab" come in.

---

## 8. Why hydration matters

Without hydration awareness:
1. App loads
2. `localStorage` has tokens
3. authStore is uninitialized → `isAuthenticated = false`
4. ProtectedRoute redirects to `/login`
5. authStore bootstrap completes → `isAuthenticated = true`
6. User sees `/login` flash, then bounces back to their target page

The `hasHydrated` flag prevents this. Routes simply wait until bootstrap completes (a few hundred ms at most). The user sees a brief spinner instead of a page flash.

---

## 9. The `bootstrap` event

`authStore.bootstrap()` is the only thing `App.tsx` does on mount:

```tsx
function App() {
  const bootstrap = useAuthStore((s) => s.bootstrap);
  useEffect(() => { bootstrap(); }, []);
  return <AppRouter />;
}
```

It also subscribes to the `biat-auth-expired` event:

```tsx
useEffect(() => {
  const onExpired = () => useAuthStore.getState().clearSession({ sessionExpired: true });
  window.addEventListener('biat-auth-expired', onExpired);
  return () => window.removeEventListener('biat-auth-expired', onExpired);
}, []);
```

This is the only event-based coupling in the app. Everything else flows through props or stores.

---

## 10. Why no useQuery / useSWR

The frontend uses plain `useState` + `useEffect` + Axios for data fetching, not a library.

**Why:**
- Data isn't shared across components (no global cache to manage)
- Each route mounts → fetches → unmounts. Simple lifecycle.
- Avoiding cache invalidation complexity entirely
- Smaller bundle, fewer concepts for new contributors

**When to revisit:** if we ever need cross-route caching (e.g., the project list should stay cached when navigating between projects), introduce a query library at that point. Don't preemptively adopt it.
