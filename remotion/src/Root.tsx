import React from "react";
import { Composition, staticFile } from "remotion";
import { loadFont } from "@remotion/fonts";
import { Reel, ReelProps } from "./Reel";
import { SANS, MONO } from "./lib";
import sample from "./sample_props.json";

loadFont({ family: SANS, url: staticFile("InterDisplay-SemiBold.otf"), weight: "600" });
loadFont({ family: SANS, url: staticFile("InterDisplay-Bold.otf"), weight: "700" });
loadFont({ family: SANS, url: staticFile("InterDisplay-ExtraBold.otf"), weight: "800" });
loadFont({ family: SANS, url: staticFile("InterDisplay-Black.otf"), weight: "900" });
loadFont({ family: MONO, url: staticFile("JetBrainsMono.ttf"), weight: "100 900" });

export const RemotionRoot: React.FC = () => (
  <Composition
    id="Reel"
    component={Reel as unknown as React.FC<Record<string, unknown>>}
    durationInFrames={300}
    fps={30}
    width={1080}
    height={1920}
    defaultProps={sample as unknown as Record<string, unknown>}
    calculateMetadata={({ props }) => ({ durationInFrames: Math.ceil(((props as unknown as ReelProps).duration + 3) * 30) })}
  />
);
