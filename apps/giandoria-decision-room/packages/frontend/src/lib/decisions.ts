export interface Evidence {
  Through: string;
  Sequence: number;
  Observation: string;
  Stock: number | null;
  Backlog: number | null;
  PreviousBacklog: number | null;
  DailySales: number | null;
  Cash: number | null;
  Revenue30: number | null;
  CashMovement30: number | null;
  Sold30: number | null;
}

export interface DecisionCase {
  id: string;
  title: string;
  condition: string;
  proposal: string;
  question: string;
  triggered: boolean;
}

export function parseEvidence(rows: unknown[][], columns: { name: string }[],
  expected: { throughDate: string; sequence: number }): Evidence {
  if (rows.length !== 1) throw new Error('Expected exactly one enterprise evidence row.');
  if (rows[0].length !== columns.length) throw new Error('Enterprise evidence columns and values differ.');
  const values: Record<string, unknown> = {};
  columns.forEach((column, index) => {
    const name = column.name.replace(/^\[|\]$/g, '');
    if (name in values) throw new Error('Enterprise evidence has duplicate columns.');
    values[name] = rows[0][index];
  });
  const virtualDate = (key: string): string => {
    const value = values[key];
    if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) {
      throw new Error(`Missing or invalid virtual date: ${key}.`);
    }
    const parsed = new Date(value + 'T00:00:00Z');
    if (!Number.isFinite(parsed.getTime()) || parsed.toISOString().slice(0, 10) !== value) {
      throw new Error(`Invalid virtual calendar date: ${key}.`);
    }
    return value;
  };
  const numberValue = (key: string): number | null => {
    const value = values[key];
    if (value === null) return null;
    if (typeof value !== 'number' || !Number.isFinite(value)) {
      throw new Error(`Missing or invalid evidence measure: ${key}.`);
    }
    return value;
  };
  if (values.Through !== expected.throughDate || values.Sequence !== expected.sequence) {
    throw new Error('Semantic snapshot changed. Reconcile sources and prepare the app again.');
  }
  if (String(values.Observation) > expected.throughDate) throw new Error('Observation exceeds the virtual cutoff.');
  return {
    Through: virtualDate('Through'), Sequence: expected.sequence,
    Observation: virtualDate('Observation'), Stock: numberValue('Stock'),
    Backlog: numberValue('Backlog'), PreviousBacklog: numberValue('PreviousBacklog'),
    DailySales: numberValue('DailySales'), Cash: numberValue('Cash'),
    Revenue30: numberValue('Revenue30'), CashMovement30: numberValue('CashMovement30'),
    Sold30: numberValue('Sold30'),
  };
}

export function decisionCases(e: Evidence): DecisionCase[] {
  return [
    {
      id: 'backlog', title: 'Backlog pressure',
      condition: 'Latest sampled backlog exceeds the last observation available at or before seven virtual days earlier.',
      triggered: e.Backlog !== null && e.PreviousBacklog !== null && e.Backlog > e.PreviousBacklog,
      proposal: 'Investigate releases, shipments and the virtual-date mix before changing production. Test a stock-cover hypothesis; no live action is authorized.',
      question: `Compare enterprise backlog at the last observation through ${e.Through} with the last observation at or before seven virtual days earlier. Explain the distinction between production starts, releases and shipments. Which conclusions cannot be drawn from these aggregate facts?`,
    },
    {
      id: 'stock', title: 'Stock-cover gap',
      condition: 'Last sampled finished stock is below three times average daily sell-out over the final 30 virtual days.',
      triggered: e.Stock !== null && e.DailySales !== null && e.Stock < 3 * e.DailySales,
      proposal: 'Compare the two-, three-, four-, five- and seven-day illustrative policies. A target gap is not a feasible production order.',
      question: `Using the snapshot through ${e.Through}, compare the enterprise stock-cover policies of 3 and 4 virtual days. Define daily sell-out, target stock and the target gap. Do not infer SKU stock, factory capacity or OEE.`,
    },
    {
      id: 'cash', title: 'Cash-flow divergence',
      condition: 'Recognized revenue is positive but cash movement is negative over the final 30 virtual days.',
      triggered: e.Revenue30 !== null && e.CashMovement30 !== null && e.Revenue30 > 0 && e.CashMovement30 < 0,
      proposal: 'Inspect receipts, collections and payment timing. Revenue is not cash and neither measure establishes profit.',
      question: `Explain revenue versus cash movement over the final 30 virtual days through ${e.Through}. Which receipts, collections and payment components explain the distinction? Do not invent product profitability.`,
    },
  ];
}

export function stockScenario(stock: number | null, dailySales: number | null, days: number) {
  if (![2, 3, 4, 5, 7].includes(days)) throw new Error('Unsupported cover policy.');
  if (stock === null || dailySales === null) return null;
  if (!Number.isFinite(stock) || !Number.isFinite(dailySales) || stock < 0 || dailySales < 0) {
    throw new Error('Stock scenario requires finite, nonnegative observed quantities.');
  }
  const target = dailySales * days;
  return { days, target, gap: target - stock };
}
