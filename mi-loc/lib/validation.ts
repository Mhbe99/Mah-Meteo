import { z } from "zod";

export const CONTACT_METHODS = ["telephone", "sms", "whatsapp", "email"] as const;
export const FUEL_TYPES = [
  "essence",
  "diesel",
  "hybride",
  "hybride_rechargeable",
  "electrique",
  "peu_importe",
] as const;
export const GEARBOX_TYPES = ["automatique", "manuelle", "peu_importe"] as const;
export const VEHICLE_TYPES = [
  "citadine",
  "berline",
  "suv",
  "break",
  "coupe",
  "cabriolet",
  "utilitaire",
  "autre",
  "peu_importe",
] as const;
export const TIMELINE_OPTIONS = [
  "des_que_possible",
  "moins_2_semaines",
  "moins_1_mois",
  "1_a_3_mois",
  "je_regarde",
] as const;

export const CONTACT_METHOD_LABELS: Record<(typeof CONTACT_METHODS)[number], string> = {
  telephone: "Téléphone",
  sms: "SMS",
  whatsapp: "WhatsApp",
  email: "E-mail",
};

export const FUEL_LABELS: Record<(typeof FUEL_TYPES)[number], string> = {
  essence: "Essence",
  diesel: "Diesel",
  hybride: "Hybride",
  hybride_rechargeable: "Hybride rechargeable",
  electrique: "Électrique",
  peu_importe: "Peu importe",
};

export const GEARBOX_LABELS: Record<(typeof GEARBOX_TYPES)[number], string> = {
  automatique: "Automatique",
  manuelle: "Manuelle",
  peu_importe: "Peu importe",
};

export const VEHICLE_TYPE_LABELS: Record<(typeof VEHICLE_TYPES)[number], string> = {
  citadine: "Citadine",
  berline: "Berline",
  suv: "SUV",
  break: "Break",
  coupe: "Coupé",
  cabriolet: "Cabriolet",
  utilitaire: "Utilitaire",
  autre: "Autre",
  peu_importe: "Peu importe",
};

export const TIMELINE_LABELS: Record<(typeof TIMELINE_OPTIONS)[number], string> = {
  des_que_possible: "Dès que possible",
  moins_2_semaines: "Moins de 2 semaines",
  moins_1_mois: "Moins d'un mois",
  "1_a_3_mois": "1 à 3 mois",
  je_regarde: "Je regarde simplement",
};

// Regex volontairement souple : accepte les formats FR (06 12 34 56 78,
// +33 6 12 34 56 78) et internationaux courants.
const PHONE_REGEX = /^[\d\s().+-]{6,20}$/;

const emptyToUndefined = (val: unknown) =>
  typeof val === "string" && val.trim() === "" ? undefined : val;

const optionalTrimmedString = (max: number) =>
  z.preprocess(emptyToUndefined, z.string().trim().max(max).optional());

export const searchRequestSchema = z
  .object({
    // Honeypot : doit rester vide. Un bot qui remplit ce champ est démasqué
    // (traité côté API, qui répond succès sans envoyer d'e-mail).
    website: z.string().max(200).optional().default(""),

    firstName: z
      .string({ required_error: "Merci d'indiquer votre prénom." })
      .trim()
      .min(1, "Merci d'indiquer votre prénom.")
      .max(80, "Prénom trop long."),
    lastName: optionalTrimmedString(80),
    phone: z.preprocess(
      emptyToUndefined,
      z
        .string()
        .trim()
        .regex(PHONE_REGEX, "Numéro de téléphone invalide.")
        .optional(),
    ),
    email: z.preprocess(
      emptyToUndefined,
      z.string().trim().email("Adresse e-mail invalide.").max(120).optional(),
    ),
    preferredContactMethod: z.enum(CONTACT_METHODS, {
      errorMap: () => ({ message: "Merci de choisir un moyen de contact." }),
    }),

    brand: optionalTrimmedString(60),
    model: optionalTrimmedString(60),
    maxBudget: z.coerce
      .number({ invalid_type_error: "Merci d'indiquer votre budget maximum." })
      .int()
      .positive("Le budget doit être supérieur à 0.")
      .max(2_000_000, "Budget invalide."),
    minYear: z.preprocess(
      emptyToUndefined,
      z.coerce.number().int().min(1980).max(2100).optional(),
    ),
    maxMileage: z.preprocess(
      emptyToUndefined,
      z.coerce.number().int().min(0).max(2_000_000).optional(),
    ),
    fuelType: z.preprocess(emptyToUndefined, z.enum(FUEL_TYPES).optional()),
    gearbox: z.preprocess(emptyToUndefined, z.enum(GEARBOX_TYPES).optional()),
    vehicleType: z.preprocess(emptyToUndefined, z.enum(VEHICLE_TYPES).optional()),

    details: optionalTrimmedString(2000),
    color: optionalTrimmedString(60),
    mustHaveEquipment: optionalTrimmedString(500),
    timeline: z.preprocess(emptyToUndefined, z.enum(TIMELINE_OPTIONS).optional()),

    consent: z.literal(true, {
      errorMap: () => ({
        message: "Merci d'accepter que MI LOC vous recontacte au sujet de votre recherche.",
      }),
    }),

    // Rempli côté client uniquement si Turnstile est configuré.
    turnstileToken: z.string().optional(),
  })
  .refine((data) => Boolean(data.phone) || Boolean(data.email), {
    message: "Merci de renseigner au moins un numéro de téléphone ou une adresse e-mail.",
    path: ["phone"],
  });

export type SearchRequestInput = z.infer<typeof searchRequestSchema>;
