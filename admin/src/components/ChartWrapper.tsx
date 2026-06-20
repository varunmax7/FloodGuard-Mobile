/**
 * Thin Recharts wrappers used across Phase 11-12 pages.
 * Import from here so chart library stays decoupled from page code.
 */
export {
  LineChart, Line,
  BarChart, Bar,
  AreaChart, Area,
  PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts'

// Shared colour palette (matches mobile design tokens)
export const COLORS = {
  low:      '#22C55E',
  moderate: '#FACC15',
  high:     '#F97316',
  severe:   '#EF4444',
  blue:     '#2563EB',
  muted:    '#94A3B8',
}
