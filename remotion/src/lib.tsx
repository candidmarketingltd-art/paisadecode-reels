import React, { createContext, useContext } from "react";
import { interpolate, spring, useCurrentFrame, Easing, Img, staticFile, random } from "remotion";

export const FPS = 30;
export const COL = {
  bg: "#0A0A0B", edge: "rgba(255,255,255,0.09)", txt: "#EEECE6", dim: "#4A4A4A", mute: "#8C8C88",
  gold: "#F5C242", blue: "#6EBEFF", red: "#EE5454", green: "#54D68C", ink: "#0C0C0C",
};
export const PALETTE: Record<string, string> = { gold: COL.gold, white: COL.txt, blue: COL.blue, red: COL.red, green: COL.green, muted: COL.mute };
export const col = (c?: string, d = COL.txt) => (c && PALETTE[c]) || d;
export const SANS = "InterD";
export const MONO = "JBMono";
export const clamp = { extrapolateLeft: "clamp" as const, extrapolateRight: "clamp" as const };
export const easeOut = Easing.bezier(0.16, 1, 0.3, 1);
export const fx = (s: number) => s * FPS;

export const SceneCtx = createContext<{ end: number }>({ end: 1e9 });

/** auto-fit font size so a single line fits `w` px */
export const fit = (text: string, w: number, max: number, k = 0.56) => Math.min(max, w / Math.max(1, text.length * k));

/** spring-in from `at`: rise + scale + blur-to-sharp; exits with the scene */
export const Reveal: React.FC<{ at: number; children: React.ReactNode; style?: React.CSSProperties; dy?: number; scale?: number; blur?: number; damping?: number; dim?: number; tilt?: number }> = ({
  at, children, style, dy = 46, scale = 0.92, blur = 14, damping = 13, dim, tilt = 0,
}) => {
  const f = useCurrentFrame();
  const { end } = useContext(SceneCtx);
  if (f < fx(at) - 1) return null;
  const s = spring({ frame: f - fx(at), fps: FPS, config: { damping, stiffness: 150, mass: 0.85 } });
  const lin = interpolate(f, [fx(at), fx(at) + 9], [0, 1], clamp);
  const out = interpolate(f, [fx(end) - 2, fx(end) + 8], [0, 1], { ...clamp, easing: Easing.in(Easing.cubic) });
  const dimK = dim === undefined ? 1 : interpolate(f, [fx(dim), fx(dim) + 10], [1, 0.32], clamp);
  return (
    <div style={{ ...style, opacity: lin * (1 - out) * dimK, translate: `0px ${(1 - s) * dy - out * 40}px`,
      scale: `${(scale + (1 - scale) * s) * (1 - out * 0.05)}`, filter: `blur(${(1 - lin) * blur + out * 10}px)`,
      transform: tilt ? `perspective(1400px) rotateX(${(1 - s) * tilt}deg)` : undefined, transformOrigin: "50% 100%" }}>
      {children}
    </div>
  );
};

export const Card: React.FC<{ w: number; h: number; label?: string; children?: React.ReactNode; glow?: string; glowAt?: number; style?: React.CSSProperties; fill?: string; accent?: string; shineAt?: number }> = ({
  w, h, label, children, glow, glowAt = 0, style, fill, accent, shineAt,
}) => {
  const f = useCurrentFrame();
  const g = glow ? interpolate(f, [fx(glowAt), fx(glowAt) + 10], [0, 1], clamp) : 0;
  return (
    <div style={{
      width: w, height: h, borderRadius: 28, position: "relative", overflow: "hidden",
      background: fill ?? "linear-gradient(180deg, #1A1C1F 0%, #121315 100%)",
      border: `2px solid ${glow && g > 0 ? glow : COL.edge}`,
      boxShadow: `inset 0 1px 0 rgba(255,255,255,0.07), 0 30px 70px rgba(0,0,0,0.65)${glow ? `, 0 0 ${60 * g}px ${glow}${Math.round(g * 0x66).toString(16).padStart(2, "0")}` : ""}`,
      ...style,
    }}>
      {accent && <div style={{ position: "absolute", left: 0, right: 0, top: 0, height: 4, background: accent, opacity: 0.85 }} />}
      {label && <div style={{ position: "absolute", left: 28, top: 24, font: `600 24px ${MONO}`, letterSpacing: 2, color: COL.mute, whiteSpace: "nowrap" }}>{label}</div>}
      {children}
      {shineAt !== undefined && <Shine at={shineAt} />}
    </div>
  );
};

export const Shine: React.FC<{ at: number }> = ({ at }) => {
  const f = useCurrentFrame();
  const p = interpolate(f, [fx(at), fx(at) + 22], [-0.6, 1.4], { ...clamp, easing: easeOut });
  if (p <= -0.6 || p >= 1.4) return null;
  return (
    <div style={{ position: "absolute", inset: 0, overflow: "hidden", pointerEvents: "none" }}>
      <div style={{ position: "absolute", top: -40, bottom: -40, width: "35%", left: `${p * 100}%`, rotate: "18deg", background: "linear-gradient(90deg, transparent, rgba(255,255,255,0.28), transparent)" }} />
    </div>
  );
};

export const Pill: React.FC<{ text: string; bg?: string; color?: string; size?: number; outline?: boolean }> = ({ text, bg = COL.gold, color = COL.ink, size = 26, outline }) => (
  <div style={{
    display: "inline-block", padding: `${size * 0.45}px ${size * 1.05}px`, borderRadius: 999, whiteSpace: "nowrap", font: `800 ${size}px ${MONO}`, letterSpacing: 1.5,
    background: outline ? "transparent" : bg, color: outline ? bg : color, border: outline ? `3px solid ${bg}` : "none",
    boxShadow: outline ? `0 0 30px ${bg}33` : `0 10px 40px ${bg}55, inset 0 1px 0 rgba(255,255,255,0.35)`,
  }}>{text}</div>
);

export const Mono: React.FC<{ s: number; c?: string; w?: number; children: React.ReactNode; style?: React.CSSProperties }> = ({ s, c = COL.mute, w = 600, children, style }) => (
  <div style={{ font: `${w} ${s}px ${MONO}`, color: c, letterSpacing: s * 0.08, whiteSpace: "nowrap", ...style }}>{children}</div>
);

/** big display text; if it contains a number it rolls like an odometer from `at` */
export const Big: React.FC<{ s: number; c?: string; children: string; at?: number; dur?: number; style?: React.CSSProperties; roll?: boolean }> = ({ s, c = COL.txt, children, at, dur = 0.9, style, roll = true }) => (
  <div style={{ font: `900 ${s}px ${SANS}`, color: c, letterSpacing: -s * 0.035, lineHeight: `${s * 1.05}px`, whiteSpace: "nowrap", textShadow: `0 0 ${s * 0.35}px ${c}40, 0 6px 30px rgba(0,0,0,.5)`, ...style }}>
    {roll && at !== undefined && (children.match(/\d[\d,]*/g) || []).length === 1 ? <RollText text={children} at={at} dur={dur} size={s} /> : children}
  </div>
);

/** slot-machine roll: every digit column spins up to its target, lower columns spin more; other characters stay put */
export const RollText: React.FC<{ text: string; at: number; dur: number; size: number }> = ({ text, at, dur, size }) => {
  const f = useCurrentFrame();
  const chars = [...text];
  const digitIdx = chars.map((ch, i) => (/\d/.test(ch) ? i : -1)).filter((i) => i >= 0);
  const nd = digitIdx.length;
  const H = size * 1.05;
  return (
    <span style={{ display: "inline-flex", fontVariantNumeric: "tabular-nums" }}>
      {chars.map((ch, i) => {
        const j = digitIdx.indexOf(i);
        if (j < 0) return <span key={i} style={{ whiteSpace: "pre" }}>{ch}</span>;
        const d = +ch;
        const spins = Math.min(3, nd - 1 - j);
        const p = interpolate(f, [fx(at), fx(at + dur * (0.6 + 0.4 * (nd - j) / nd))], [0, 1], { ...clamp, easing: Easing.bezier(0.2, 0.7, 0.2, 1) });
        const v = p * (d + 10 * spins);
        const cur = Math.floor(v) % 10, fr = v - Math.floor(v);
        return (
          <span key={i} style={{ display: "inline-block", height: H, overflow: "hidden" }}>
            <span style={{ display: "block", translate: `0px ${-fr * H}px` }}>
              <span style={{ display: "block", height: H }}>{cur}</span>
              <span style={{ display: "block", height: H }}>{(cur + 1) % 10}</span>
            </span>
          </span>
        );
      })}
    </span>
  );
};

/** Fluent 3D illustration (MIT), floats gently */
export const Ill: React.FC<{ name: string; size: number; at: number; style?: React.CSSProperties }> = ({ name, size, at, style }) => {
  const f = useCurrentFrame();
  const s = spring({ frame: f - fx(at), fps: FPS, config: { damping: 10, stiffness: 160 } });
  return (
    <Img src={staticFile(`ill/${name}.png`)} style={{ width: size, height: size, scale: `${0.4 + 0.6 * s}`, rotate: `${(1 - s) * -25 + Math.sin(f / 20) * 3}deg`,
      translate: `0 ${Math.sin(f / 14) * size * 0.025}px`, filter: `drop-shadow(0 ${size * 0.12}px ${size * 0.15}px rgba(0,0,0,.55))`, ...style }} />
  );
};

/** real photo / logo (freely licensed, see pipeline/render/photos.py): logos on a white plate, photos cropped with a slow zoom */
export const Photo: React.FC<{ src: string; logo?: boolean; w: number; h: number; at: number; credit?: string; radius?: number }> = ({ src, logo, w, h, at, credit, radius = 22 }) => {
  const f = useCurrentFrame();
  const s = spring({ frame: f - fx(at), fps: FPS, config: { damping: 13, stiffness: 150 } });
  const zoom = 1.04 + 0.06 * interpolate(f, [fx(at), fx(at) + 150], [0, 1], clamp);
  return (
    <div style={{ width: w, height: h, borderRadius: radius, overflow: "hidden", position: "relative", scale: `${0.85 + 0.15 * s}`,
      background: logo ? "linear-gradient(180deg,#FFFFFF,#ECEAE4)" : "#111", border: `2px solid ${logo ? "rgba(255,255,255,.6)" : COL.edge}`,
      boxShadow: "0 24px 60px rgba(0,0,0,.6), inset 0 1px 0 rgba(255,255,255,.15)" }}>
      <Img src={staticFile(src)} style={{ width: "100%", height: "100%", objectFit: logo ? "contain" : "cover", padding: logo ? Math.min(w, h) * 0.12 : 0,
        scale: logo ? "1" : `${zoom}` }} />
      {credit && Math.min(w, h) >= 160 && <div style={{ position: "absolute", right: 8, bottom: 6, font: `500 13px ${MONO}`, color: logo ? "#666" : "rgba(255,255,255,.75)",
        textShadow: logo ? "none" : "0 1px 3px #000", maxWidth: w - 16, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{credit}</div>}
    </div>
  );
};

/** the visual slot on cards/headlines/steps: real photo or logo when the pipeline found one, else the 3D illustration */
export const Vis: React.FC<{ o: any; size: number; at: number }> = ({ o, size, at }) =>
  o.photo ? <Photo src={o.photo} logo={(o.photo_kind || "") === "logo"} w={size} h={size} at={at} radius={Math.max(12, size * 0.18)} />
    : o.ill ? <Ill name={o.ill} size={size} at={at} /> : null;

/** particle burst on impact (big reveals): sparks fly out from the centre and fade */
export const Burst: React.FC<{ at: number; color?: string; n?: number; spread?: number }> = ({ at, color = COL.gold, n = 26, spread = 420 }) => {
  const f = useCurrentFrame();
  const t = (f - fx(at)) / FPS;
  if (t < 0 || t > 0.9) return null;
  const k = Easing.out(Easing.cubic)(Math.min(1, t / 0.6));
  return (
    <div style={{ position: "absolute", left: "50%", top: "50%", width: 0, height: 0, pointerEvents: "none" }}>
      <div style={{ position: "absolute", left: -spread * 0.45, top: -spread * 0.45, width: spread * 0.9, height: spread * 0.9, borderRadius: "50%",
        border: `3px solid ${color}`, opacity: (1 - t / 0.5) * 0.7, scale: `${0.2 + k * 1.1}`, filter: "blur(1px)" }} />
      {Array.from({ length: n }).map((_, i) => {
        const a = (i / n) * Math.PI * 2 + (random(`ba${i}`) - 0.5) * 0.4;
        const d = spread * (0.35 + random(`bd${i}`) * 0.65) * k;
        const sz = 4 + random(`bs${i}`) * 8;
        return <div key={i} style={{ position: "absolute", left: Math.cos(a) * d, top: Math.sin(a) * d + 60 * t * t, width: sz, height: sz * (1.6 + random(`bl${i}`) * 2),
          rotate: `${(a * 180) / Math.PI + 90}deg`, borderRadius: sz, background: color, opacity: Math.max(0, 1 - t / 0.85), boxShadow: `0 0 12px ${color}` }} />;
      })}
    </div>
  );
};
