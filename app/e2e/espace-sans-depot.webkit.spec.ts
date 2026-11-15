import { expect } from "@playwright/test";
import { seriousViolations } from "./demo";
import { test, trackWorkspace } from "./isolation";

// Issue #160 sous WebKit : sans dépôt distant, le champ Domaine de « Nouveau concept ou KPI »
// explique quoi faire, mène à l'Administration, et la création est refusée sans requête.

test("[S-UI-103-119] WebKit : espace sans dépôt, l'éditeur explique l'absence de domaine et mène à l'Administration", async ({ page }) => {
  const id = `sans-depot-${crypto.randomUUID().slice(0, 8)}`;
  trackWorkspace(id);
  const refused: string[] = [];
  page.on("response", (response) => {
    if (response.url().includes("/proposals") && response.status() >= 400) refused.push(`${response.status()} ${response.url()}`);
  });
  await page.goto("/#/");
  await page.getByRole("button", { name: "Créer un espace" }).click();
  const dialog = page.getByRole("dialog", { name: "Créer un espace" });
  await dialog.getByLabel(/^Nom/).fill(`Sans dépôt ${id}`);
  await dialog.getByLabel(/^Identifiant/).fill(id);
  await dialog.getByLabel("Entités").fill("perrault-fr");
  await dialog.getByRole("button", { name: "Créer l'espace" }).click();
  await expect(page).toHaveURL(new RegExp(`#/w/${id}/catalogue$`));

  await page.getByRole("link", { name: "Nouveau concept ou KPI" }).click();
  await expect(page.getByText("Aucun domaine. Rattachez un dépôt distant puis créez un domaine dans l'Administration.", { exact: true })).toBeVisible();
  await expect(page.getByRole("combobox", { name: /^Domaine/ })).toHaveCount(0);
  await page.getByLabel(/^Libellé/).fill("Client actif");
  const posts: string[] = [];
  page.on("request", (request) => { if (request.method() === "POST") posts.push(request.url()); });
  await page.getByRole("button", { name: "Créer et ouvrir l'éditeur" }).click();
  await expect(page.getByText("Aucun domaine disponible : créez d'abord un domaine dans l'Administration.", { exact: true })).toBeVisible();
  expect(posts).toEqual([]);
  expect(await seriousViolations(page)).toEqual([]);
  await page.getByRole("link", { name: "Administration", exact: true }).click();
  await expect(page.getByRole("heading", { level: 1, name: `Administration — Sans dépôt ${id}` })).toBeVisible();
  await expect(page.getByText("Cet espace n'a pas encore de dépôt distant", { exact: true })).toBeVisible();
  expect(refused).toEqual([]);
});
