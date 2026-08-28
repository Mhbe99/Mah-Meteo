import { NextResponse, type NextRequest } from "next/server";
import { searchRequestSchema } from "@/lib/validation";
import { sendSearchRequestEmail } from "@/lib/email";
import { checkRateLimit } from "@/lib/rateLimit";
import { verifyTurnstile } from "@/lib/turnstile";

export const runtime = "nodejs";

function getClientIp(request: NextRequest): string {
  const forwardedFor = request.headers.get("x-forwarded-for");
  if (forwardedFor) return forwardedFor.split(",")[0]!.trim();

  const realIp = request.headers.get("x-real-ip");
  if (realIp) return realIp;

  return "unknown";
}

export async function POST(request: NextRequest) {
  const ip = getClientIp(request);

  const { allowed, retryAfterSeconds } = checkRateLimit(ip);
  if (!allowed) {
    return NextResponse.json(
      {
        success: false,
        message: "Trop de demandes envoyées. Merci de réessayer dans quelques minutes.",
      },
      { status: 429, headers: retryAfterSeconds ? { "Retry-After": String(retryAfterSeconds) } : {} },
    );
  }

  let rawBody: unknown;
  try {
    rawBody = await request.json();
  } catch {
    return NextResponse.json(
      { success: false, message: "Requête invalide." },
      { status: 400 },
    );
  }

  const parsed = searchRequestSchema.safeParse(rawBody);
  if (!parsed.success) {
    const firstIssue = parsed.error.issues[0];
    return NextResponse.json(
      {
        success: false,
        message: firstIssue?.message ?? "Merci de vérifier les informations saisies.",
      },
      { status: 400 },
    );
  }

  const data = parsed.data;

  // Honeypot rempli => très probablement un bot. On répond succès pour ne
  // pas donner d'indice, sans envoyer d'e-mail ni traiter la demande.
  if (data.website && data.website.length > 0) {
    return NextResponse.json({ success: true });
  }

  const turnstile = await verifyTurnstile(data.turnstileToken, ip);
  if (!turnstile.ok) {
    return NextResponse.json(
      {
        success: false,
        message: "Vérification anti-robot échouée. Merci de réessayer.",
      },
      { status: 400 },
    );
  }

  const result = await sendSearchRequestEmail(data);
  if (!result.success) {
    return NextResponse.json(
      {
        success: false,
        message:
          "Votre demande n'a pas pu être envoyée pour le moment. Merci de réessayer dans quelques instants.",
      },
      { status: 502 },
    );
  }

  return NextResponse.json({ success: true });
}
