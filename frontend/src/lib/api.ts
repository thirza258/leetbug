let csrfToken: string | null = null;
export function setCsrf(token: string | null) { csrfToken = token; }
export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) { super(message); this.status = status; }
}
export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...options, credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', ...(csrfToken ? { 'X-CSRF-Token': csrfToken } : {}), ...options.headers },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: 'The server could not complete this request.' }));
    const message = Array.isArray(payload.detail)
      ? payload.detail.map((item: { msg: string; loc: string[] }) => `${item.loc.at(-1)}: ${item.msg}`).join('. ')
      : payload.detail;
    throw new ApiError(message || 'Something went wrong. Please try again.', response.status);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}
export function post<T>(path: string, body?: unknown) {
  return api<T>(path, { method: 'POST', ...(body === undefined ? {} : { body: JSON.stringify(body) }) });
}

// ---------- problem submissions ----------

export function submitProblem(data: {
  title: string; summary: string; description: string; category: string;
  difficulty: string; tags: string[]; language: string; buggy_code: string;
  fixed_code: string; test_cases: { input: string; expected: string }[];
  hint: string;
}) {
  return post<import('../types').ProblemSubmission>('/problem-submissions', data);
}

export function getMyProblemSubmissions(page = 1) {
  return api<import('../types').Page<import('../types').ProblemSubmission>>(`/problem-submissions?page=${page}`);
}

// ---------- admin ----------

export function getAdminSubmissions(status = '', page = 1) {
  return api<import('../types').Page<import('../types').ProblemSubmission>>(
    `/admin/problem-submissions?status=${status}&page=${page}`
  );
}

export function getAdminSubmission(id: string) {
  return api<import('../types').ProblemSubmission>(`/admin/problem-submissions/${id}`);
}

export function reviewSubmission(id: string, action: 'approved' | 'rejected', admin_notes = '') {
  return api<import('../types').ProblemSubmission>(`/admin/problem-submissions/${id}`, {
    method: 'PATCH',
    body: JSON.stringify({ action, admin_notes }),
  });
}
