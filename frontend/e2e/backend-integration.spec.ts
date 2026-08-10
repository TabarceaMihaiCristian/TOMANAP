import { expect, test } from "@playwright/test";

test("creates a room through FastAPI and enters the authoritative lobby", async ({
  page,
}) => {
  test.skip(
    process.env.TOMANAP_E2E_BACKEND !== "1",
    "Set TOMANAP_E2E_BACKEND=1 and start the backend to run this contract test",
  );

  await page.goto("/");
  await page.getByLabel(/cum te cheamă/i).fill("Mihai");
  await page.getByRole("button", { name: /creează joc/i }).click();

  await expect(page).toHaveURL(/\/room\/[A-Z0-9]{6}$/);
  await expect(page.getByRole("heading", { name: /camera [A-Z0-9]{6}/i })).toBeVisible();
  await expect(page.getByText("Mihai")).toBeVisible();
  await expect(page.getByText("Gazdă")).toBeVisible();
});

test("rotates credentials and restores the same room after refresh", async ({ page }) => {
  test.skip(
    process.env.TOMANAP_E2E_BACKEND !== "1",
    "Set TOMANAP_E2E_BACKEND=1 and start the backend to run this contract test",
  );

  await page.goto("/");
  await page.getByLabel(/cum te cheamă/i).fill("Mihai");
  await page.getByRole("button", { name: /creează joc/i }).click();
  await expect(page).toHaveURL(/\/room\/[A-Z0-9]{6}$/);
  const roomUrl = page.url();
  const credentialsBeforeRefresh = await page.evaluate(() =>
    sessionStorage.getItem("tomanap.session.v1"),
  );

  await page.reload();

  await expect(page).toHaveURL(roomUrl);
  await expect(page.getByRole("heading", { name: /camera [A-Z0-9]{6}/i })).toBeVisible();
  const credentialsAfterRefresh = await page.evaluate(() =>
    sessionStorage.getItem("tomanap.session.v1"),
  );
  expect(credentialsBeforeRefresh).not.toBeNull();
  expect(credentialsAfterRefresh).not.toBe(credentialsBeforeRefresh);
});
