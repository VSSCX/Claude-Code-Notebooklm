import "./index.css";
import { Composition } from "remotion";
import { WeinbrennerMug } from "./WeinbrennerMug";

// Formato 9:16 para Reels/TikTok (1080x1920)
// Formato 1:1 para Feed (1080x1080) — descomentar el segundo Composition

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="WeinbrennerMug-Reel"
        component={WeinbrennerMug}
        durationInFrames={450}
        fps={30}
        width={1080}
        height={1920}
      />
      <Composition
        id="WeinbrennerMug-Feed"
        component={WeinbrennerMug}
        durationInFrames={450}
        fps={30}
        width={1080}
        height={1080}
      />
    </>
  );
};
