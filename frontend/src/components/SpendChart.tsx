import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { MonthlySpend } from "../api/types";
import { monthLabel } from "../lib/format";

export function SpendChart({ data }: { data: MonthlySpend[] }) {
  const rows = data.map((m) => ({ ...m, label: monthLabel(m.month) }));
  return (
    <div style={{ width: "100%", height: 280 }}>
      <ResponsiveContainer>
        <BarChart data={rows} margin={{ top: 8, right: 8, bottom: 8, left: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
          <XAxis dataKey="label" tickLine={false} axisLine={false} />
          <YAxis tickLine={false} axisLine={false} width={48} />
          <Tooltip
            formatter={(v: number) => v.toFixed(2)}
            labelFormatter={(_label, payload) =>
              payload?.[0]?.payload?.month ?? ""
            }
          />
          <Bar dataKey="total" fill="#4f46e5" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
