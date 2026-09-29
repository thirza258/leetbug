import { expect, test } from '@playwright/test';
import { courses, courseTracks } from '../src/lib/courses';

test('courses cover every section with shareable filters and mobile layouts', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/');
  await page.getByRole('link', { name: 'Courses', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Problem-solving courses' })).toBeVisible();
  await expect(page.locator('.course-card')).toHaveCount(14);
  await expect(page.locator('.course-intro')).toContainText('14 courses · 42 lessons');
  await expect(page.locator('.course-track')).toHaveCount(6);
  for (const track of courseTracks) {
    await page.getByRole('navigation', { name: 'Course sections' }).getByRole('link', { name: new RegExp(`^${track.title}`) }).click();
    await expect(page).toHaveURL(`/courses?track=${track.id}`);
    await expect(page.locator('.course-card')).toHaveCount(track.id === 'system_design' ? 4 : 2);
    await expect(page.getByRole('heading', { name: track.title, exact: true })).toBeVisible();
    await page.reload();
    await expect(page.locator('.course-track')).toHaveCount(1);
  }
  await page.goto('/courses?track=unknown');
  await expect(page.locator('.course-card')).toHaveCount(14);
  await page.goto('/courses?track=runtime');
  await page.screenshot({ path: '../artifacts/courses-runtime-desktop.png', fullPage: true });
  await page.getByRole('button', { name: 'Switch to dark theme' }).click();
  await page.getByRole('link', { name: 'Start course', exact: true }).first().click();
  await expect(page.locator('.lesson-code')).toBeVisible();
  await expect(page.locator('.lesson-steps li')).toHaveCount(3);
  await page.screenshot({ path: '../artifacts/course-walkthrough-dark.png', fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: '../artifacts/course-walkthrough-mobile.png', fullPage: true, animations: 'disabled' });
  await page.getByRole('link', { name: 'All courses', exact: true }).click();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  expect(errors).toEqual([]);
});

for (const course of courses) {
  test(`course lessons grade and persist: ${course.title}`, async ({ page }) => {
    await page.goto(`/courses/${course.slug}`);
    for (const [index, lesson] of course.lessons.entries()) {
      await expect(page.getByRole('heading', { name: lesson.title, exact: true })).toBeVisible();
      await expect(page.locator('.lesson-example')).toBeVisible();
      await expect(page.locator('.lesson-source')).toHaveAttribute('href', lesson.source.url);
      await expect(page.getByRole('button', { name: 'Check answer' })).toBeDisabled();
      if (lesson.example.steps) await expect(page.locator('.lesson-steps li')).toHaveCount(3);
      const answer = lesson.checkpoint.options.find(option => option.correct)!;
      if (index === 0) {
        const wrong = lesson.checkpoint.options.find(option => !option.correct)!;
        await page.getByRole('radio', { name: wrong.text, exact: true }).check();
        await page.getByRole('button', { name: 'Check answer' }).click();
        await expect(page.locator('.checkpoint-feedback')).toContainText(wrong.feedback);
        await expect(page.locator('.course-progress')).toContainText('0 of 3 lessons complete');
      }
      await page.getByRole('radio', { name: answer.text, exact: true }).check();
      await page.getByRole('button', { name: 'Check answer' }).click();
      await expect(page.locator('.checkpoint-feedback')).toContainText(answer.feedback);
      await expect(page.locator('.course-progress')).toContainText(`${index + 1} of 3 lessons complete`);
      await page.reload();
      await expect(page.getByText('Knowledge check passed', { exact: true })).toBeVisible();
      if (index === 0) {
        // Completing the same lesson twice must not double-count it.
        await page.getByRole('radio', { name: answer.text, exact: true }).check();
        await page.getByRole('button', { name: 'Check answer' }).click();
        await expect(page.locator('.course-progress')).toContainText('1 of 3 lessons complete');
        await page.getByRole('link', { name: 'All courses', exact: true }).click();
        await page.getByRole('link', { name: 'Continue course', exact: true }).click();
        await expect(page).toHaveURL(`/courses/${course.slug}/${course.lessons[1].slug}`);
      } else if (index < course.lessons.length - 1) {
        await page.getByRole('link', { name: 'Next lesson', exact: true }).click();
      }
    }
    await expect(page.getByRole('heading', { name: 'Course complete', exact: true })).toBeVisible();
    for (const problem of course.practice) {
      const response = await page.request.get(`/api/problems/${problem.slug}`);
      expect(response.ok()).toBe(true);
      expect((await response.json()).title).toBe(problem.title);
    }
    const nextCourse = courses[courses.indexOf(course) + 1];
    if (nextCourse) {
      await page.getByRole('link', { name: /^Next course:/ }).click();
      await expect(page.getByRole('heading', { name: nextCourse.title, exact: true })).toBeVisible();
    }
    await page.getByRole('link', { name: 'All courses', exact: true }).click();
    await expect(page.getByRole('link', { name: 'Review course', exact: true })).toHaveCount(1);
  });
}

test('courses recover from invalid storage and unknown lessons', async ({ page }) => {
  await page.goto('/courses');
  for (const value of ['not json', 'null', '{}', '["unknown/lesson",3,null]']) {
    await page.evaluate(saved => localStorage.setItem('leetbug.courses.v1:guest', saved), value);
    await page.reload();
    await expect(page.getByRole('link', { name: 'Start course', exact: true })).toHaveCount(courses.length);
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
  await expect(page.getByRole('link', { name: 'Start course', exact: true })).toHaveCount(courses.length);
  await page.getByRole('link', { name: 'Data, consistency, and caching', exact: true }).click();
  await page.getByRole('radio', { name: 'The required transaction boundary and query patterns.' }).check();
  await page.getByRole('button', { name: 'Check answer' }).click();
  await page.reload();
  await expect(page.getByText('Knowledge check passed', { exact: true })).toBeVisible();
  await page.getByRole('link', { name: /Problem library/ }).click();
  await page.getByRole('button', { name: /System design Choose for the requirements/ }).click();
  await expect(page.locator('.problem-table tbody tr')).toHaveCount(20);
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
  await expect(page.locator('.category-progress > div').filter({ hasText: 'System design' })).toContainText('1 / 48');
  await page.getByRole('link', { name: 'Courses', exact: true }).click();
  await expect(page.locator('.course-card').filter({ hasText: 'Data, consistency, and caching' })).toContainText('1 of 3 lessons complete');
  await page.getByRole('button', { name: 'Sign out', exact: true }).click();
  await expect(page.locator('.course-card').filter({ hasText: 'Choosing the right architecture' })).toContainText('1 of 3 lessons complete');
  await expect(page.locator('.course-card').filter({ hasText: 'Data, consistency, and caching' })).toContainText('0 of 3 lessons complete');
});
