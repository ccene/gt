import { expect, test } from "@playwright/test";

test("join screen loads on mobile viewport", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText(/Join your game session/i)).toBeVisible();
  await expect(page.getByPlaceholder("ABC123")).toBeVisible();
  await expect(page.getByTestId("generate-and-host")).toBeVisible();
});

test("API health endpoint responds", async ({ request }) => {
  const resp = await request.get("/health");
  expect(resp.ok()).toBeTruthy();
});

test("host generates a story from an idea and gets a session code", async ({ page }) => {
  await page.goto("/");
  await page.fill("textarea", "Goblins stole the village bell");
  await page.selectOption("select >> nth=0", "1"); // 1 hour (default)
  await page.getByTestId("generate-and-host").click();
  const code = page.getByTestId("host-code");
  await expect(code).toBeVisible({ timeout: 30_000 });
  await expect(code.locator(".big-code")).toHaveText(/^[A-Z2-9]{6}$/);

  await page.getByText(/Enter as host/i).click();
  await expect(page.getByTestId("story-panel")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByTestId("campaign-bar")).toBeVisible();
  await expect(page.getByTestId("combat-panel")).toBeVisible();
  await expect(page.getByTestId("chat-panel")).toBeVisible();
});

test("campaign clock starts on play and the host can extend it", async ({ page }) => {
  await page.goto("/");
  await page.getByText(/Quick host/i).click();
  await expect(page.getByTestId("host-code")).toBeVisible({ timeout: 15_000 });
  await page.getByText(/Enter as host/i).click();
  await page.getByText(/Start session/i).click();
  await expect(page.getByTestId("campaign-remaining")).toContainText(/remaining/, { timeout: 15_000 });
  await page.getByText("+30 min").click();
  await expect(page.getByTestId("campaign-remaining")).toContainText(/1h 2\d|1h 3\d/, { timeout: 15_000 });
});

test("player joining a session already in play still gets the character form", async ({ page, context }) => {
  await page.goto("/");
  await page.getByText(/Quick host/i).click();
  await expect(page.getByTestId("host-code")).toBeVisible({ timeout: 15_000 });
  const code = (await page.locator('[data-testid="host-code"] .big-code').textContent())?.trim() ?? "";
  await page.getByText(/Enter as host/i).click();
  await page.getByText(/Start session/i).click(); // session is already playing
  await expect(page.getByText(/playing/i)).toBeVisible();

  const player = await context.newPage();
  await player.goto("/");
  await player.getByPlaceholder("Aria").fill("Aria");
  await player.getByPlaceholder("ABC123").fill(code);
  await player.getByRole("button", { name: /Join session/i }).click();
  // even though the session is 'playing', the player must be able to create a character
  await expect(player.getByText(/Your character/i)).toBeVisible({ timeout: 15_000 });
});
