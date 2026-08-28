import { Resend } from "resend";
import {
  CONTACT_METHOD_LABELS,
  FUEL_LABELS,
  GEARBOX_LABELS,
  TIMELINE_LABELS,
  VEHICLE_TYPE_LABELS,
  type SearchRequestInput,
} from "./validation";

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function fmtCurrency(value?: number): string {
  if (value === undefined) return "—";
  return new Intl.NumberFormat("fr-FR").format(value) + " €";
}

function fmtKm(value?: number): string {
  if (value === undefined) return "—";
  return new Intl.NumberFormat("fr-FR").format(value) + " km";
}

function line(label: string, value: string | undefined): string {
  return `${label} : ${value && value.trim() !== "" ? value : "—"}`;
}

function row(label: string, value: string | undefined): string {
  const safeValue = value && value.trim() !== "" ? escapeHtml(value) : "—";
  return `
    <tr>
      <td style="padding:6px 12px 6px 0;color:#6b6b6b;font-size:13px;white-space:nowrap;vertical-align:top;">${escapeHtml(label)}</td>
      <td style="padding:6px 0;color:#111111;font-size:14px;vertical-align:top;">${safeValue}</td>
    </tr>`;
}

export function buildRequestSubject(data: SearchRequestInput): string {
  const vehicle = [data.brand, data.model].filter(Boolean).join(" ").trim();
  const suffix = vehicle || "Recherche personnalisée";
  return `🚗 Nouvelle recherche véhicule MI LOC – ${data.firstName} – ${suffix}`;
}

export function buildRequestTextBody(data: SearchRequestInput): string {
  const now = new Intl.DateTimeFormat("fr-FR", {
    dateStyle: "long",
    timeStyle: "short",
    timeZone: "Europe/Paris",
  }).format(new Date());

  return [
    "NOUVELLE DEMANDE MI LOC",
    "",
    "CLIENT",
    line("Prénom", data.firstName),
    line("Nom", data.lastName),
    line("Téléphone", data.phone),
    line("E-mail", data.email),
    line("Contact préféré", CONTACT_METHOD_LABELS[data.preferredContactMethod]),
    "",
    "RECHERCHE",
    line("Marque", data.brand),
    line("Modèle", data.model),
    line("Budget maximum", fmtCurrency(data.maxBudget)),
    line("Année minimum", data.minYear?.toString()),
    line("Kilométrage maximum", fmtKm(data.maxMileage)),
    line("Carburant", data.fuelType ? FUEL_LABELS[data.fuelType] : undefined),
    line("Boîte", data.gearbox ? GEARBOX_LABELS[data.gearbox] : undefined),
    line("Type", data.vehicleType ? VEHICLE_TYPE_LABELS[data.vehicleType] : undefined),
    line("Couleur", data.color),
    line("Délai", data.timeline ? TIMELINE_LABELS[data.timeline] : undefined),
    line("Équipements", data.mustHaveEquipment),
    "",
    "MESSAGE / PRÉCISIONS :",
    data.details && data.details.trim() !== "" ? data.details : "—",
    "",
    `Date de la demande : ${now}`,
  ].join("\n");
}

export function buildRequestHtmlBody(data: SearchRequestInput): string {
  const now = new Intl.DateTimeFormat("fr-FR", {
    dateStyle: "long",
    timeStyle: "short",
    timeZone: "Europe/Paris",
  }).format(new Date());

  const replyHref = data.email
    ? `mailto:${encodeURIComponent(data.email)}?subject=${encodeURIComponent(
        `RE: Votre recherche véhicule MI LOC`,
      )}`
    : null;

  return `
  <div style="font-family:'Helvetica Neue',Arial,sans-serif;background:#f6f3ec;padding:32px 16px;">
    <div style="max-width:600px;margin:0 auto;background:#ffffff;border-radius:16px;overflow:hidden;border:1px solid #ececec;">
      <div style="background:#0a0a0a;padding:24px 28px;">
        <p style="margin:0;color:#d4b876;font-size:12px;letter-spacing:0.14em;text-transform:uppercase;">MI LOC</p>
        <h1 style="margin:6px 0 0;color:#ffffff;font-size:19px;font-weight:600;">Nouvelle demande de recherche véhicule</h1>
      </div>

      <div style="padding:24px 28px;">
        <h2 style="font-size:13px;letter-spacing:0.08em;text-transform:uppercase;color:#b8964f;margin:0 0 8px;">Client</h2>
        <table role="presentation" style="width:100%;border-collapse:collapse;margin-bottom:20px;">
          ${row("Prénom", data.firstName)}
          ${row("Nom", data.lastName)}
          ${row("Téléphone", data.phone)}
          ${row("E-mail", data.email)}
          ${row("Contact préféré", CONTACT_METHOD_LABELS[data.preferredContactMethod])}
        </table>

        <h2 style="font-size:13px;letter-spacing:0.08em;text-transform:uppercase;color:#b8964f;margin:0 0 8px;">Recherche</h2>
        <table role="presentation" style="width:100%;border-collapse:collapse;margin-bottom:20px;">
          ${row("Marque", data.brand)}
          ${row("Modèle", data.model)}
          ${row("Budget maximum", fmtCurrency(data.maxBudget))}
          ${row("Année minimum", data.minYear?.toString())}
          ${row("Kilométrage maximum", fmtKm(data.maxMileage))}
          ${row("Carburant", data.fuelType ? FUEL_LABELS[data.fuelType] : undefined)}
          ${row("Boîte", data.gearbox ? GEARBOX_LABELS[data.gearbox] : undefined)}
          ${row("Type", data.vehicleType ? VEHICLE_TYPE_LABELS[data.vehicleType] : undefined)}
          ${row("Couleur", data.color)}
          ${row("Délai", data.timeline ? TIMELINE_LABELS[data.timeline] : undefined)}
          ${row("Équipements", data.mustHaveEquipment)}
        </table>

        <h2 style="font-size:13px;letter-spacing:0.08em;text-transform:uppercase;color:#b8964f;margin:0 0 8px;">Message / précisions</h2>
        <p style="white-space:pre-wrap;font-size:14px;line-height:1.6;color:#111111;background:#f6f3ec;border-radius:10px;padding:14px 16px;margin:0 0 20px;">${
          data.details && data.details.trim() !== "" ? escapeHtml(data.details) : "—"
        }</p>

        ${
          replyHref
            ? `<a href="${replyHref}" style="display:inline-block;background:#0a0a0a;color:#ffffff;text-decoration:none;padding:12px 22px;border-radius:999px;font-size:14px;font-weight:600;">Répondre à ${escapeHtml(
                data.email as string,
              )}</a>`
            : ""
        }

        <p style="margin-top:24px;color:#8a8a8a;font-size:12px;">Date de la demande : ${escapeHtml(now)}</p>
      </div>
    </div>
  </div>`;
}

export type SendSearchRequestEmailResult = { success: true } | { success: false; error: string };

export async function sendSearchRequestEmail(
  data: SearchRequestInput,
): Promise<SendSearchRequestEmailResult> {
  const apiKey = process.env.RESEND_API_KEY;
  const contactEmail = process.env.CONTACT_EMAIL;
  const fromEmail = process.env.RESEND_FROM_EMAIL || "MI LOC <onboarding@resend.dev>";

  if (!apiKey || !contactEmail) {
    console.error(
      "[mi-loc] RESEND_API_KEY ou CONTACT_EMAIL manquant : impossible d'envoyer la demande par e-mail.",
    );
    return { success: false, error: "server_misconfigured" };
  }

  const resend = new Resend(apiKey);

  try {
    const { error } = await resend.emails.send({
      from: fromEmail,
      to: [contactEmail],
      replyTo: data.email || undefined,
      subject: buildRequestSubject(data),
      text: buildRequestTextBody(data),
      html: buildRequestHtmlBody(data),
    });

    if (error) {
      console.error("[mi-loc] Échec envoi e-mail Resend:", error);
      return { success: false, error: "send_failed" };
    }

    return { success: true };
  } catch (err) {
    console.error("[mi-loc] Exception lors de l'envoi de l'e-mail:", err);
    return { success: false, error: "send_exception" };
  }
}
