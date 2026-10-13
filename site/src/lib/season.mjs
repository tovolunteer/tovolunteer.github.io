export function torontoMonth(date) {
  return Number(new Intl.DateTimeFormat('en-CA', {
    timeZone: 'America/Toronto', month: 'numeric',
  }).format(date));
}

export function seasonStatus(openMonths, currentMonth) {
  if (openMonths === 'year-round') return { kind: 'year-round' };
  if (!Array.isArray(openMonths) || openMonths.length === 0) return null;
  if (openMonths.includes(currentMonth)) return { kind: 'open' };

  const nextMonth = [...openMonths].sort((a, b) =>
    ((a - currentMonth + 12) % 12) - ((b - currentMonth + 12) % 12))[0];
  return { kind: 'seasonal', nextMonth };
}

export function seasonLabel(status, t) {
  if (status.kind === 'year-round') return t.seasonYearRound;
  if (status.kind === 'open') return t.seasonOpenNow;
  const month = t.lang === 'zh' ? String(status.nextMonth) : new Intl.DateTimeFormat('en-CA', {
    month: 'long', timeZone: 'UTC',
  }).format(new Date(Date.UTC(2024, status.nextMonth - 1, 1)));
  return t.seasonReturns.replace('{month}', month);
}
