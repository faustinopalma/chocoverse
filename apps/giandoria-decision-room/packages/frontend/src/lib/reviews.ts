import type { DecisionReviewRecord } from '@rayfin-app/shared';

function reviewText(value: unknown, field: string): string {
  if (typeof value === 'string') return value;
  // Rayfin's legacy reader also hydrates ISO-looking text and boolean strings.
  if (typeof value === 'boolean') return String(value);
  if (value instanceof Date && Number.isFinite(value.getTime())) {
    const iso = value.toISOString();
    return iso.endsWith('T00:00:00.000Z') ? iso.slice(0, 10) : iso;
  }
  throw new Error(`The saved review has an invalid ${field} field.`);
}

export function normalizeReview(record: DecisionReviewRecord): DecisionReviewRecord {
  const virtualDate = reviewText(record.virtualDate, 'virtual cutoff');
  const parsed = new Date(virtualDate + 'T00:00:00Z');
  if (!/^\d{4}-\d{2}-\d{2}$/.test(virtualDate) ||
    !Number.isFinite(parsed.getTime()) || parsed.toISOString().slice(0, 10) !== virtualDate) {
    throw new Error('The saved review has an invalid virtual calendar date.');
  }
  return {
    ...record,
    virtualDate,
    question: reviewText(record.question, 'question'),
    answer: reviewText(record.answer, 'answer'),
    rationale: reviewText(record.rationale, 'reasoning'),
  };
}
