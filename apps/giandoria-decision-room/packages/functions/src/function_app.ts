import { AudienceType, UserDataFunctions, type RayfinContext } from '@microsoft/fabric-user-data-functions';
import { sourceContext, type UniversalAppSchema } from '@rayfin-app/shared';
import { askAgent } from './mcp.js';
import { assertContract } from './contract.js';

const udf = new UserDataFunctions();

udf.func(
  'investigate',
  async (ctx: RayfinContext<UniversalAppSchema, AudienceType.Fabric>,
    question: string): Promise<{ answer: string; virtualDate: string; snapshotDigest: string }> => {
    if (!question.trim() || question.length > 1500) throw new Error('Enter a question of 1 to 1,500 characters.');
    const token = ctx.Tokens.Fabric;
    const deadline = AbortSignal.timeout(210000);
    const verify = async () => {
      await assertContract(sourceContext.workspaceId, sourceContext.modelId, sourceContext.modelDigest, token,
        AbortSignal.any([deadline, AbortSignal.timeout(45000)]), 'TMSL');
      await assertContract(sourceContext.workspaceId, sourceContext.agentId, sourceContext.agentDigest, token,
        AbortSignal.any([deadline, AbortSignal.timeout(45000)]));
    };
    await verify();
    const endpoint = `https://api.fabric.microsoft.com/v1/mcp/workspaces/${sourceContext.workspaceId}/dataagents/${sourceContext.agentId}/agent`;
    const prompt = `Use only the published enterprise snapshot through ${sourceContext.throughDate} (virtual Rome date). ` +
      'Answer concisely in English, under 3,000 characters. State limitations and distinguish observed facts from hypothetical advice. Do not claim live data. Question: ' + question;
    const answer = await askAgent(endpoint, token, prompt, deadline);
    await verify();
    return { answer, virtualDate: sourceContext.throughDate, snapshotDigest: sourceContext.snapshotDigest };
  },
  []
);
