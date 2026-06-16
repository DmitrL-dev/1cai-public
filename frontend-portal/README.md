# 🌐 Unified Portal - Frontend

> Modern, role-based dashboard for Enterprise 1C AI Stack

## ✨ Features

- **Role-Based Dashboards** - Personalized for each user role
- **Real-Time Updates** - WebSocket integration
- **AI Assistance** - Integrated AI agents
- **Dark Mode** - Full dark theme support
- **Responsive** - Mobile, tablet, desktop
- **Accessible** - WCAG 2.1 Level AA compliant

---

## 🚀 Quick Start

### Prerequisites
```bash
Node.js >= 18
npm or yarn
```

### Install
```bash
cd frontend-portal
npm install
```

### Development
```bash
npm run dev
# Opens at http://localhost:3000
```

### Build
```bash
npm run build
# Output: dist/
```

### Preview
```bash
npm run preview
```

---

## 🏗️ Tech Stack

- **Framework:** React 18 + TypeScript
- **Build:** Vite (⚡ fast!)
- **State:** Zustand
- **Routing:** React Router v6
- **API:** TanStack Query (React Query)
- **UI:** Radix UI + Tailwind CSS
- **Forms:** React Hook Form + Zod
- **Charts:** Recharts
- **Icons:** Lucide React

---

## 📁 Project Structure

```
src/
├── app/                    # App shell
│   ├── App.tsx            # Main app
│   ├── routes.tsx         # Routing
│   └── layout/            # Layouts
│       ├── AppLayout.tsx
│       ├── Sidebar.tsx
│       └── TopNav.tsx
│
├── features/               # Feature modules
│   ├── auth/              # Authentication
│   ├── executive/         # Executive dashboard
│   ├── pm/                # PM dashboard
│   ├── developer/         # Developer console
│   ├── team-lead/         # Team lead dashboard
│   └── ba/                # BA workspace
│
├── shared/                 # Shared components
│   ├── components/        # UI components
│   │   ├── Button/
│   │   ├── Card/
│   │   ├── MetricCard/
│   │   └── ...
│   ├── hooks/             # Custom hooks
│   └── utils/             # Utilities
│
├── lib/                    # Libraries
│   ├── api-client.ts      # API client
│   ├── store.ts           # Zustand store
│   └── types.ts           # TypeScript types
│
└── styles/                 # Global styles
    └── index.css          # Tailwind imports
```

---

## 🎨 Design System

See: 

**Colors:**
- Primary: `#2563EB` (Blue)
- Success: `#10B981` (Green)
- Warning: `#F59E0B` (Orange)
- Error: `#EF4444` (Red)

**Typography:**
- Font: Inter
- Monospace: JetBrains Mono

**Spacing:** 8-point grid (4px, 8px, 16px, 24px, 32px...)

---

## 👥 Role-Based Dashboards

### **Executive** (`/executive`)
- High-level KPIs
- Revenue trends
- Project health
- Strategic objectives

### **PM** (`/pm`)
- Project timeline
- Team workload
- Sprint progress
- Resource allocation

### **Developer** (`/developer`)
- Assigned tasks
- Code reviews
- Build status
- AI assistance

### **Team Lead** (`/team-lead`)
- Team metrics
- Code quality trends
- Technical debt
- Team performance

### **Business Analyst** (`/ba`)
- Requirements management
- Traceability matrix
- Gap analysis
- BPMN diagrams

---

## 🔐 Authentication

**Supported methods:**
- Email/Password
- Google OAuth
- Microsoft OAuth
- GitHub OAuth

**Implementation:** Auth0 / Supabase Auth

---

## 🧪 Testing

```bash
# Unit tests
npm run test

# E2E tests
npm run test:e2e

# Coverage
npm run test:coverage
```

---

## 📦 Deployment

### **Production Build:**
```bash
npm run build
```

### **Docker:**
```dockerfile
FROM node:18-alpine as build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

### **Environment Variables:**
```env
VITE_API_URL=https://api.yourdomain.com
VITE_WS_URL=wss://api.yourdomain.com
VITE_AUTH_DOMAIN=yourdomain.auth0.com
```

---

## 📚 Documentation

- 
- 
- 
- 
- 

---

## 🤝 Contributing

1. Fork the repository
2. Create feature branch
3. Make changes
4. Write tests
5. Submit PR

---

## 📄 License

MIT

---

**Built with ❤️ for 1C Developers**


