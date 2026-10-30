import React from "react";
import { AbsoluteFill, Img, interpolate, spring, staticFile, useCurrentFrame, random, Easing } from "remotion";
import { COL, SANS, MONO, FPS, clamp, easeOut, fx, SceneCtx, Reveal, Big, Mono, Pill } from "./lib";
import { SPECS, El, W, MoneyRain } from "./Elements";

export type Word = { t: string; k: boolean; s: number; e: number };
export type SceneT = { start: number; end: number; tint?: string; elements: El[] };
export type ReelProps = {
  duration: number; badge: string; tag: string; handle: string; disclaimer?: string;
  words: Word[]; chunks: number[][]; scenes: SceneT[];
  reacts: { at: number; until: number; pose: string }[];
  cta: { start: number; line1: string; line1_at: number; line2?: string; line2_at?: number };
  endcard: { at: number; title: string; terminal: string };
};

const TINTS: Record<string, string> = { warm: "245,194,66", cold: "70,150,255", red: "238,84,84", green: "84,214,140" };

/* ---------------------------------------------------------------- background */
const Background: React.FC<{ scenes: SceneT[] }> = ({ scenes }) => {
  const f = useCurrentFrame();
  const pulse = 0.85 + 0.15 * Math.sin(f / 40);
  return (
    <AbsoluteFill style={{ background: COL.bg }}>
      {Object.entries(TINTS).map(([name, rgb]) => {
        // weight of this tint = how much the current scene(s) use it, cross-faded over 12 frames
        let w = 0;
        for (const s of scenes) {
          if ((s.tint || "warm") !== name) continue;
          w = Math.max(w, interpolate(f, [fx(s.start) - 6, fx(s.start) + 6, fx(s.end) - 6, fx(s.end) + 6], [0, 1, 1, 0], clamp));
        }
        if (name === "warm" && f < fx(scenes[0]?.start ?? 0) + 6) w = 1;
        if (name === "warm" && scenes.length && f > fx(scenes[scenes.length - 1].end)) w = 1;
        return <AbsoluteFill key={name} style={{ opacity: w * pulse, background: `radial-gradient(ellipse 70% 45% at 50% 38%, rgba(${rgb},${name === "warm" ? 0.16 : 0.2}), transparent 70%)` }} />;
      })}
      <svg width={1080} height={1920} style={{ position: "absolute", opacity: 0.5 }}>
        <defs>
          <pattern id="grid" width="60" height="60" patternUnits="userSpaceOnUse"><path d="M60 0 L0 0 0 60" fill="none" stroke="rgba(255,255,255,0.025)" strokeWidth="1" /></pattern>
          <radialGradient id="gm" cx="50%" cy="38%" r="60%"><stop offset="0" stopColor="#fff" /><stop offset="1" stopColor="#000" /></radialGradient>
          <mask id="m"><rect width="1080" height="1920" fill="url(#gm)" /></mask>
        </defs>
        <rect width="1080" height="1920" fill="url(#grid)" mask="url(#m)" />
      </svg>
      {Array.from({ length: 40 }).map((_, i) => {
        const x = (random(`x${i}`) * 1080 + f * (0.2 + random(`v${i}`) * 0.5)) % 1080;
        const y = (random(`y${i}`) * 1920 - f * (0.3 + random(`w${i}`) * 0.6) + 3840) % 1920;
        const r = 1 + random(`r${i}`) * 2.5;
        return <div key={i} style={{ position: "absolute", left: x, top: y, width: r, height: r, borderRadius: "50%", background: "#fff", opacity: 0.08 + random(`o${i}`) * 0.18 }} />;
      })}
      <AbsoluteFill style={{ background: "radial-gradient(ellipse 90% 70% at 50% 45%, transparent 55%, rgba(0,0,0,0.75) 100%)" }} />
    </AbsoluteFill>
  );
};

/* ---------------------------------------------------------------- one scene: auto-stacked elements, camera push-in */
const TOP = 190, AREA = 900, GAP = 36;
const Scene: React.FC<{ s: SceneT; i: number }> = ({ s, i }) => {
  const f = useCurrentFrame();
  if (f < fx(s.start) - 2 || f > fx(s.end) + 12) return null;
  const els = s.elements.filter((e) => SPECS[e.type]);
  const hs = els.map((e) => SPECS[e.type].h(e));
  const stacked = els.filter((_, k) => hs[k] > 0);
  const total = hs.filter((h) => h > 0).reduce((a, b) => a + b, 0) + GAP * Math.max(0, stacked.length - 1);
  const k = total > AREA ? AREA / total : 1;
  const top = TOP + (total < AREA ? (AREA - total) * 0.42 : 0);
  const p = interpolate(f, [fx(s.start), fx(s.end)], [0, 1], clamp);
  let y = 0;
  return (
    <SceneCtx.Provider value={{ end: s.end }}>
      <AbsoluteFill style={{ scale: `${1 + 0.035 * p}`, translate: `${(i % 2 ? -1 : 1) * (p - 0.5) * 14}px ${-p * 10}px`, transformOrigin: "540px 650px" }}>
        <div style={{ position: "absolute", left: 70, top, width: W, scale: `${k}`, transformOrigin: "50% 0" }}>
          {els.map((e, j) => {
            const h = hs[j];
            if (h === 0) return e.type === "money_rain" ? <div key={j} style={{ position: "absolute", left: -70, top: -top }}><MoneyRain at={e.at} /></div> : null;
            const R = SPECS[e.type].R;
            const node = (
              <Reveal key={j} at={e.at} style={{ position: "absolute", left: 0, top: y, width: W }} dy={e.type === "stat_row" || e.type === "vs" || e.type === "arrow_pair" ? 0 : 46} blur={e.type === "stat_row" || e.type === "vs" ? 0 : 14} scale={e.type === "stat_row" || e.type === "vs" ? 1 : 0.92}>
                <R e={e} />
              </Reveal>
            );
            y += h + GAP;
            return node;
          })}
        </div>
      </AbsoluteFill>
    </SceneCtx.Provider>
  );
};

/* ---------------------------------------------------------------- captions */
const Captions: React.FC<{ words: Word[]; chunks: number[][] }> = ({ words, chunks }) => {
  const f = useCurrentFrame();
  const t = f / FPS;
  let ch: number[] | null = null;
  for (const c of chunks) if (words[c[0]].s - 0.12 <= t && t < words[c[c.length - 1]].e + 0.3) ch = c;
  if (!ch) return null;
  const c0 = words[ch[0]].s - 0.12;
  const enter = interpolate(t, [c0, c0 + 0.18], [0, 1], { ...clamp, easing: easeOut });
  return (
    <div style={{ position: "absolute", left: 50, right: 50, top: 1150, display: "flex", flexWrap: "wrap", justifyContent: "center", gap: "0 18px",
      opacity: enter, translate: `0 ${(1 - enter) * 18}px`, filter: `blur(${(1 - enter) * 8}px)` }}>
      {ch.map((i) => {
        const w = words[i];
        const spoken = t >= w.s, live = spoken && t < w.e + 0.05;
        const p = spring({ frame: f - fx(w.s), fps: FPS, config: { damping: 11, stiffness: 260 } });
        return (
          <span key={i} style={{ font: `800 66px ${SANS}`, letterSpacing: -1, color: spoken ? (w.k ? COL.gold : COL.txt) : "#3E3E3E", display: "inline-block",
            scale: `${spoken ? 1 + 0.1 * (1 - p) + (live ? 0.03 : 0) : 1}`, translate: `0 ${spoken ? -6 * (1 - p) : 0}px`,
            textShadow: spoken && w.k ? `0 0 26px ${COL.gold}88` : "0 4px 18px rgba(0,0,0,.7)" }}>{w.t}</span>
        );
      })}
    </div>
  );
};

/* ---------------------------------------------------------------- Rohan */
const VOW: Record<string, string> = { a: "A", e: "E", i: "E", o: "O", u: "O", m: "MBP", b: "MBP", p: "MBP" };
const mouthAt = (words: Word[], t: number) => {
  for (const w of words) if (w.s <= t && t < w.e) {
    const seq = [...w.t.toLowerCase()].filter((c) => VOW[c]).map((c) => VOW[c]);
    const s = seq.length ? seq : ["A"];
    return s[Math.min(Math.floor(((t - w.s) / Math.max(w.e - w.s, 1e-3)) * s.length), s.length - 1)];
  }
  return null;
};
const REST: Record<string, string> = { neutral: "smile", smirk: "smirk", shocked: "O", serious: "closed" };
const Mascot: React.FC<{ reacts: ReelProps["reacts"]; words: Word[] }> = ({ reacts, words }) => {
  const f = useCurrentFrame();
  const t = f / FPS;
  return (
    <>
      {reacts.map((r, i) => {
        if (t < r.at - 0.05 || t > r.until + 0.5) return null;
        const inn = spring({ frame: f - fx(r.at), fps: FPS, config: { damping: 12, stiffness: 140 } });
        const out = interpolate(t, [r.until, r.until + 0.35], [0, 1], { ...clamp, easing: Easing.in(Easing.cubic) });
        const mood = r.pose.split("_")[0];
        const mouth = mouthAt(words, t) ?? REST[mood] ?? "smile";
        return (
          <div key={i} style={{ position: "absolute", left: 700, top: 1360 + (1 - inn) * 520 + out * 520 + Math.sin(f / 9) * 6,
            rotate: `${(1 - inn) * 12 + Math.sin(f / 23) * 1.5}deg`, transformOrigin: "50% 100%", filter: "drop-shadow(0 30px 40px rgba(0,0,0,.6))" }}>
            <Img src={staticFile(`rohan/${r.pose}_${mouth}.png`)} style={{ width: 360 }} />
          </div>
        );
      })}
    </>
  );
};

/* ---------------------------------------------------------------- chrome */
const Chrome: React.FC<{ p: ReelProps }> = ({ p }) => {
  const f = useCurrentFrame();
  const inn = spring({ frame: f, fps: FPS, config: { damping: 14 } });
  return (
    <>
      <div style={{ position: "absolute", left: 40, top: 60, height: 58, display: "flex", alignItems: "center", gap: 14, padding: "0 22px 0 12px", borderRadius: 16,
        background: "linear-gradient(180deg,#1B1D20,#131416)", border: `2px solid ${COL.edge}`, boxShadow: "0 12px 30px rgba(0,0,0,.5)", translate: `${(1 - inn) * -60}px 0`, opacity: inn }}>
        <div style={{ width: 34, height: 34, borderRadius: 9, background: COL.gold, display: "flex", alignItems: "center", justifyContent: "center", font: `900 24px ${SANS}`, color: COL.ink, boxShadow: `0 0 18px ${COL.gold}88` }}>₹</div>
        <div style={{ font: `800 26px ${MONO}`, color: COL.txt, letterSpacing: 2 }}>{p.badge}</div>
      </div>
      <div style={{ position: "absolute", right: 40, top: 66, padding: "8px 22px", borderRadius: 999, border: `2px solid ${COL.gold}`, font: `800 22px ${MONO}`, color: COL.gold, letterSpacing: 2,
        translate: `${(1 - inn) * 60}px 0`, opacity: inn, display: "flex", alignItems: "center", gap: 10, maxWidth: 520, whiteSpace: "nowrap", overflow: "hidden" }}>
        <span style={{ width: 12, height: 12, borderRadius: 6, background: COL.gold, opacity: 0.5 + 0.5 * Math.sin(f / 6), boxShadow: `0 0 10px ${COL.gold}`, flex: "none" }} />{p.tag}
      </div>
      <div style={{ position: "absolute", left: 0, right: 0, top: 1345, display: "flex", justifyContent: "center", alignItems: "center", gap: 12 }}>
        <div style={{ width: 14, height: 14, background: COL.green }} /><div style={{ font: `500 26px ${MONO}`, color: COL.mute }}>{p.handle}</div>
      </div>
      {p.disclaimer && f < 5.5 * FPS && <div style={{ position: "absolute", left: 0, right: 0, top: 1100, textAlign: "center", font: `500 18px ${MONO}`, color: "#555", letterSpacing: 2 }}>{p.disclaimer}</div>}
    </>
  );
};

/* ---------------------------------------------------------------- CTA + end card */
const Plane: React.FC<{ at: number }> = ({ at }) => {
  const f = useCurrentFrame();
  const t = interpolate(f, [fx(at), fx(at + 1.1)], [0, 1], { ...clamp, easing: Easing.bezier(0.3, 0.6, 0.2, 1) });
  if (f < fx(at)) return null;
  const path = (u: number) => [80 + u * 520, 420 - Math.sin(u * Math.PI) * 220 - u * 80];
  const [x, y] = path(t);
  return (
    <>
      <svg width={1080} height={700} style={{ position: "absolute", left: 0, top: 0, overflow: "visible" }}>
        <polyline points={Array.from({ length: 12 }).map((_, i) => path(Math.max(0, t - i * 0.025)).join(",")).join(" ")} fill="none" stroke={COL.gold} strokeWidth={4} strokeDasharray="6 10" opacity={0.6} />
      </svg>
      <svg width={180} height={140} viewBox="0 0 180 140" style={{ position: "absolute", left: x, top: y - 70, rotate: `${-18 + t * 18}deg`, filter: `drop-shadow(0 10px 30px ${COL.gold}66)` }}>
        <polygon points="0,70 180,0 120,140 90,90" fill={COL.gold} /><polygon points="90,90 180,0 100,120" fill="#C89A2A" />
      </svg>
    </>
  );
};

const Center: React.FC<{ y: number; at: number; children: React.ReactNode }> = ({ y, at, children }) => (
  <Reveal at={at} style={{ position: "absolute", left: 0, width: 1080, top: y, display: "flex", justifyContent: "center" }}>{children}</Reveal>
);

const fitS = (t: string, w: number, max: number) => Math.min(max, w / Math.max(1, t.length * 0.55));

const Cta: React.FC<{ c: ReelProps["cta"]; end: number }> = ({ c, end }) => {
  const f = useCurrentFrame();
  if (f < fx(c.start) - 2 || f > fx(end) + 12) return null;
  return (
    <SceneCtx.Provider value={{ end }}>
      <AbsoluteFill>
        <Plane at={c.start} />
        <Center y={480} at={c.line1_at}><Big s={fitS(c.line1, 960, 86)} roll={false}>{c.line1}</Big></Center>
        {c.line2 && <Center y={600} at={c.line2_at ?? c.line1_at + 0.6}><div style={{ font: `700 ${fitS(c.line2, 960, 50)}px ${SANS}`, color: COL.gold, whiteSpace: "nowrap" }}>{c.line2}</div></Center>}
      </AbsoluteFill>
    </SceneCtx.Provider>
  );
};

const EndCard: React.FC<{ e: ReelProps["endcard"]; handle: string }> = ({ e, handle }) => {
  const f = useCurrentFrame();
  if (f < fx(e.at)) return null;
  const n = Math.floor(interpolate(f, [fx(e.at + 0.4), fx(e.at + 1.4)], [0, e.terminal.length], clamp));
  return (
    <>
      <Center y={600} at={e.at}><Big s={fitS(e.title, 960, 120)} roll={false}>{e.title}</Big></Center>
      <Center y={760} at={e.at + 0.3}>
        <div style={{ padding: "18px 28px", borderRadius: 16, background: "#121315", border: `2px solid ${COL.edge}`, boxShadow: "0 20px 50px rgba(0,0,0,.6)", minWidth: 640 }}>
          <Mono s={26} c={COL.green}>{e.terminal.slice(0, n)}<span style={{ opacity: f % 16 < 8 ? 1 : 0 }}>_</span></Mono>
        </div>
      </Center>
      <Center y={880} at={e.at + 1.0}><Pill text={`FOLLOW ${handle}`} size={26} /></Center>
    </>
  );
};

export const Reel: React.FC<ReelProps> = (p) => {
  const f = useCurrentFrame();
  const fade = interpolate(f, [fx(p.duration + 2.4), fx(p.duration + 2.9)], [0, 1], clamp);
  return (
    <AbsoluteFill style={{ background: COL.bg, overflow: "hidden" }}>
      <Background scenes={p.scenes} />
      {p.scenes.map((s, i) => <Scene key={i} s={s} i={i} />)}
      <Cta c={p.cta} end={p.endcard.at} />
      <EndCard e={p.endcard} handle={p.handle} />
      <Mascot reacts={p.reacts} words={p.words} />
      <Captions words={p.words} chunks={p.chunks} />
      <Chrome p={p} />
      <AbsoluteFill style={{ background: COL.bg, opacity: fade }} />
    </AbsoluteFill>
  );
};
