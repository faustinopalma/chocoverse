/**
 * Browser-safe contracts shared by the data registration package and frontend.
 *
 * Keep each record shape aligned with its decorated runtime entity in
 * `@rayfin-app/data`. This package must stay isomorphic, so do not import the
 * decorated classes here.
 */
export interface DecisionReviewRecord {
  id: string;
  owner_id: string;
  title: string;
  verdict: string;
  virtualDate: string;
  snapshotDigest: string;
  evidence: string;
  question: string;
  answer: string;
  rationale: string;
  createdAt: Date;
}

export type UniversalAppSchema = {
  DecisionReview: DecisionReviewRecord;
};

export { sourceContext } from './source-context.js';
