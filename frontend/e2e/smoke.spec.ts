import { expect, test } from "@playwright/test";

test("join screen loads on mobile viewport", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText(/Join your game session/i)).toBeVisible();
  await expect(page.getByPlaceholder("ABC123")).toBeVisible();
});

test("API health endpoint responds", async ({ request }) => {
  const resp = await request.get("/health");
  expect(resp.ok()).toBeTruthy();
});
