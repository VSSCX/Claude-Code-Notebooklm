import { AbsoluteFill, useCurrentFrame, useVideoConfig, interpolate, Easing } from "remotion";

const FEATURES = [
  { icon: "◈", label: "Acero Inoxidable", sub: "316L Premium" },
  { icon: "❄", label: "Doble Pared", sub: "Mantiene temperatura" },
  { icon: "◉", label: "Tapa Hermética", sub: "Antigoteo 100%" },
  { icon: "♻", label: "Eco-Friendly", sub: "Libre de BPA" },
];

export const Features: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "flex-end",
        padding: "0 56px",
        flexDirection: "column",
        gap: 20,
      }}
    >
      {FEATURES.map((feat, i) => {
        const delay = i * Math.round(fps * 0.15);
        const opacity = interpolate(frame, [delay, delay + fps * 0.5], [0, 1], {
          extrapolateRight: "clamp",
          extrapolateLeft: "clamp",
          easing: Easing.bezier(0.16, 1, 0.3, 1),
        });
        const translateX = interpolate(frame, [delay, delay + fps * 0.5], [40, 0], {
          extrapolateRight: "clamp",
          extrapolateLeft: "clamp",
          easing: Easing.bezier(0.16, 1, 0.3, 1),
        });

        return (
          <div
            key={feat.label}
            style={{
              opacity,
              transform: `translateX(${translateX}px)`,
              display: "flex",
              alignItems: "center",
              gap: 16,
              backgroundColor: "rgba(255,255,255,0.88)",
              backdropFilter: "blur(12px)",
              borderRadius: 16,
              padding: "12px 20px",
              boxShadow: "0 4px 24px rgba(0,0,0,0.07)",
              border: "1px solid rgba(196,149,106,0.2)",
              minWidth: 240,
            }}
          >
            <span style={{ fontSize: 24, color: "#C4956A" }}>{feat.icon}</span>
            <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
              <span
                style={{
                  fontFamily: "'Georgia', serif",
                  fontSize: 15,
                  fontWeight: 700,
                  color: "#1a1a1a",
                  letterSpacing: "0.04em",
                }}
              >
                {feat.label}
              </span>
              <span
                style={{
                  fontFamily: "sans-serif",
                  fontSize: 12,
                  color: "#888",
                  letterSpacing: "0.06em",
                }}
              >
                {feat.sub}
              </span>
            </div>
          </div>
        );
      })}
    </AbsoluteFill>
  );
};
