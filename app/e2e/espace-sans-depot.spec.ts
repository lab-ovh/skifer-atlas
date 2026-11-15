import { execFileSync } from "node:child_process";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { expect, type Page } from "@playwright/test";
import { seriousViolations } from "./demo";
import { git, test, trackWorkspace } from "./isolation";

// Issue #160 (ADR 0065) : un espace créé sans dépôt distant n'a aucun domaine, donc aucun KPI.
// L'éditeur dit pourquoi et mène à l'Administration ; les propositions répondent sans erreur ;
// une fois le dépôt rattaché et un domaine créé, le premier concept se crée.

const unique = () => crypto.randomUUID().slice(0, 8);
const nav = (page: Page) => page.getByRole("navigation", { name: "Navigation de l'espace" });
const create = (page: Page) => page.getByRole("button", { name: "Créer et ouvrir l'éditeur" });
const NO_REMOTE = "Aucun domaine. Rattachez un dépôt distant puis créez un domaine dans l'Administration.";
const NO_DOMAIN = "Aucun domaine. Un référent crée les domaines dans l'Administration.";
const REFUSED = "Aucun domaine disponible : créez d'abord un domaine dans l'Administration.";

async function newDocument(page: Page) {
  await nav(page).getByRole("link", { name: "Catalogue" }).click();
  await page.getByRole("link", { name: "Nouveau concept ou KPI" }).click();
  await expect(create(page)).toBeVisible();
}

test("[S-UI-103-117] [S-UI-103-118] espace sans dépôt : l'éditeur explique l'absence de domaine, puis rattachement, domaine et premier concept", async ({ page }) => {
  test.setTimeout(120_000);
  const id = `sans-depot-${unique()}`;
  const root = mkdtempSync(join(tmpdir(), "atlas-sans-depot-"));
  const bare = join(root, "vide.git");
  trackWorkspace(id, root);
  execFileSync("git", ["init", "--bare", "--quiet", "--initial-branch=main", bare]);
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

  // [S-UI-103-117] Sans dépôt : le champ Domaine dit quoi faire, la création est refusée sans requête.
  await newDocument(page);
  await expect(page.getByText(NO_REMOTE, { exact: true })).toBeVisible();
  await expect(page.getByRole("combobox", { name: /^Domaine/ })).toHaveCount(0);
  await page.getByLabel(/^Libellé/).fill("Client actif");
  const posts: string[] = [];
  page.on("request", (request) => { if (request.method() === "POST") posts.push(request.url()); });
  await create(page).click();
  await expect(page.getByText(REFUSED, { exact: true })).toBeVisible();
  expect(posts).toEqual([]);
  expect(await seriousViolations(page)).toEqual([]);
  await page.getByRole("link", { name: "Administration", exact: true }).click();
  await expect(page.getByRole("heading", { level: 1, name: `Administration — Sans dépôt ${id}` })).toBeVisible();

  // Rattacher le dépôt vide.
  const attachment = page.getByRole("group", { name: "Rattacher un dépôt distant" });
  await attachment.getByLabel(/^Adresse du dépôt vide/).fill(bare);
  await attachment.getByRole("button", { name: "Rattacher le dépôt" }).click();
  await expect(page.getByText(`Dépôt rattaché : l'espace est publié sur ${bare}, sous le compte anna.k.`)).toBeVisible();

  // [S-UI-103-118] Rattaché mais sans domaine : le message change, la création reste refusée.
  await newDocument(page);
  await expect(page.getByText(NO_DOMAIN, { exact: true })).toBeVisible();
  await expect(page.getByText(NO_REMOTE, { exact: true })).toHaveCount(0);
  await page.getByRole("link", { name: "Administration", exact: true }).click();

  // Le référent crée un domaine ; l'enregistrement fusionne aussitôt (seul compte habilité).
  const domains = page.getByRole("region", { name: "Domaines métier" });
  await domains.getByRole("button", { name: "Domaine", exact: true }).click();
  const form = page.getByRole("group", { name: "Nouveau domaine" });
  await form.getByLabel(/^Libellé/).fill("Ventes");
  await form.getByRole("button", { name: "Ajouter le domaine" }).click();
  await expect(form).toHaveCount(0);
  await page.getByRole("button", { name: /^Enregistrer et/ }).click();
  await expect(page.getByText(/Paramètres enregistrés : proposition n° \d+ fusionnée sans revue\./)).toBeVisible();
  expect(git(bare, "show", "main:governance.yaml")).toContain("id: ventes");

  // Le domaine est proposé, sans nouveau chargement de l'application, et le concept se crée.
  await newDocument(page);
  await expect(page.getByText(NO_DOMAIN, { exact: true })).toHaveCount(0);
  await page.getByLabel(/^Libellé/).fill("Client actif");
  await page.getByLabel(/^Domaine/).selectOption("ventes");
  await create(page).click();
  await expect(page.getByRole("heading", { level: 1, name: /^Client actif : v1 · brouillon/ })).toBeVisible();

  expect(refused).toEqual([]);
});
