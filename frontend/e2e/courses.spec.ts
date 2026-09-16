import { expect, test } from '@playwright/test';

test('courses explain choices, grade answers, and resume all nine lessons', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/');
  await page.getByRole('link', { name: 'Courses', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'System design courses', exact: true })).toBeVisible();
  await expect(page.locator('.course-card')).toHaveCount(3);
  await page.getByRole('link', { name: 'Start course', exact: true }).first().click();
  await expect(page.getByRole('heading', { name: 'Start with the requirements', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Check answer' })).toBeDisabled();
  await page.getByRole('radio', { name: 'Choose it because throughput is the highest.' }).check();
  await page.getByRole('button', { name: 'Check answer' }).click();
  await expect(page.locator('.checkpoint-feedback')).toContainText('makes this candidate infeasible');
  await expect(page.locator('.course-progress')).toContainText('0 of 3 lessons complete');

  const lessons = [
    ['choosing-an-architecture', 'requirements-first', 'Exclude it, then compare the candidates that meet every requirement.'],
    ['choosing-an-architecture', 'architecture-styles', 'Enqueue conversion work and expose job status.'],
    ['choosing-an-architecture', 'defend-the-decision', 'Report no feasible design and revisit candidates or requirements.'],
    ['data-consistency-and-caching', 'access-patterns', 'The required transaction boundary and query patterns.'],
    ['data-consistency-and-caching', 'concurrent-updates', 'Atomically debit only when the stored balance is sufficient, and check whether it succeeded.'],
    ['data-consistency-and-caching', 'cache-freshness', 'No. Check whether the key exists independently of its value.'],
    ['queues-and-reliability', 'queues-and-bursts', 'The backlog grows unless capacity or admission changes.'],
    ['queues-and-reliability', 'safe-retries', 'The same key and payload for the same intended reservation.'],
    ['queues-and-reliability', 'bounded-recovery', 'Two retries, subject to the overall deadline.'],
  ];
  for (const [index, [course, lesson, answer]] of lessons.entries()) {
    if (index > 0) await expect(page).toHaveURL(`/courses/${course}${index % 3 === 0 ? '' : `/${lesson}`}`);
    await expect(page.locator('.lesson-example')).toBeVisible();
    await expect(page.locator('.lesson-source')).toHaveAttribute('href', /^https:\/\//);
    await page.getByRole('radio', { name: answer, exact: true }).check();
    await page.getByRole('button', { name: 'Check answer' }).click();
    await expect(page.locator('.checkpoint-feedback')).toContainText('Correct.');
    await expect(page.locator('.course-progress')).toContainText(`${index % 3 + 1} of 3 lessons complete`);
    await page.reload();
    await expect(page.getByText('Knowledge check passed', { exact: true })).toBeVisible();
    // Rechecking an already completed lesson must not increment progress twice.
    if (index === 0) {
      await page.getByRole('radio', { name: answer, exact: true }).check();
      await page.getByRole('button', { name: 'Check answer' }).click();
      await expect(page.locator('.course-progress')).toContainText('1 of 3 lessons complete');
      await page.getByRole('link', { name: 'All courses', exact: true }).click();
      await page.getByRole('link', { name: 'Continue course', exact: true }).click();
    } else if (index % 3 < 2) {
      await page.getByRole('link', { name: 'Next lesson', exact: true }).click();
    } else {
      await expect(page.getByRole('heading', { name: 'Course complete', exact: true })).toBeVisible();
      // Every linked practice case must resolve to a real public problem.
      for (const link of await page.locator('.practice-link').all()) {
        const href = await link.getAttribute('href');
        const response = await page.request.get(`/api${href}`);
        expect(response.ok()).toBe(true);
      }
      if (index < lessons.length - 1) await page.getByRole('link', { name: /^Next course:/ }).click();
    }
  }
  await page.getByRole('link', { name: 'All courses', exact: true }).click();
  await expect(page.getByRole('link', { name: 'Review course', exact: true })).toHaveCount(3);
  await page.screenshot({ path: '../artifacts/system-design-courses.png', fullPage: true });
  await page.getByRole('button', { name: 'Switch to dark theme' }).click();
  await page.getByRole('link', { name: 'Review course', exact: true }).first().click();
  await page.screenshot({ path: '../artifacts/system-design-lesson-dark.png', fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: '../artifacts/system-design-lesson-mobile.png', fullPage: true, animations: 'disabled' });
  await page.getByRole('button', { name: 'Open navigation' }).click();
  await page.getByRole('link', { name: 'Courses', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'System design courses', exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  expect(errors).toEqual([]);
});

test('courses recover from invalid storage and unknown lessons', async ({ page }) => {
  await page.goto('/courses');
  for (const value of ['not json', 'null', '{}', '["unknown/lesson",3,null]']) {
    await page.evaluate(saved => localStorage.setItem('leetbug.courses.v1:guest', saved), value);
    await page.reload();
    await expect(page.getByRole('link', { name: 'Start course', exact: true })).toHaveCount(3);
  }
  await page.goto('/courses/missing');
  await expect(page.getByText('This lesson could not be found.')).toBeVisible();
  await page.goto('/courses/choosing-an-architecture/missing');
  await expect(page.getByRole('link', { name: 'Browse courses' })).toBeVisible();
  await page.goto('/courses/choosing-an-architecture');
  await expect(page.getByRole('heading', { name: 'Start with the requirements', exact: true })).toBeVisible();
  await page.evaluate(() => { Storage.prototype.setItem = () => { throw new Error('Storage unavailable'); }; });
  await page.getByRole('radio', { name: 'Exclude it, then compare the candidates that meet every requirement.' }).check();
  await page.getByRole('button', { name: 'Check answer' }).click();
  await expect(page.locator('.course-outline')).toContainText('Browser storage is unavailable');
  await expect(page.locator('.course-progress')).toContainText('1 of 3 lessons complete');
});

test('course progress is separate for guests and members, and the system design case can be solved', async ({ page }) => {
  await page.goto('/courses/choosing-an-architecture');
  await page.getByRole('radio', { name: 'Exclude it, then compare the candidates that meet every requirement.' }).check();
  await page.getByRole('button', { name: 'Check answer' }).click();
  await expect(page.locator('.course-progress')).toContainText('1 of 3 lessons complete');
  await page.goto('/register');
  const username = `design_${Date.now().toString(36)}`;
  await page.getByLabel('Username').fill(username);
  await page.getByLabel('Email address').fill(`${username}@example.com`);
  await page.getByLabel('Password', { exact: true }).fill('DesignTestPassword123!');
  await page.getByRole('button', { name: 'Start your debugging journey' }).click();
  await expect(page).toHaveURL('/');
  await page.getByRole('link', { name: 'Courses', exact: true }).click();
  await expect(page.getByRole('link', { name: 'Start course', exact: true })).toHaveCount(3);
  await page.getByRole('link', { name: 'Start course', exact: true }).nth(1).click();
  await page.getByRole('radio', { name: 'The required transaction boundary and query patterns.' }).check();
  await page.getByRole('button', { name: 'Check answer' }).click();
  await page.reload();
  await expect(page.getByText('Knowledge check passed', { exact: true })).toBeVisible();
  await page.getByRole('link', { name: /Problem library/ }).click();
  await page.getByRole('button', { name: /System design Choose for the requirements/ }).click();
  await expect(page.locator('.problem-table tbody tr')).toHaveCount(5);
  await page.getByRole('link', { name: /Choosing the right system design/ }).click();
  await expect(page.locator('.monaco-editor')).toBeVisible();
  await page.getByRole('button', { name: 'Run code', exact: true }).click();
  await expect(page.locator('.results-summary')).toContainText('Failed', { timeout: 90_000 });
  await page.locator('.monaco-editor .view-lines').click({ position: { x: 100, y: 35 } });
  await page.keyboard.press('ControlOrMeta+a');
  const solution = `def solve(data):
    r = data["requirements"]
    feasible = [d for d in data["designs"]
                if d["capacity_rps"] >= r["peak_rps"]
                and d["latency_ms"] <= r["max_latency_ms"]
                and d["monthly_cost"] <= r["monthly_budget"]
                and d["ops"] <= r["max_ops"]
                and (not r["needs_strong_consistency"] or d["strong_consistency"])]
    feasible.sort(key=lambda d: (d["monthly_cost"], d["ops"], d["id"]))
    return {"design": feasible[0]["id"] if feasible else None}
`;
  // Paste through the clipboard so Monaco preserves multiline indentation.
  await page.context().grantPermissions(['clipboard-read', 'clipboard-write']);
  await page.evaluate(source => navigator.clipboard.writeText(source), solution);
  await page.keyboard.press('ControlOrMeta+v');
  const submitted = page.waitForRequest(request => request.url().endsWith('/api/submissions') && request.method() === 'POST');
  await page.getByRole('button', { name: 'Submit fix', exact: true }).click();
  expect((await submitted).postDataJSON().code.trim()).toBe(solution.trim());
  await expect(page.locator('.success-note')).toContainText('All tests passed', { timeout: 90_000 });
  await page.getByRole('button', { name: 'Solutions', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Behind the fix' })).toBeVisible();
  await page.getByRole('link', { name: 'My progress', exact: true }).click();
  await expect(page.locator('.category-progress > div').filter({ hasText: 'System design' })).toContainText('1 / 5');
  await page.getByRole('link', { name: 'Courses', exact: true }).click();
  await expect(page.locator('.course-card').nth(1)).toContainText('1 of 3 lessons complete');
  await page.getByRole('button', { name: 'Sign out', exact: true }).click();
  await expect(page.locator('.course-card').first()).toContainText('1 of 3 lessons complete');
  await expect(page.locator('.course-card').nth(1)).toContainText('0 of 3 lessons complete');
});
