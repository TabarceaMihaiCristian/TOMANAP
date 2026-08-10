import { expect, test } from "@playwright/test";

test("landing flow is usable without horizontal overflow", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: /șapte categorii/i })).toBeVisible();
  await expect(page.getByRole("button", { name: /creează joc/i })).toBeVisible();
  await expect
    .poll(() =>
      page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
    )
    .toBe(true);
});

test("join mode remains keyboard and touch accessible", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("tab", { name: /intră cu cod/i }).click();

  await expect(page.getByLabel(/codul camerei/i)).toBeVisible();
  await expect(page.getByLabel(/cum te cheamă/i)).toBeVisible();
  await expect(page.getByRole("button", { name: /intră în joc/i })).toBeVisible();
});
