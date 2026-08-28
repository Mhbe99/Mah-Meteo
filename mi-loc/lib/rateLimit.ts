/**
 * Limitation de requêtes en mémoire, par adresse IP.
 *
 * Volontairement simple (pas de dépendance externe / Redis) : suffisant pour
 * dissuader les envois automatisés répétés sur une instance Node classique.
 * Sur un déploiement multi-instances / serverless, chaque instance a son
 * propre compteur — ce n'est donc qu'une protection de premier niveau, à
 * compléter le cas échéant par un service dédié (Cloudflare, Upstash…).
 */

type Bucket = {
  count: number;
  windowStart: number;
};

const buckets = new Map<string, Bucket>();

const WINDOW_MS = 15 * 60 * 1000; // 15 minutes
const MAX_REQUESTS_PER_WINDOW = 5;

// Purge périodique pour éviter une fuite mémoire sur le long terme.
setInterval(
  () => {
    const now = Date.now();
    for (const [key, bucket] of buckets) {
      if (now - bucket.windowStart > WINDOW_MS) {
        buckets.delete(key);
      }
    }
  },
  10 * 60 * 1000,
).unref?.();

export function checkRateLimit(identifier: string): { allowed: boolean; retryAfterSeconds?: number } {
  const now = Date.now();
  const bucket = buckets.get(identifier);

  if (!bucket || now - bucket.windowStart > WINDOW_MS) {
    buckets.set(identifier, { count: 1, windowStart: now });
    return { allowed: true };
  }

  if (bucket.count >= MAX_REQUESTS_PER_WINDOW) {
    const retryAfterSeconds = Math.ceil((WINDOW_MS - (now - bucket.windowStart)) / 1000);
    return { allowed: false, retryAfterSeconds };
  }

  bucket.count += 1;
  return { allowed: true };
}
