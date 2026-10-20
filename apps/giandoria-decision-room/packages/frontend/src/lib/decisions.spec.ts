import { describe, expect, it } from 'vitest';
import { decisionCases, parseEvidence, stockScenario } from './decisions';

const expected = { throughDate: '2034-09-03', sequence: 613901 };
const columns = ['Through', 'Sequence', 'Observation', 'Stock', 'Backlog', 'PreviousBacklog',
  'DailySales', 'Cash', 'Revenue30', 'CashMovement30', 'Sold30'].map(name => ({ name: `[${name}]` }));
const row: unknown[] = ['2034-09-03', 613901, '2034-09-03', 0, 37, 18, 417.56666666666666,
  3441661.55, 144187.5, 62537.87, 12527];

describe('governed evidence and bounded policies', () => {
  it('maps verified connector output and applies explicit virtual rules', () => {
    const evidence = parseEvidence([row], columns, expected);
    expect(evidence.Cash).toBe(3441661.55);
    expect(decisionCases(evidence).map(item => item.triggered)).toEqual([true, true, false]);
    expect(stockScenario(evidence.Stock, evidence.DailySales, 3)?.target).toBeCloseTo(1252.7);
    expect(stockScenario(evidence.Stock, evidence.DailySales, 4)?.gap).toBeCloseTo(1670.2666666666667);
  });
  it('rejects mismatched cutoff, version, future or invalid dates and malformed columns', () => {
    for (const [index, value] of [[0, '2035-01-01'], [1, 1], [2, '2034-09-04'],
      [2, '2034-02-30'], [3, '0'], [4, Infinity], [6, undefined]] as const) {
      const changed = [...row]; changed[index] = value;
      expect(() => parseEvidence([changed], columns, expected)).toThrow();
    }
    expect(() => parseEvidence([], columns, expected)).toThrow();
    expect(() => parseEvidence([row.slice(1)], columns, expected)).toThrow();
    expect(() => parseEvidence([row], columns.map(() => ({ name: 'Through' })), expected)).toThrow();
  });
  it('preserves missing data and negative target gaps without inventing production', () => {
    const changed = [...row]; changed[3] = null;
    expect(parseEvidence([changed], columns, expected).Stock).toBeNull();
    expect(stockScenario(null, 10, 3)).toBeNull();
    expect(stockScenario(100, 10, 3)).toEqual({ days: 3, target: 30, gap: -70 });
    expect(() => stockScenario(0, 10, 6)).toThrow('Unsupported');
    expect(() => stockScenario(-1, 10, 3)).toThrow();
  });
});
