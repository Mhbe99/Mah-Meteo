import { ImageResponse } from "next/og";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { SITE } from "@/lib/config";

export const alt = `${SITE.name} — ${SITE.tagline}`;
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OpengraphImage() {
  const logoBuffer = readFileSync(join(process.cwd(), "public", "logo-mark.png"));
  const logoSrc = `data:image/png;base64,${logoBuffer.toString("base64")}`;

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          background: "linear-gradient(135deg, #0a0a0a 0%, #1c1c1e 60%, #0a0a0a 100%)",
          padding: 64,
        }}
      >
        <img src={logoSrc} width={420} height={223} alt="" />
        <div
          style={{
            marginTop: 28,
            fontSize: 30,
            color: "#d4b876",
            letterSpacing: 4,
            textTransform: "uppercase",
            display: "flex",
          }}
        >
          Recherche de véhicule sur mesure
        </div>
      </div>
    ),
    { ...size },
  );
}
