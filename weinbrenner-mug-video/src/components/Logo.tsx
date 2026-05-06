import { AbsoluteFill, useCurrentFrame, useVideoConfig, interpolate, Easing } from "remotion";

export const Logo: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const opacity = interpolate(frame, [0, fps * 0.8], [0, 1], {
    extrapolateRight: "clamp",
    extrapolateLeft: "clamp",
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });

  const translateY = interpolate(frame, [0, fps * 0.8], [20, 0], {
    extrapolateRight: "clamp",
    extrapolateLeft: "clamp",
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });

  return (
    <AbsoluteFill
      style={{
        justifyContent: "flex-start",
        alignItems: "flex-start",
        padding: "48px 56px",
      }}
    >
      <div
        style={{
          opacity,
          transform: `translateY(${translateY}px)`,
          display: "flex",
          flexDirection: "column",
          gap: 4,
        }}
      >
        <span
          style={{
            fontFamily: "'Georgia', serif",
            fontSize: 32,
            fontWeight: 700,
            letterSpacing: "0.18em",
            color: "#1a1a1a",
            textTransform: "uppercase",
          }}
        >
          WEINBRENNER
        </span>
        <div
          style={{
            height: 2,
            width: "100%",
            backgroundColor: "#C4956A",
            borderRadius: 1,
          }}
        />
        <span
          style={{
            fontFamily: "'Georgia', serif",
            fontSize: 13,
            letterSpacing: "0.3em",
            color: "#888",
            textTransform: "uppercase",
          }}
        >
          PREMIUM LIFESTYLE
        </span>
      </div>
    </AbsoluteFill>
  );
};
