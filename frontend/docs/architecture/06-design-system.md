# 06 — Design System

**Tailwind tokens. Component conventions. Typography. Iconography.**

---

## 1. The token approach

Custom tokens defined as CSS custom properties on `:root` in `src/index.css`. Tailwind v4 picks them up via the `@tailwindcss/vite` plugin.

### 1.1 Color tokens

| Token | RGB | Hex | Use |
|---|---|---|---|
| `--primary` | `37 99 235` | `#2563EB` | CTA, links (blue-600) |
| `--primary-light` | `219 234 254` | `#DBEAFE` | Subtle backgrounds (blue-100) |
| `--surface` | `255 255 255` | `#FFFFFF` | Cards, panels |
| `--bg` | `248 250 252` | `#F8FAFC` | Page background |
| `--warm` | `234 88 12` | `#EA580C` | Warnings (orange-600) |
| `--text` | `15 23 42` | `#0F172A` | Body text (slate-900) |
| `--muted` | `100 116 139` | `#64748B` | Secondary text (slate-500) |
| `--border` | `226 232 240` | `#E2E8F0` | Borders (slate-200) |

### 1.2 Why RGB triples (not hex)
The values are stored as RGB triples (e.g., `37 99 235`) so Tailwind can construct `rgb(var(--primary) / <alpha-value>)` for opacity utilities like `bg-primary/50`. Hex would lose this.

### 1.3 Tailwind config
```typescript
// tailwind.config.ts
export default {
  theme: {
    extend: {
      colors: {
        primary: 'rgb(var(--primary) / <alpha-value>)',
        'primary-light': 'rgb(var(--primary-light) / <alpha-value>)',
        surface: 'rgb(var(--surface) / <alpha-value>)',
        bg: 'rgb(var(--bg) / <alpha-value>)',
        warm: 'rgb(var(--warm) / <alpha-value>)',
        text: 'rgb(var(--text) / <alpha-value>)',
        muted: 'rgb(var(--muted) / <alpha-value>)',
        border: 'rgb(var(--border) / <alpha-value>)',
      },
      fontFamily: {
        sans: ['Plus Jakarta Sans', 'system-ui', 'sans-serif'],
      },
    },
  },
};
```

### 1.4 Status colors
For statuses (passed, failed, running, etc.), use Tailwind's full palette directly:
- Passed: `green-600`, `green-50`
- Failed: `red-600`, `red-50`
- Running: `blue-600`, `blue-50`
- Pending: `slate-400`, `slate-50`
- Warning: `amber-600`, `amber-50`

These don't need custom tokens — they're status indicators, not brand colors.

---

## 2. Typography

### 2.1 Font
**Plus Jakarta Sans** — declared in `tailwind.config.ts` with system-ui fallback. Loaded via Google Fonts or self-hosted (current: Google Fonts via `<link>` in `index.html`).

### 2.2 Scale
Stick to Tailwind's default type scale:
- `text-xs` — 12px — labels, badges
- `text-sm` — 14px — body, table rows, form labels
- `text-base` — 16px — primary body
- `text-lg` — 18px — section headings
- `text-xl` — 20px — page subtitles
- `text-2xl` — 24px — page titles
- `text-3xl` — 30px — major headings

### 2.3 Weight
- `font-normal` (400) — body
- `font-medium` (500) — buttons, emphasis
- `font-semibold` (600) — headings, important values
- `font-bold` (700) — only for very prominent things

Don't use `font-light` — Plus Jakarta Sans's light weight is too thin for UI text.

---

## 3. Spacing

Tailwind's default spacing scale (4px base). Stick to:
- `p-2` (8px) — tight padding (chips, badges)
- `p-3` (12px) — compact padding (small cards)
- `p-4` (16px) — standard padding (most cards, list items)
- `p-6` (24px) — comfortable padding (modals, important panels)
- `p-8` (32px) — generous padding (page-level containers)

Avoid arbitrary spacing (`p-[13px]`) unless absolutely necessary. The 4px grid keeps layouts visually consistent.

---

## 4. The UI primitives

`src/components/ui/`:

### 4.1 Button
```tsx
<Button variant="primary" size="md" isLoading={false} loadingText="Saving...">
  Save
</Button>
```
- Variants: `primary`, `secondary`, `ghost`, `danger`
- Sizes: `sm`, `md`, `lg`
- Props use `isLoading` (not `loading`) — the latter is a reserved word in some contexts

### 4.2 Input
```tsx
<Input label="Name" value={name} onChange={...} placeholder="..." />
```
- Always pair with a label (accessibility)
- Error state shown via a sibling `<ErrorMessage>`

### 4.3 Modal
```tsx
<Modal open={open} onClose={...} title="Edit case" size="lg">
  ...
</Modal>
```
- Sizes: `sm`, `md`, `lg`, `xl`, `full`
- Closes on backdrop click and Esc by default
- Trap focus inside while open

### 4.4 Badge
```tsx
<Badge variant="success">Passed</Badge>
```
- Variants: `success`, `error`, `warning`, `info`, `neutral`
- For status indicators

### 4.5 EmptyState
```tsx
<EmptyState
  icon="📭"
  title="No test cases yet"
  description="Create your first test case to get started"
  action={<Button>Create case</Button>}
/>
```
- Used wherever a list is empty

### 4.6 Spinner
```tsx
<Spinner size="md" />
```
- Sizes: `sm`, `md`, `lg`
- Used for loading states

### 4.7 PageHeader
```tsx
<PageHeader title="Projects" actions={<Button>New project</Button>} />
```
- Standard page header with title + action area

### 4.8 PaginationControls
```tsx
<PaginationControls
  page={page}
  totalPages={totalPages}
  onPageChange={setPage}
/>
```
- Companion to any list using DRF pagination

### 4.9 UserPicker
```tsx
<UserPicker value={userId} onChange={setUserId} />
```
- Search-filtered user dropdown
- Walks all pages of `/api/admin/users/` (use only when count is small)

### 4.10 ConfirmDialog
```tsx
<ConfirmDialog
  open={open}
  title="Delete this case?"
  message="This will permanently delete the case and all its revisions."
  confirmText="Delete"
  variant="danger"
  onConfirm={...}
  onCancel={...}
/>
```
- For destructive operations

### 4.11 ErrorMessage
```tsx
<ErrorMessage message="Could not load specs" onDismiss={() => ...} />
```
- Dismissible error banner with warning icon

---

## 5. Iconography

### 5.1 Current approach
Inline SVG components for the few icons used. No icon library yet.

### 5.2 When to add an icon library
If we exceed ~20 distinct icons or need a richer set, adopt **lucide-react** (small, tree-shakable, comprehensive). Don't preemptively pull it in.

### 5.3 Status icons
Status icons (✓ ✗ ⟳ ⏸) are emoji or simple SVG glyphs in colored containers. Not from an icon library. They convey state quickly.

---

## 6. Layout

### 6.1 The app shell
```
<AppLayout>
  <TopNav />
  <main className="flex-1 overflow-auto bg-bg">
    {children}
  </main>
</AppLayout>
```

`AppLayout` is the shell every protected page uses (except `AutomationLivePage` which is full-screen).

### 6.2 The TopNav
- Logo (left) — clicks → `/projects`
- Page title / breadcrumb (center, optional)
- User menu (right) — profile, admin links (role-gated), sign out

### 6.3 Tab bars
Tab bars within a page use a consistent pattern:
```tsx
<TabBar
  tabs={[
    { id: 'repository', label: 'Repository' },
    { id: 'specifications', label: 'Specifications' },
    ...
  ]}
  active={tab}
  onChange={setTab}
/>
```

---

## 7. Loading states

Three patterns:

### 7.1 Page load
Full-page spinner centered:
```tsx
if (!data) return <CenteredSpinner />;
```
For initial page loads.

### 7.2 Inline skeleton
For partial loads (e.g., a tree expanding):
```tsx
{loading ? <SkeletonRow /> : <RealRow />}
```

### 7.3 Button loading
```tsx
<Button isLoading={saving} loadingText="Saving...">Save</Button>
```
Buttons that trigger async work show their loading state inline.

**Don't:** show a global spinner overlay during background mutations. It's intrusive and breaks flow.

---

## 8. Form patterns

### 8.1 Field validation
- Validate on submit, not on every keystroke
- Show errors below the field via `<ErrorMessage>`
- Clear errors on next valid input

### 8.2 Async submit
```tsx
const handleSubmit = async () => {
  setSubmitting(true);
  try {
    await api.save(data);
    onClose();
  } catch (e) {
    setError(e.message);
  } finally {
    setSubmitting(false);
  }
};
```

### 8.3 Don't auto-save
Modals and form pages have explicit Save buttons. Auto-save is a complex UX (when did it save? did it succeed?) and surprises users. Save on click; close the modal on success.

---

## 9. Tables and lists

### 9.1 Table use
Tables are for tabular data with clear columns. Use them for:
- User admin
- Team members
- Run cases inside a run

### 9.2 List use
Lists are for cards / row items where each item is its own object. Use for:
- Projects
- Recent executions
- Specifications

### 9.3 Don't use tables for everything
A "table" with 1 column or wildly different cell shapes is a list. Use a list component.

### 9.4 Empty rows
Both tables and lists must handle the empty state — render `<EmptyState>`, never an empty table.

---

## 10. Accessibility basics

The platform's users are bank QA staff. Accessibility matters but at a baseline level:

- All form inputs have labels
- Modals trap focus and are dismissable with Esc
- Buttons have visible focus rings
- Color is never the only signal (status icons accompany colored text)
- Tables have semantic `<th>` headers

We don't hand-build a full WCAG AA compliance suite. We do enough that screen-reader users can operate the platform.

---

## 11. Dark mode

**Not in scope.** The bank's typical use is daytime, fluorescent-lit office. Dark mode is a feature complexity multiplier (every color decision has a dark variant) for marginal user benefit at this scale.

If real demand emerges, add it later. The CSS-variable token approach makes it possible (just swap variables on a `data-theme="dark"` attribute) but don't preemptively build it.

---

## 12. Why no component library

The platform is small enough that a few hand-built primitives outperform any library:
- No bundle bloat from unused components
- Visual consistency under our exact control
- No "MUI says this is how dropdowns look" dictating our UX
- Easy onboarding (the primitives are <100 lines each)

When the platform grows past ~30 primitives or needs sophisticated components (date pickers, complex tables, etc.), revisit. For now, custom components win.
