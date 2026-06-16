# 🌐 UNIFIED PORTAL - Technical Architecture

**Version:** 1.0  
**Date:** 3 ноября 2025

---

## 🏗️ ARCHITECTURE OVERVIEW

```
┌─────────────────────────────────────────────┐
│         FRONTEND (React + TypeScript)       │
│  ┌─────────────────────────────────────┐   │
│  │  Unified Portal App                 │   │
│  │  - SSO Authentication               │   │
│  │  - Role Detection                   │   │
│  │  - Dynamic Dashboard Routing        │   │
│  └─────────────────────────────────────┘   │
│         ↓                                   │
│  ┌──────┴───────────┬───────────────┐      │
│  ↓                  ↓               ↓      │
│ Executive        PM/PO         Developer   │
│ Dashboard      Dashboard        Console    │
│  ↓                  ↓               ↓      │
│ Team Lead       BA Workspace   Settings    │
│ Dashboard                                   │
└─────────────────────────────────────────────┘
         ↓ (REST API + WebSocket)
┌─────────────────────────────────────────────┐
│         BACKEND (FastAPI - Already exists!) │
│  ┌─────────────────────────────────────┐   │
│  │  API Gateway                        │   │
│  │  - /api/dashboard/*                 │   │
│  │  - /api/projects/*                  │   │
│  │  - /api/analytics/*                 │   │
│  │  - /ws/* (WebSocket)                │   │
│  └─────────────────────────────────────┘   │
│         ↓                                   │
│  ┌──────┴───────────────────────────┐      │
│  │  Existing Services:              │      │
│  │  - AI Orchestrator ✅            │      │
│  │  - Neo4j Client ✅               │      │
│  │  - Qdrant Client ✅              │      │
│  │  - PostgreSQL ✅                 │      │
│  │  - Redis Cache ✅                │      │
│  └──────────────────────────────────┘      │
└─────────────────────────────────────────────┘
```

---

## 🎯 TECH STACK

### **Frontend:**
```json
{
  "framework": "React 18 + TypeScript",
  "build": "Vite (fast!)",
  "state": "Zustand (simple, fast)",
  "routing": "React Router v6",
  "forms": "React Hook Form + Zod",
  "charts": "Recharts",
  "ui": "Radix UI + Tailwind CSS",
  "icons": "Lucide React",
  "auth": "Auth0 / Supabase Auth",
  "realtime": "Socket.io client"
}
```

### **Why this stack:**
✅ Modern & performant  
✅ Excellent TypeScript support  
✅ Great DX (Developer Experience)  
✅ Small bundle size  
✅ Accessibility built-in (Radix UI)  
✅ Fast builds (Vite)  

---

## 📁 PROJECT STRUCTURE

```
frontend/
├── public/
│   └── assets/
├── src/
│   ├── app/                 # App shell
│   │   ├── App.tsx
│   │   ├── routes.tsx
│   │   └── layout/
│   │       ├── AppLayout.tsx
│   │       ├── Sidebar.tsx
│   │       └── TopNav.tsx
│   │
│   ├── features/            # Feature-based organization
│   │   ├── auth/
│   │   │   ├── components/
│   │   │   ├── hooks/
│   │   │   └── api/
│   │   ├── executive/       # Executive dashboard
│   │   ├── pm/              # PM dashboard
│   │   ├── developer/       # Dev console
│   │   ├── team-lead/       # Team lead dashboard
│   │   └── ba/              # BA workspace
│   │
│   ├── shared/              # Shared across features
│   │   ├── components/      # UI components
│   │   │   ├── Button/
│   │   │   ├── Card/
│   │   │   ├── Chart/
│   │   │   ├── Table/
│   │   │   └── ...
│   │   ├── hooks/           # Shared hooks
│   │   ├── utils/           # Utilities
│   │   └── types/           # TypeScript types
│   │
│   ├── lib/                 # Libraries & configs
│   │   ├── api-client.ts    # Axios instance
│   │   ├── websocket.ts     # Socket.io
│   │   └── store.ts         # Zustand store
│   │
│   ├── styles/              # Global styles
│   │   ├── index.css        # Tailwind imports
│   │   └── theme.ts         # Design tokens
│   │
│   └── main.tsx             # Entry point
│
├── package.json
├── vite.config.ts
├── tailwind.config.js
└── tsconfig.json
```

---

## 🔐 AUTHENTICATION FLOW

```
User lands on portal.1c-ai.com
         ↓
Login Page (SSO)
  - Email/Password
  - Google OAuth
  - Microsoft OAuth
  - GitHub OAuth
         ↓
Auth0 / Supabase Auth
         ↓
JWT Token received
         ↓
Role detection (from token claims)
         ↓
Route to appropriate dashboard:
  - CEO/CTO → Executive
  - PM/PO → PM Dashboard
  - Developer → Dev Console
  - Team Lead → Team Dashboard
  - BA → BA Workspace
         ↓
Dashboard loads with user data
```

---

## 🎨 ROUTING STRUCTURE

```typescript
Routes:
/                     → Landing (if not logged in)
/login                → Login page
/dashboard            → Role-based redirect
/executive            → Executive dashboard
/pm                   → PM dashboard
/developer            → Developer console
/team-lead            → Team lead dashboard
/ba                   → BA workspace
/settings             → User settings
/admin                → Admin panel (super admin only)

Protected routes: All except / and /login
Role-based: Each dashboard checks user role
```

---

## 🔄 STATE MANAGEMENT

### **Zustand Store Structure:**

```typescript
// Global state
interface AppStore {
  // User
  user: User | null;
  userRole: Role;
  
  // UI
  sidebarCollapsed: boolean;
  darkMode: boolean;
  
  // Data
  projects: Project[];
  currentProject: Project | null;
  
  // Loading states
  loading: Record<string, boolean>;
  
  // Actions
  setUser: (user: User) => void;
  toggleSidebar: () => void;
  // ...
}
```

### **Why Zustand over Redux:**
- ✅ Simpler API
- ✅ Less boilerplate
- ✅ Better TypeScript
- ✅ Smaller bundle
- ✅ No Provider hell

---

## 📡 API INTEGRATION

### **API Client:**

```typescript
// lib/api-client.ts
import axios from 'axios';

const apiClient = axios.create({
  baseURL: process.env.VITE_API_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor (add auth token)
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor (handle errors)
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Redirect to login
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);
```

---

## 🔌 REAL-TIME UPDATES

### **WebSocket Integration:**

```typescript
// lib/websocket.ts
import io from 'socket.io-client';

const socket = io(process.env.VITE_WS_URL, {
  auth: {
    token: localStorage.getItem('token'),
  },
});

// Listen for events
socket.on('project:updated', (data) => {
  // Update UI
});

socket.on('notification', (notification) => {
  // Show toast
});

// Emit events
socket.emit('subscribe:project', projectId);
```

**Use cases:**
- Project status updates
- Team activity feed
- Code review comments
- Build/deploy notifications
- Chat messages

---

## 📊 DATA FETCHING

### **React Query (TanStack Query):**

```typescript
// hooks/useProjects.ts
import { useQuery } from '@tanstack/react-query';

export function useProjects() {
  return useQuery({
    queryKey: ['projects'],
    queryFn: () => apiClient.get('/api/projects').then(r => r.data),
    staleTime: 5 * 60 * 1000, // 5 min
    cacheTime: 10 * 60 * 1000, // 10 min
  });
}

// Usage in component:
const { data: projects, isLoading, error } = useProjects();
```

**Benefits:**
- ✅ Automatic caching
- ✅ Background refetching
- ✅ Optimistic updates
- ✅ Loading states
- ✅ Error handling

---

## 🎨 COMPONENT PATTERNS

### **Composition Pattern:**

```typescript
// Good: Composable
<Card>
  <Card.Header>
    <Card.Title>Revenue</Card.Title>
  </Card.Header>
  <Card.Body>
    <RevenueChart data={data} />
  </Card.Body>
</Card>

// Bad: Monolithic
<RevenueCard data={data} title="Revenue" />
```

### **Render Props / Hooks:**

```typescript
// Good: Flexible
function useMetric(metricId: string) {
  const { data, loading } = useQuery(...)
  return { value: data, loading };
}

// Usage
const { value, loading } = useMetric('revenue');
```

---

## ♿ ACCESSIBILITY

### **ARIA Labels:**
```tsx
<button aria-label="Close dialog">
  <XIcon />
</button>

<input 
  aria-describedby="email-error"
  aria-invalid={hasError}
/>
```

### **Keyboard Navigation:**
```
Tab: Navigate forward
Shift+Tab: Navigate backward
Enter: Activate
Escape: Close modal/dropdown
Arrow keys: Navigate lists
```

### **Focus Management:**
```typescript
// Trap focus in modal
import { FocusTrap } from '@radix-ui/react-focus-scope';

<FocusTrap>
  <Modal>...</Modal>
</FocusTrap>
```

---

## 🚀 PERFORMANCE

### **Code Splitting:**
```typescript
// Lazy load dashboards
const ExecutiveDashboard = lazy(() => import('./features/executive'));
const PMDashboard = lazy(() => import('./features/pm'));

// Route-based splitting
<Route path="/executive" element={
  <Suspense fallback={<Loading />}>
    <ExecutiveDashboard />
  </Suspense>
} />
```

### **Image Optimization:**
```
- WebP format (fallback to PNG)
- Lazy loading (below fold)
- Responsive images (srcset)
- CDN delivery
```

### **Bundle Optimization:**
```
- Tree shaking
- Minification
- Gzip compression
- Dynamic imports
- Remove unused CSS

Target: < 200KB initial bundle
```

---

## 🧪 TESTING STRATEGY

```
Unit Tests:      Jest + React Testing Library
Integration:     Playwright / Cypress
E2E:             Playwright
Visual Regression: Chromatic
Performance:     Lighthouse CI

Coverage target: >80%
```

---

## 📱 RESPONSIVE STRATEGY

### **Mobile First:**
```scss
// Default: Mobile
.component {
  flex-direction: column;
}

// Tablet +
@media (min-width: 768px) {
  .component {
    flex-direction: row;
  }
}
```

### **Adaptive Components:**
```
Mobile:  Single column, full width cards
Tablet:  2 columns, medium cards
Desktop: 3-4 columns, optimized layout
```

---

## 🎯 IMPLEMENTATION PHASES

### **Phase 1: Foundation** (Week 1)
- [ ] Setup Vite + React + TypeScript
- [ ] Configure Tailwind CSS
- [ ] Implement Design System components
- [ ] Setup routing
- [ ] Implement authentication

### **Phase 2: Core Dashboards** (Week 2)
- [ ] Executive Dashboard
- [ ] PM Dashboard
- [ ] Developer Console (basic)

### **Phase 3: Advanced Features** (Week 3)
- [ ] Team Lead Dashboard
- [ ] BA Workspace
- [ ] Real-time updates (WebSocket)
- [ ] Advanced charts

### **Phase 4: Polish** (Week 4)
- [ ] Dark mode
- [ ] Animations
- [ ] Mobile optimization
- [ ] Performance tuning
- [ ] Accessibility audit

---

**Architecture Complete!** ✅  
**Ready for Implementation →**


