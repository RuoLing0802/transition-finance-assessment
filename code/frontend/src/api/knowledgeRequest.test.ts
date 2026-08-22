import { describe, expect, it } from 'vitest';
import { shouldApplyKnowledgeResponse } from './knowledgeRequest';

describe('knowledge request race guard', () => {
  it('rejects a slow response after the user switched runs', () => {
    expect(shouldApplyKnowledgeResponse({ requestSeq: 1, currentSeq: 2, requestRunId: 'run-a', currentRunId: 'run-b', responseRunId: 'run-a' })).toBe(false);
  });

  it('accepts only the current run response with the matching sequence', () => {
    expect(shouldApplyKnowledgeResponse({ requestSeq: 3, currentSeq: 3, requestRunId: 'run-a', currentRunId: 'run-a', responseRunId: 'run-a' })).toBe(true);
  });
});
