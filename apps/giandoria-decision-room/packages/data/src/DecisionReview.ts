import { date, entity, role, text, uuid } from '@microsoft/rayfin-core';

@entity()
@role('authenticated', '*', {
  policy: (claims, item) => claims.sub.eq(item.owner_id),
})
export class DecisionReview {
  @uuid() id!: string;
  @text({ max: 200 }) owner_id!: string;
  @text({ min: 1, max: 200 }) title!: string;
  @text({ max: 20 }) verdict!: string;
  @text({ max: 10 }) virtualDate!: string;
  @text({ max: 64 }) snapshotDigest!: string;
  @text({ max: 4000 }) evidence!: string;
  @text({ max: 2000 }) question!: string;
  @text({ max: 4000 }) answer!: string;
  @text({ max: 2000 }) rationale!: string;
  @date() createdAt!: Date;
}
