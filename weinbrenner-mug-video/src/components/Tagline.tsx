import { AbsoluteFill, useCurrentFrame, useVideoConfig, interpolate, Easing } from "remotion";

interface TaglineProps {
  line1?: string;
  line2?: string;
}

export const Tagline: React.FC<TaglineProps> = ({
  line1 = "Cada sorbo,",
  line2 = "una experiencia.",
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const makeAnim = (delay: number) => {
    const opacity = interpolate(frame, [delay, delay + fps * 0.7], [0, 1], {
      extrapolateRight: "clamp",
      extrapolateLeft: "clamp",
      easing: Easing.bezier(0.16, 1, 0.3, 1),
    });
    const translateX = interpolate(frame, [delay, delay + fps * 0.7], [-30, 0], {
      extrapolateRight: "clamp",
      extrapolateLeft: "clamp",
      easing: Easing.bezier(0.16, 1, 0.3, 1),
    });
    return { opacity, translateX };
  };

  const a1 = makeAnim(0);
  const a2 = makeAnim(Math.round(fps * 0.25));

  const textStyle: React.CSSProperties = {
    fontFamily: "'Georgia', serif",
    fontSize: 72,
    lineHeight: 1.1,
    color: "#1a1a1a",
    fontWeight: 400,
    margin: 0,
  };

  return (
    <AbsoluteFill
      style={{
        justifyContent: "flex-end",
        alignItems: "flex-start",
        padding: "0 56px 100px",
      }}
    >
      <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
        <p
          style={{
            ...textStyle,
            opacity: a1.opacity,
            transform: `translateX(${a1.translateX}px)`,
          }}
        >
          {line1}
        </p>
        <p
          style={{
            ...textStyle,
            fontStyle: "italic",
            color: "#C4956A",
            opacity: a2.opacity,
            transform: `translateX(${a2.translateX}px)`,
          }}
        >
          {line2}
        </p>
      </div>
    </AbsoluteFill>
  );
};
