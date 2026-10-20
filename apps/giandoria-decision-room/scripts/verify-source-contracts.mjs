import { sourceContext } from '../packages/shared/dist/source-context.js';
import { assertContract } from '../packages/functions/dist/contract.js';

if (!process.env.RAYFIN_TOKEN) throw new Error('A process-scoped Fabric token is required.');
await assertContract(sourceContext.workspaceId, sourceContext.modelId, sourceContext.modelDigest, process.env.RAYFIN_TOKEN, undefined, 'TMSL');
await assertContract(sourceContext.workspaceId, sourceContext.agentId, sourceContext.agentDigest, process.env.RAYFIN_TOKEN);
console.log(JSON.stringify({ operation: 'decision-room.verify-sources', status: 'verified',
  virtualDate: sourceContext.throughDate, snapshotDigest: sourceContext.snapshotDigest }));
