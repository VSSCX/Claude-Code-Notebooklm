import { AbsoluteFill, Img, staticFile, useVideoConfig } from "remotion";

export const VideoBase: React.FC = () => {
  const { width, height } = useVideoConfig();

  return (
    <AbsoluteFill style={{ backgroundColor: "#FFFFFF" }}>
      {/* Cuando tengas el video de Higgsfield, reemplaza el Img por Video */}
      {/* <Video src={staticFile("assembly.mp4")} style={{ width, height, objectFit: "cover" }} /> */}
      <Img
        src={staticFile("mug.jpg")}
        style={{
          width,
          height,
          objectFit: "contain",
          objectPosition: "center",
        }}
      />
    </AbsoluteFill>
  );
};
