/**
 * Vérification Cloudflare Turnstile — activée uniquement si
 * TURNSTILE_SECRET_KEY est renseignée côté serveur. Sans cette variable,
 * la fonction est un no-op qui laisse passer la requête (le honeypot et la
 * limitation de requêtes restent actifs dans tous les cas).
 */
export async function verifyTurnstile(
  token: string | undefined,
  remoteIp: string | undefined,
): Promise<{ ok: boolean; skipped: boolean }> {
  const secretKey = process.env.TURNSTILE_SECRET_KEY;

  if (!secretKey) {
    return { ok: true, skipped: true };
  }

  if (!token) {
    return { ok: false, skipped: false };
  }

  try {
    const response = await fetch("https://challenges.cloudflare.com/turnstile/v0/siteverify", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        secret: secretKey,
        response: token,
        ...(remoteIp ? { remoteip: remoteIp } : {}),
      }),
    });

    const result = (await response.json()) as { success: boolean };
    return { ok: result.success === true, skipped: false };
  } catch (err) {
    console.error("[mi-loc] Échec de la vérification Turnstile:", err);
    return { ok: false, skipped: false };
  }
}
