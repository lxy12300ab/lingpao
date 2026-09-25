"use strict";
function cycleEnergyMetrics(row, weekly, daily) {
  const dates = row.period.match(/\d{4}\/\d{2}\/\d{2}/g) || [];
  const start = dates[0]?.replaceAll("/", "-"), end = dates[1]?.replaceAll("/", "-");
  const entries = daily.filter(r => start && r.date >= start && r.date <= end);
  const recorded = entries.reduce((sum, r) => sum + r.km, 0);
  const rate = weekly.find(r => r.period === row.period)?.value;
  const inferred = Number.isFinite(rate) && rate > 0 ? row.totalKwh / rate * 100 : null;
  const complete = new Set(entries.map(r => r.date)).size === 7;
  const difference = complete && inferred !== null ? inferred - recorded : null;
  return {recorded, inferred, complete, rate, difference,
    differencePct: difference !== null && recorded > 0 ? difference / recorded * 100 : null,
    consumedPct: row.totalKwh / 81.9 * 100,
    remainingPct: Math.max(0, 1 - row.totalKwh / 81.9) * 100,
    excess: Math.max(0, row.totalKwh - 81.9)};
}
