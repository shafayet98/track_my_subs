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
  const axisTick = { fill: "#948d80", fontFamily: "Space Mono, monospace", fontSize: 12 };
  return (
    <div style={{ width: "100%", height: 280 }}>
      <ResponsiveContainer>
        <BarChart data={rows} margin={{ top: 8, right: 8, bottom: 8, left: 8 }}>
          <CartesianGrid strokeDasharray="4 4" stroke="#e7e1d6" vertical={false} />
          <XAxis dataKey="label" tickLine={false} axisLine={false} tick={axisTick} />
          <YAxis tickLine={false} axisLine={false} width={40} tick={axisTick} />
          <Tooltip
            cursor={{ fill: "rgba(224,87,62,0.06)" }}
            formatter={(v: number) => v.toFixed(2)}
            labelFormatter={(_label, payload) =>
              payload?.[0]?.payload?.month ?? ""
            }
          />
          <Bar dataKey="total" fill="#e0573e" radius={[6, 6, 0, 0]} maxBarSize={42} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
