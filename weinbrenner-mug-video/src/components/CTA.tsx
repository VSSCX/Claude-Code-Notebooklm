import { AbsoluteFill, useCurrentFrame, useVideoConfig, interpolate, Easing } from "remotion";

interface CTAProps {
  price?: string;
  ctaText?: string;
}

export const CTA: React.FC<CTAProps> = ({
  price = "$29.990",
  ctaText = "Disponible en weinbrenner.cl",
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const bgOpacity = interpolate(frame, [0, fps * 0.5], [0, 1], {
    extrapolateRight: "clamp",
    extrapolateLeft: "clamp",
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });

  const scalePrice = interpolate(frame, [fps * 0.2, fps * 0.8], [0.7, 1], {
    extrapolateRight: "clamp",
    extrapolateLeft: "clamp",
    easing: Easing.bezier(0.34, 1.56, 0.64, 1),
  });

  const opacityPrice = interpolate(frame, [fps * 0.2, fps * 0.8], [0, 1], {
    extrapolateRight: "clamp",
    extrapolateLeft: "clamp",
  });

  const opacityLink = interpolate(frame, [fps * 0.6, fps * 1.0], [0, 1], {
    extrapolateRight: "clamp",
    extrapolateLeft: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        justifyContent: "flex-end",
        alignItems: "center",
        paddingBottom: 0,
      }}
    >
      <div
        style={{
          opacity: bgOpacity,
          width: "100%",
          background: "linear-gradient(180deg, rgba(255,255,255,0) 0%, rgba(255,255,255,0.97) 40%, #fff 100%)",
          padding: "60px 56px 56px",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 16,
        }}
      >
        <div
          style={{
            opacity: opacityPrice,
            transform: `scale(${scalePrice})`,
            display: "flex",
            alignItems: "baseline",
            gap: 8,
          }}
        >
          <span
            style={{
              fontFamily: "'Georgia', serif",
              fontSize: 18,
              color: "#888",
              letterSpacing: "0.1em",
              textTransform: "uppercase",
            }}
          >
            Solo
          </span>
          <span
            style={{
              fontFamily: "'Georgia', serif",
              fontSize: 64,
              fontWeight: 700,
              color: "#1a1a1a",
              letterSpacing: "-0.02em",
            }}
          >
            {price}
          </span>
        </div>

        <div
          style={{
            opacity: opacityLink,
            backgroundColor: "#1a1a1a",
            borderRadius: 100,
            padding: "16px 48px",
            display: "flex",
            alignItems: "center",
            gap: 12,
          }}
        >
          <span
            style={{
              fontFamily: "sans-serif",
              fontSize: 18,
              color: "#FFFFFF",
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              fontWeight: 600,
            }}
          >
            {ctaText}
          </span>
        </div>

        <div
          style={{
            width: 40,
            height: 3,
            backgroundColor: "#C4956A",
            borderRadius: 2,
            opacity: opacityLink,
          }}
        />
      </div>
    </AbsoluteFill>
  );
};
