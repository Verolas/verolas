import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test("home redirects to login", async ({ page }) => {
  const response = await page.goto("/");
  expect(response).not.toBeNull();
  await expect(page).toHaveURL(/\/login$/);
});

test("login page renders and is WCAG 2.2 AA clean", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByRole("heading", { name: /sign in to verolas/i })).toBeVisible();
  await expect(page.getByLabel(/email/i)).toBeVisible();
  await expect(page.getByRole("button", { name: /continue/i })).toBeVisible();

  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
    .analyze();
  expect(results.violations, JSON.stringify(results.violations, null, 2)).toEqual([]);
});

test("dashboard renders for unauthenticated users (skeleton stage)", async ({ page }) => {
  await page.goto("/dashboard");
  await expect(page.getByRole("heading", { name: /dashboard/i })).toBeVisible();

  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
    .analyze();
  expect(results.violations, JSON.stringify(results.violations, null, 2)).toEqual([]);
});

test("projects renders for unauthenticated users (skeleton stage)", async ({ page }) => {
  await page.goto("/projects");
  await expect(page.getByRole("heading", { name: /projects/i })).toBeVisible();

  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
    .analyze();
  expect(results.violations, JSON.stringify(results.violations, null, 2)).toEqual([]);
});
