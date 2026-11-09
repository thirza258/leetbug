import { api, post } from '../../lib/api';
import type { Page } from '../../types';
import type { AssistantInteraction, AssistantRequest } from './types';

export function askAssistant(slug: string, body: AssistantRequest & { question: string }) {
  return post<AssistantInteraction>(`/problems/${slug}/debug-assistant`, body);
}
export function whyFixFailed(slug: string, body: AssistantRequest) {
  return post<AssistantInteraction>(`/problems/${slug}/why-fix-failed`, body);
}
export function getInteraction(id: string) {
  return api<AssistantInteraction>(`/ai-interactions/${id}`);
}
export function listInteractions(slug: string, limit = 10) {
  return api<Page<AssistantInteraction>>(`/problems/${slug}/ai-interactions?limit=${limit}`);
}
