import { expect, type Page, test } from "@playwright/test";

const roundCount = 3;

async function completeRound(page: Page, playerName: string, roundNumber: number) {
  const heading = page.getByRole("heading", { name: /litera [a-z]/i });
  await expect(heading).toBeVisible();
  const headingText = (await heading.textContent()) ?? "";
  const letter = /litera\s+([a-z])/i.exec(headingText)?.[1]?.toUpperCase();
  expect(letter).toMatch(/^[A-Z]$/);

  const inputs = page.getByRole("textbox");
  await expect(inputs).toHaveCount(7);
  for (let index = 0; index < 7; index += 1) {
    const input = inputs.nth(index);
    await expect(input).toBeEditable();
    await input.fill(
      `${letter ?? "A"}${playerName}${String(roundNumber)}${String(index)}`,
    );
  }
  await page.getByRole("button", { name: /trimite răspunsurile/i }).click();
}

test("two players complete every round and reach the final leaderboard", async ({
  baseURL,
  browser,
  page: host,
}, testInfo) => {
  test.skip(
    process.env.TOMANAP_E2E_BACKEND !== "1",
    "Set TOMANAP_E2E_BACKEND=1 and start the backend to run this journey",
  );
  test.skip(
    testInfo.project.name !== "desktop-chromium",
    "The full multiplayer journey runs once; responsive behavior has separate coverage",
  );
  test.setTimeout(120_000);

  const guestContext = await browser.newContext({ baseURL });
  const guest = await guestContext.newPage();
  try {
    await host.goto("/");
    await host.getByLabel(/cum te cheamă/i).fill("Mihai");
    await host.getByLabel("Runde").selectOption(String(roundCount));
    await host.getByRole("button", { name: /creează joc/i }).click();
    await expect(host).toHaveURL(/\/room\/[A-Z0-9]{6}$/);

    const roomCode = /\/room\/([A-Z0-9]{6})$/.exec(host.url())?.[1] ?? "";
    expect(roomCode).toMatch(/^[A-Z0-9]{6}$/);

    await guest.goto("/");
    await guest.getByRole("tab", { name: /intră cu cod/i }).click();
    await guest.getByLabel(/codul camerei/i).fill(roomCode);
    await guest.getByLabel(/cum te cheamă/i).fill("Ana");
    await guest.getByRole("button", { name: /intră în joc/i }).click();
    await expect(guest).toHaveURL(`/room/${roomCode}`);

    await guest.getByRole("button", { name: /sunt gata/i }).click();
    const startGame = host.getByRole("button", { name: /pornește jocul/i });
    await expect(startGame).toBeEnabled({ timeout: 15_000 });
    await startGame.click();
    await expect(host).toHaveURL(`/room/${roomCode}/play`);
    await expect(guest).toHaveURL(`/room/${roomCode}/play`, { timeout: 15_000 });

    for (let roundNumber = 1; roundNumber <= roundCount; roundNumber += 1) {
      await test.step(`round ${String(roundNumber)}: host submits`, async () => {
        await completeRound(host, "Mihai", roundNumber);
      });
      await test.step(`round ${String(roundNumber)}: guest submits`, async () => {
        await completeRound(guest, "Ana", roundNumber);
      });
      await expect(host).toHaveURL(new RegExp(`/room/${roomCode}/review/[a-f0-9-]+$`), {
        timeout: 15_000,
      });
      await expect(guest).toHaveURL(new RegExp(`/room/${roomCode}/review/[a-f0-9-]+$`), {
        timeout: 15_000,
      });
      await expect(
        host.getByRole("heading", { name: /rezultatele rundei/i }),
      ).toBeVisible();

      await host.getByRole("button", { name: /runda următoare|vezi podiumul/i }).click();

      if (roundNumber < roundCount) {
        await expect(host).toHaveURL(`/room/${roomCode}/play`);
        await expect(guest).toHaveURL(`/room/${roomCode}/play`, {
          timeout: 15_000,
        });
      } else {
        await expect(host).toHaveURL(`/room/${roomCode}/results`);
        await expect(guest).toHaveURL(`/room/${roomCode}/results`, {
          timeout: 15_000,
        });
      }
    }

    await expect(
      host.getByRole("heading", { name: /avem un câștigător/i }),
    ).toBeVisible();
    await expect(
      guest.getByRole("heading", { name: /avem un câștigător/i }),
    ).toBeVisible();
  } finally {
    await guestContext.close();
  }
});
