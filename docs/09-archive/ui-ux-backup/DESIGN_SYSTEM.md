# 🎨 UNIFIED PORTAL - Design System

**Версия:** 1.0  
**Дата:** 3 ноября 2025  
**Based on:** Material Design 3, Apple HIG, Best Practices

---

## 🎯 DESIGN PRINCIPLES

### **1. Role-Based Clarity**
- Каждая роль видит только релевантную информацию
- Personalized dashboards
- Context-aware navigation

### **2. Progressive Disclosure**
- Показываем important info первым
- Details on demand
- No overwhelming with data

### **3. Consistency**
- Unified visual language
- Consistent patterns across roles
- Predictable interactions

### **4. Accessibility First**
- WCAG 2.1 Level AA compliance
- Keyboard navigation
- Screen reader support
- Color blind friendly

### **5. Performance**
- < 2s initial load
- < 100ms interactions
- Optimistic UI updates
- Smart caching

---

## 🎨 VISUAL LANGUAGE

### **Color Palette**

**Primary (Brand):**
```
Primary Blue:    #2563EB (Trustworthy, Professional)
Primary Dark:    #1E40AF
Primary Light:   #60A5FA
```

**Secondary:**
```
Success Green:   #10B981 (Positive actions, success)
Warning Orange:  #F59E0B (Attention needed)
Error Red:       #EF4444 (Errors, critical)
Info Purple:     #8B5CF6 (Information, insights)
```

**Neutrals:**
```
Background:      #F9FAFB (Light theme)
Surface:         #FFFFFF
Text Primary:    #111827
Text Secondary:  #6B7280
Border:          #E5E7EB
```

**Dark Theme:**
```
Background:      #111827
Surface:         #1F2937
Text Primary:    #F9FAFB
Text Secondary:  #9CA3AF
Border:          #374151
```

---

### **Typography**

**Font Family:**
```
Primary: 'Inter', system-ui, sans-serif
Monospace: 'JetBrains Mono', 'Fira Code', monospace
```

**Scale:**
```
Display:    48px / 56px (Hero titles)
H1:         36px / 44px (Page titles)
H2:         30px / 38px (Section titles)
H3:         24px / 32px (Subsections)
H4:         20px / 28px (Card titles)
Body Large: 16px / 24px (Main text)
Body:       14px / 20px (Standard text)
Caption:    12px / 16px (Helper text)
```

**Weights:**
```
Regular:    400
Medium:     500
Semibold:   600
Bold:       700
```

---

### **Spacing System**

**8-point grid:**
```
xs:  4px   (0.5 units)
sm:  8px   (1 unit)
md:  16px  (2 units)
lg:  24px  (3 units)
xl:  32px  (4 units)
2xl: 48px  (6 units)
3xl: 64px  (8 units)
```

---

### **Elevation (Shadows)**

```css
/* Card hover */
shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);

/* Cards */
shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1);

/* Modals */
shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1);

/* Dropdowns */
shadow-xl: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
```

---

### **Border Radius**

```
sm:  4px  (Buttons, inputs)
md:  8px  (Cards)
lg:  12px (Large cards)
xl:  16px (Modals)
full: 9999px (Pills, avatars)
```

---

### **Icons**

**Library:** Lucide Icons (consistent, modern)

**Sizes:**
```
sm: 16px (Inline icons)
md: 20px (Buttons)
lg: 24px (Headers)
xl: 32px (Features)
```

---

## 🧩 COMPONENT LIBRARY

### **1. Navigation**

#### **Top Navigation Bar**
```
Height: 64px
Background: Surface
Shadow: shadow-sm
Border-bottom: 1px solid Border

Elements:
- Logo (left, 40px height)
- Global search (center-left, expandable)
- Notifications (right)
- User avatar + dropdown (right)
```

#### **Sidebar Navigation**
```
Width: 
  - Collapsed: 72px
  - Expanded: 256px
  - Mobile: Full width overlay

Background: Surface
Border-right: 1px solid Border

Sections:
- Role-based menu items
- Quick actions
- Settings (bottom)
- Collapse toggle (bottom)
```

---

### **2. Dashboard Cards**

#### **Metric Card**
```
Min-height: 120px
Padding: 24px
Border-radius: 12px
Background: Surface
Shadow: shadow-md
Hover: shadow-lg + scale(1.02)

Layout:
┌─────────────────────┐
│ 📊 TITLE       ⓘ   │
│                     │
│ 1,234              │
│ Large number        │
│                     │
│ +12% ↑ vs last week│
└─────────────────────┘
```

#### **Chart Card**
```
Min-height: 320px
Padding: 24px
Chart library: Recharts / Chart.js

Features:
- Interactive hover
- Time range selector
- Export button
- Fullscreen option
```

#### **List Card**
```
Recent activity, tasks, etc.

Each item:
- Icon (left)
- Title + description
- Timestamp
- Action button (right)
```

---

### **3. Tables**

**Best practices:**
```
- Sticky header
- Sortable columns
- Filterable
- Pagination (50/100/200 per page)
- Row actions (hover reveal)
- Bulk actions (checkbox selection)
- Responsive (cards on mobile)
```

---

### **4. Forms**

**Input Fields:**
```
Height: 40px
Padding: 12px 16px
Border: 1px solid Border
Border-radius: 8px
Focus: Primary border + shadow

States:
- Default
- Focus
- Error (red border)
- Disabled (opacity 0.5)
- Success (green border)
```

**Buttons:**
```
Primary:
  - Background: Primary Blue
  - Text: White
  - Hover: Primary Dark
  - Height: 40px
  - Padding: 12px 24px

Secondary:
  - Background: Transparent
  - Border: 1px Primary
  - Text: Primary
  - Hover: Light background

Ghost:
  - Background: Transparent
  - No border
  - Hover: Light background

Sizes: sm (32px), md (40px), lg (48px)
```

---

### **5. Modals & Dialogs**

```
Max-width: 
  - sm: 400px
  - md: 600px
  - lg: 800px
  - xl: 1200px

Overlay: rgba(0,0,0,0.5)
Border-radius: 16px
Padding: 32px

Header:
  - Title (H3)
  - Close button (top-right)

Body:
  - Content

Footer:
  - Actions (right-aligned)
  - Cancel (left) + Confirm (right)
```

---

### **6. Notifications**

**Toast Notifications:**
```
Position: Top-right
Width: 400px
Auto-dismiss: 5s
Animation: Slide in from right

Types:
- Success (green)
- Error (red)
- Warning (orange)
- Info (purple)
```

**Notification Center:**
```
Dropdown from bell icon
Max height: 480px
Scrollable
Group by date
Mark as read
See all (link to page)
```

---

## 📱 RESPONSIVE DESIGN

### **Breakpoints:**
```
xs:  < 640px   (Mobile portrait)
sm:  640px     (Mobile landscape)
md:  768px     (Tablet)
lg:  1024px    (Desktop)
xl:  1280px    (Large desktop)
2xl: 1536px    (Ultra wide)
```

### **Mobile-First Approach:**
```
1. Design for mobile first
2. Progressive enhancement for larger screens
3. Touch-friendly targets (min 44x44px)
4. Swipe gestures where appropriate
```

---

## 🎭 ANIMATIONS & TRANSITIONS

### **Timing:**
```
Fast:    150ms (Hover, active states)
Medium:  300ms (Modals, dropdowns)
Slow:    500ms (Page transitions)
```

### **Easing:**
```
ease-out: Entering elements
ease-in:  Exiting elements
ease-in-out: Moving elements
spring:   Interactive elements
```

### **Microinteractions:**
```
- Button press (scale down 0.95)
- Card hover (lift + shadow)
- Loading (skeleton screens)
- Success (checkmark animation)
- Error (shake animation)
```

---

## ♿ ACCESSIBILITY

### **WCAG 2.1 Level AA:**
```
✅ Color contrast 4.5:1 (text)
✅ Color contrast 3:1 (UI components)
✅ Keyboard navigation
✅ Screen reader labels
✅ Focus indicators
✅ Skip links
✅ Error identification
✅ Consistent navigation
```

### **Semantic HTML:**
```html
<header> for top navigation
<nav> for menus
<main> for primary content
<article> for self-contained content
<aside> for sidebars
<footer> for footers
```

---

## 🌙 DARK MODE

**Auto-switching:**
```
1. System preference (default)
2. User override (toggle)
3. Remember preference
```

**Implementation:**
```css
/* Use CSS variables */
:root {
  --color-background: #F9FAFB;
  --color-surface: #FFFFFF;
  --color-text: #111827;
}

.dark {
  --color-background: #111827;
  --color-surface: #1F2937;
  --color-text: #F9FAFB;
}
```

---

## 🔤 CONTENT GUIDELINES

### **Tone of Voice:**
```
✅ Clear and concise
✅ Professional yet friendly
✅ Action-oriented
✅ Helpful, not bossy

❌ Jargon without explanation
❌ Too casual
❌ Blame language
```

### **Microcopy:**
```
Buttons:
  ✅ "Save changes"
  ❌ "Submit"

Errors:
  ✅ "Email address is required"
  ❌ "Invalid input"

Empty states:
  ✅ "No projects yet. Create your first project!"
  ❌ "No data"
```

---

## 📊 DASHBOARD PATTERNS

### **Information Hierarchy:**
```
1. KPIs at top (most important)
2. Trends/charts (second level)
3. Recent activity (third level)
4. Quick actions (sidebar or bottom)
```

### **Grid Layout:**
```
Desktop (lg+):
  - 12-column grid
  - KPIs: 3 columns (4 cards)
  - Charts: 6-8 columns
  - Sidebar: 4 columns

Tablet (md):
  - 8-column grid
  - KPIs: 2 columns (2 cards)
  - Charts: Full width
  
Mobile (xs-sm):
  - Single column
  - Stack vertically
  - Swipeable cards
```

---

## 🎯 ROLE-SPECIFIC PATTERNS

### **Executive Dashboard:**
```
Focus: High-level KPIs, trends, alerts
Layout: Large numbers, simple charts
Colors: Traffic light system (red/yellow/green)
Actions: Minimal, view details only
```

### **PM Dashboard:**
```
Focus: Projects, timelines, teams
Layout: Gantt charts, kanban boards
Colors: Status-based (on track/delayed)
Actions: Moderate (assign, comment)
```

### **Developer Console:**
```
Focus: Code, performance, debugging
Layout: Dense information, code views
Colors: Syntax highlighting
Actions: Many (edit, test, deploy)
```

---

## 📐 LAYOUT EXAMPLES

### **Dashboard Layout:**
```
┌────────────────────────────────────────┐
│ TopNav: Logo | Search | Notif | Avatar│
├──────┬─────────────────────────────────┤
│ Side │ Page Title             [Action]│
│ Nav  ├─────────────────────────────────┤
│      │ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐│
│ 📊  │ │ KPI │ │ KPI │ │ KPI │ │ KPI ││
│ 📈  │ └─────┘ └─────┘ └─────┘ └─────┘│
│ 👥  │ ┌───────────────┐ ┌───────────┐ │
│ ⚙️  │ │ Chart         │ │ Activity  │ │
│      │ │               │ │ Feed      │ │
│ ───  │ └───────────────┘ └───────────┘ │
│ 🌙  │ ┌─────────────────────────────┐ │
│ 👤  │ │ Table / List                │ │
│      │ └─────────────────────────────┘ │
└──────┴─────────────────────────────────┘
```

---

## 🚀 IMPLEMENTATION STACK

### **Frontend:**
```
Framework: React 18 + TypeScript
Build: Vite
State: Zustand (lightweight, modern)
Router: React Router v6
Forms: React Hook Form + Zod validation
Charts: Recharts
UI Components: Radix UI (unstyled, accessible)
Styling: Tailwind CSS
Icons: Lucide React
```

### **Why this stack:**
```
✅ Modern and performant
✅ Excellent TypeScript support
✅ Great accessibility (Radix UI)
✅ Fast builds (Vite)
✅ Flexible styling (Tailwind)
✅ Lightweight (no bloat)
```

---

## 📋 COMPONENT CHECKLIST

For each component:
```
✅ Responsive (mobile, tablet, desktop)
✅ Accessible (ARIA, keyboard, screen reader)
✅ Dark mode support
✅ Loading states
✅ Empty states
✅ Error states
✅ Hover/focus states
✅ TypeScript types
✅ Storybook story
✅ Unit tests
```

---

## 🎨 DESIGN TOKENS

**Export for developers:**
```typescript
// colors.ts
export const colors = {
  primary: {
    50: '#EFF6FF',
    500: '#2563EB',
    900: '#1E3A8A',
  },
  // ... all colors
};

// spacing.ts
export const spacing = {
  xs: '4px',
  sm: '8px',
  // ...
};

// typography.ts
export const typography = {
  fontFamily: {
    sans: 'Inter, system-ui, sans-serif',
    mono: 'JetBrains Mono, monospace',
  },
  // ...
};
```

---

## 📚 BEST PRACTICES APPLIED

✅ **Material Design 3** - Modern, accessible patterns  
✅ **Apple HIG** - User-centric, intuitive  
✅ **Nielsen Norman Group** - Usability heuristics  
✅ **WCAG 2.1** - Accessibility standards  
✅ **Brad Frost's Atomic Design** - Component hierarchy  
✅ **Google's HEART Framework** - Metrics  
✅ **Don Norman's Design Principles** - User psychology  

---

**Design System готов для implementation!** ✅

Next: Specific dashboard designs for each role →


