export function shouldApplyKnowledgeResponse({
  requestSeq,
  currentSeq,
  requestRunId,
  currentRunId,
  responseRunId,
}: {
  requestSeq: number;
  currentSeq: number;
  requestRunId: string;
  currentRunId?: string;
  responseRunId?: string;
}): boolean {
  return requestSeq === currentSeq && currentRunId === requestRunId && responseRunId === requestRunId;
}
