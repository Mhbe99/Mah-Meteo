/**
 * Paramètres MI LOC — fichier central à modifier pour mettre à jour les
 * informations affichées sur le site (coordonnées, réseaux sociaux, grille
 * de commission) sans toucher aux composants.
 */

export const SITE = {
  name: "MI LOC",
  tagline: "Mobilité & Location",
  baseUrl: "https://www.mi-loc.fr", // TODO: remplacer par le domaine définitif
};

/**
 * Coordonnées publiques affichées dans le footer / la page contact.
 * Laisser une valeur vide ("") tant qu'elle n'a pas été communiquée :
 * les composants masquent automatiquement les champs vides.
 */
export const CONTACT = {
  phoneDisplay: "", // ex: "01 23 45 67 89"
  phoneHref: "", // ex: "+33123456789"
  email: "", // ex: "contact@mi-loc.fr" (affichage public, distinct de CONTACT_EMAIL serveur)
  address: "", // ex: "12 rue de l'Automobile, 75000 Paris"
  siren: "", // ex: "123 456 789 RCS Paris"
};

export const SOCIAL_LINKS = {
  instagram: "", // ex: "https://instagram.com/mi.loc"
  facebook: "", // ex: "https://facebook.com/mi.loc"
  linkedin: "", // ex: "https://linkedin.com/company/mi-loc"
};

/**
 * Grille de commission MI LOC.
 *
 * Tant que cette liste est vide, le site affiche un message générique
 * ("commission communiquée avant le lancement de la recherche"). Pour
 * publier une grille, ajouter des lignes de ce type :
 *
 * export const COMMISSION_GRID: CommissionTier[] = [
 *   { range: "Véhicule de 2015 à 2018", commission: "500 €" },
 *   { range: "Véhicule de 2019 à 2022", commission: "700 €" },
 *   { range: "Véhicule 2023 et plus", commission: "900 €" },
 * ];
 */
export type CommissionTier = {
  range: string;
  commission: string;
};

export const COMMISSION_GRID: CommissionTier[] = [];

export const LEGAL_LINKS = {
  mentionsLegales: "/mentions-legales",
  confidentialite: "/politique-de-confidentialite",
  contact: "/contact",
};
