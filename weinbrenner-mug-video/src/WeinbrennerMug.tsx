import { AbsoluteFill, Sequence, useVideoConfig } from "remotion";
import { VideoBase } from "./components/VideoBase";
import { Logo } from "./components/Logo";
import { Tagline } from "./components/Tagline";
import { Features } from "./components/Features";
import { CTA } from "./components/CTA";

// Segmentos del video (a 30fps):
// 0s-3s   : Intro — Video assembly + Logo aparece
// 3s-6s   : Producto girando + Features entran desde derecha
// 6s-10s  : Tagline aparece en la parte inferior
// 10s-15s : CTA con precio, fade-in de fondo blanco
// Total   : 15s = 450 frames

export const WeinbrennerMug: React.FC = () => {
  const { fps } = useVideoConfig();

  const SEC = (s: number) => Math.round(s * fps);

  return (
    <AbsoluteFill style={{ backgroundColor: "#FFFFFF" }}>
      {/* Video o imagen base — toda la duración */}
      <Sequence from={0}>
        <VideoBase />
      </Sequence>

      {/* Logo — aparece en el segundo 0.5 y se mantiene */}
      <Sequence from={SEC(0.5)}>
        <Logo />
      </Sequence>

      {/* Características — aparecen en el segundo 3 durante 5s */}
      <Sequence from={SEC(3)} durationInFrames={SEC(5)}>
        <Features />
      </Sequence>

      {/* Tagline — aparece en el segundo 6 durante 7s */}
      <Sequence from={SEC(6)} durationInFrames={SEC(7)}>
        <Tagline line1="Cada sorbo," line2="una experiencia." />
      </Sequence>

      {/* CTA + Precio — aparece en el segundo 10 hasta el final */}
      <Sequence from={SEC(10)}>
        <CTA price="$29.990" ctaText="Disponible en weinbrenner.cl" />
      </Sequence>
    </AbsoluteFill>
  );
};
