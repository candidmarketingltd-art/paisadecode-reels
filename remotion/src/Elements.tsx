import React from "react";
import { interpolate, spring, useCurrentFrame, random, Easing } from "remotion";
import { COL, MONO, SANS, FPS, clamp, easeOut, fx, col, fit, Card, Pill, Mono, Big, Ill, Reveal } from "./lib";
import { Object3D } from "./Object3D";

/* All times are seconds (already resolved from cue words by the pipeline). Width of the content column is 940. */
export const W = 940;
export type El = { type: string; at: number; [k: string]: any };

/* -------------------------------------------------------------- small pieces */
const DotGrid: React.FC<{ at: number; n: number; cols: number; size: number; gap: number; lostFrom?: number; lostAt?: number }> = ({ at, n, cols, size, gap, lostFrom = 1e9, lostAt = 1e9 }) => {
  const f = useCurrentFrame();
  const shown = Math.round(interpolate(f, [fx(at), fx(at + 1.2)], [0, n], { ...clamp, easing: Easing.out(Easing.quad) }));
  return (
    <div style={{ position: "relative", width: cols * (size + gap), height: Math.ceil(n / cols) * (size + gap) }}>
      {Array.from({ length: shown }).map((_, i) => {
        const r = Math.floor(i / cols), q = i % cols;
        const li = i - lostFrom, lt = lostAt + Math.max(0, li) * 0.018;
        const lost = li >= 0 && f >= fx(lt);
        const k = lost ? interpolate(f, [fx(lt), fx(lt) + 14], [0, 1], { ...clamp, easing: Easing.in(Easing.quad) }) : 0;
        const fall = lost ? k * (30 + random(`d${i}`) * 50) : 0;
        return <div key={i} style={{ position: "absolute", left: q * (size + gap), top: r * (size + gap) + fall, width: size, height: size, borderRadius: size * 0.28,
          background: lost ? "transparent" : `linear-gradient(160deg, ${COL.blue}, #2f7fd0)`, border: lost ? `2px solid ${COL.red}` : "none",
          opacity: lost ? 1 - k * 0.6 : 1, boxShadow: lost ? `0 0 10px ${COL.red}88` : `0 0 8px ${COL.blue}55`, rotate: `${fall}deg` }} />;
      })}
    </div>
  );
};

const StatCard: React.FC<{ c: any; w: number; h: number }> = ({ c, w, h }) => {
  const color = col(c.color, COL.gold);
  const vs = fit(c.value || "", w - 56, h * 0.42, 0.6);
  return (
    <Card w={w} h={h} label={c.label} accent={color} glow={c.glow ? color : undefined} glowAt={c.at} shineAt={c.at + 0.15}>
      {c.ill && <div style={{ position: "absolute", right: 14, top: 10 }}><Ill name={c.ill} size={Math.min(110, h * 0.36)} at={c.at + 0.1} /></div>}
      <div style={{ position: "absolute", left: 26, top: h * 0.27 }}><Big s={vs} c={color} at={c.at}>{c.value || ""}</Big></div>
      {c.sub && <Mono s={22} style={{ position: "absolute", left: 28, bottom: 22 }}>{c.sub}</Mono>}
    </Card>
  );
};

/* -------------------------------------------------------------- elements: { height, render } */
type Spec = { h: (e: El) => number; R: React.FC<{ e: El }> };

const centerRow = (children: React.ReactNode) => <div style={{ width: W, display: "flex", justifyContent: "center" }}>{children}</div>;

export const SPECS: Record<string, Spec> = {
  pill: { h: () => 70, R: ({ e }) => centerRow(<Pill text={e.text} bg={col(e.color, COL.gold)} outline={e.outline} size={fit(e.text, 860, 30, 0.72)} />) },

  label: { h: () => 50, R: ({ e }) => centerRow(<Mono s={fit(e.text, 900, 32, 0.66)} c={col(e.color, COL.mute)} w={800}>{e.text}</Mono>) },

  headline: {
    h: (e) => (e.sub ? 70 : 0) + (e.size === "l" ? 150 : 100),
    R: ({ e }) => {
      const s = fit(e.text, e.ill ? 760 : 920, e.size === "l" ? 130 : 84, 0.55);
      return (
        <div style={{ width: W, display: "flex", flexDirection: "column", alignItems: "center", gap: 10 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
            {e.ill && <Ill name={e.ill} size={s * 1.3} at={e.at} />}
            <Big s={s} c={col(e.color)} at={e.at}>{e.text}</Big>
          </div>
          {e.sub && <Reveal at={e.sub_at ?? e.at + 0.3} style={{}}><div style={{ font: `700 ${fit(e.sub, 900, 48)}px ${SANS}`, color: col(e.sub_color, COL.gold), whiteSpace: "nowrap" }}>{e.sub}</div></Reveal>}
        </div>
      );
    },
  },

  stat_row: {
    h: (e) => (e.cards.length === 1 ? 240 : 300),
    R: ({ e }) => {
      const n = e.cards.length, w = (W - 20 * (n - 1)) / n, h = n === 1 ? 240 : 300;
      return (
        <div style={{ position: "relative", width: W, height: h }}>
          {e.cards.map((c: any, i: number) => (
            <Reveal key={i} at={c.at} style={{ position: "absolute", left: i * (w + 20), top: 0 }}><StatCard c={c} w={w} h={h} /></Reveal>
          ))}
        </div>
      );
    },
  },

  big_number: {
    h: (e) => 330 + (e.note ? 80 : 0),
    R: ({ e }) => (
      <div style={{ width: W, display: "flex", flexDirection: "column", alignItems: "center" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 24 }}>
          {e.ill && <Ill name={e.ill} size={200} at={e.at + 0.15} />}
          <Big s={fit(e.value, e.ill ? 680 : 900, 320, 0.6)} c={col(e.color, COL.gold)} at={e.at}>{e.value}</Big>
        </div>
        {e.note && <Reveal at={e.note_at ?? e.at + 0.5} style={{ marginTop: 18 }}><Pill text={e.note} bg={col(e.note_color, COL.red)} outline size={fit(e.note, 860, 30, 0.72)} /></Reveal>}
      </div>
    ),
  },

  split_bar: {
    h: () => 170,
    R: ({ e }) => {
      const f = useCurrentFrame();
      const tot = e.parts.reduce((a: number, p: any) => a + Math.max(0.0001, +p.value || 1), 0);
      let x = 0;
      return (
        <div style={{ position: "relative", width: W, height: 170 }}>
          <div style={{ position: "absolute", left: 0, right: 0, top: 0, height: 100, borderRadius: 20, background: "#1C1E21", boxShadow: "inset 0 2px 10px rgba(0,0,0,.6)" }} />
          {e.parts.map((p: any, i: number) => {
            const w = (W - 10 * (e.parts.length - 1)) * (Math.max(0.0001, +p.value || 1) / tot);
            const left = x; x += w + 10;
            const k = interpolate(f, [fx(p.at), fx(p.at + 0.5)], [0, 1], { ...clamp, easing: easeOut });
            const c = col(p.color, [COL.blue, "#4A4D55", COL.gold, COL.green][i % 4]);
            const dark = c !== "#4A4D55";
            return (
              <React.Fragment key={i}>
                <div style={{ position: "absolute", left, top: 0, height: 100, width: w * k, borderRadius: 20, overflow: "hidden", background: `linear-gradient(180deg, ${c}, ${c}cc)`,
                  boxShadow: dark ? `0 0 30px ${c}77` : "none", display: "flex", alignItems: "center", justifyContent: i === e.parts.length - 1 && w > 200 ? "flex-end" : "flex-start", padding: "0 20px" }}>
                  {w > 110 && k > 0.6 && p.text && <Big s={Math.min(62, w * 0.3)} c={dark ? COL.ink : COL.txt} at={p.at + 0.2} dur={0.5} style={{ textShadow: "none" }}>{p.text}</Big>}
                </div>
                <Mono s={Math.min(26, Math.max(18, w / 9))} c={c === "#4A4D55" ? COL.mute : c} w={700} style={{ position: "absolute", left: i === e.parts.length - 1 && w > 200 ? undefined : left, right: i === e.parts.length - 1 && w > 200 ? 0 : undefined, top: 118, opacity: k }}>{p.label}</Mono>
              </React.Fragment>
            );
          })}
        </div>
      );
    },
  },

  dot_grid: {
    h: () => 350,
    R: ({ e }) => {
      const total = Math.max(1, +e.total), lost = Math.max(0, +(e.lost || 0));
      const n = Math.min(300, total), nl = Math.round((lost / total) * n);
      return (
        <Card w={W} h={350} shineAt={e.at + 0.1}>
          <div style={{ position: "absolute", left: 28, top: 22 }}><DotGrid at={e.at} n={n} cols={30} size={21} gap={9} lostFrom={n - nl} lostAt={e.lost_at ?? 1e9} /></div>
          <div style={{ position: "absolute", left: 28, bottom: 14, display: "flex", gap: 14, alignItems: "baseline", background: "#121315", paddingRight: 12 }}>
            <Mono s={26}>{e.label ? `${e.label} · ` : ""}{e.total_text ?? total} →</Mono>
            {e.lost_at !== undefined && <Big s={32} c={COL.red} at={e.lost_at}>{e.left_text ?? String(total - lost)}</Big>}
          </div>
        </Card>
      );
    },
  },

  vs: {
    h: () => 380,
    R: ({ e }) => {
      const f = useCurrentFrame();
      const L = e.left, Rr = e.right;
      const sa = e.strike_at ?? Rr.at + 0.3;
      const strike = interpolate(f, [fx(sa), fx(sa + 0.3)], [0, 1], { ...clamp, easing: easeOut });
      const lose = f >= fx(Rr.at);
      const vsL = fit(L.value, 400, 150, 0.6), vsR = fit(Rr.value, 400, 150, 0.6);
      return (
        <div style={{ position: "relative", width: W, height: 380 }}>
          <Reveal at={e.at} style={{ position: "absolute", left: 0 }}>
            <Card w={450} h={380} label={L.label} accent={lose ? COL.dim : COL.txt} shineAt={e.at + 0.15}>
              <div style={{ position: "absolute", left: 26, top: 110, opacity: lose ? 0.45 : 1 }}>
                <Big s={vsL} at={e.at}>{L.value}</Big>
                <div style={{ position: "absolute", left: -10, top: vsL * 0.5, height: 12, width: (vsL * 0.6 * L.value.length + 20) * strike, background: COL.red, borderRadius: 6, boxShadow: `0 0 20px ${COL.red}` }} />
              </div>
              {L.sub && <Mono s={22} style={{ position: "absolute", left: 28, bottom: 22 }}>{L.sub}</Mono>}
            </Card>
          </Reveal>
          <Reveal at={Rr.at} style={{ position: "absolute", left: 490 }}>
            <Card w={450} h={380} label={Rr.label} accent={col(Rr.color, COL.red)} glow={col(Rr.color, COL.red)} glowAt={Rr.at} shineAt={Rr.at + 0.15}>
              {Rr.ill && <div style={{ position: "absolute", right: 14, top: 12 }}><Ill name={Rr.ill} size={100} at={Rr.at} /></div>}
              <div style={{ position: "absolute", left: 26, top: 110 }}><Big s={vsR} c={col(Rr.color, COL.red)} at={Rr.at}>{Rr.value}</Big></div>
              {Rr.sub && <Mono s={22} style={{ position: "absolute", left: 28, bottom: 22 }}>{Rr.sub}</Mono>}
            </Card>
          </Reveal>
        </div>
      );
    },
  },

  arrow_pair: {
    h: () => 270,
    R: ({ e }) => {
      const L = e.left, Rr = e.right;
      const f = useCurrentFrame();
      const p = interpolate(f, [fx(Rr.at - 0.45), fx(Rr.at - 0.05)], [0, 1], { ...clamp, easing: easeOut });
      return (
        <div style={{ position: "relative", width: W, height: 270 }}>
          <Reveal at={e.at} style={{ position: "absolute", left: 0 }}><StatCard c={{ ...L, at: e.at, color: L.color ?? "blue" }} w={400} h={270} /></Reveal>
          <svg width={150} height={80} style={{ position: "absolute", left: 415, top: 95, overflow: "visible" }}>
            <path d="M 0 40 L 110 40 M 84 14 L 116 40 L 84 66" stroke={COL.gold} strokeWidth={12} fill="none" strokeLinecap="round" strokeLinejoin="round"
              strokeDasharray={220} strokeDashoffset={220 * (1 - p)} style={{ filter: `drop-shadow(0 0 10px ${COL.gold}88)` }} />
          </svg>
          <Reveal at={Rr.at} style={{ position: "absolute", left: 570 }}><StatCard c={{ ...Rr, glow: true, color: Rr.color ?? "gold" }} w={370} h={270} /></Reveal>
        </div>
      );
    },
  },

  strike_list: {
    h: (e) => e.items.length * 118,
    R: ({ e }) => {
      const f = useCurrentFrame();
      return (
        <div style={{ position: "relative", width: W, height: e.items.length * 118 }}>
          {e.items.map((it: any, i: number) => {
            const st = it.strike !== false;
            const p = st ? interpolate(f, [fx(it.at + 0.2), fx(it.at + 0.45)], [0, 1], { ...clamp, easing: easeOut }) : 0;
            const s = fit(it.text, 700, 84, 0.58);
            return (
              <Reveal key={i} at={it.at} dy={0} scale={0.8} style={{ position: "absolute", left: 90, top: i * 118, display: "flex", alignItems: "center", gap: 36 }}>
                <Big s={76} c={st ? COL.red : COL.green} roll={false}>{st ? "✕" : "✓"}</Big>
                <div style={{ position: "relative" }}>
                  <Big s={s} c={p > 0.5 ? COL.dim : COL.txt} roll={false}>{it.text}</Big>
                  <div style={{ position: "absolute", left: -8, top: s * 0.55, height: 10, width: `${p * 108}%`, background: COL.gold, borderRadius: 5, boxShadow: `0 0 18px ${COL.gold}` }} />
                </div>
              </Reveal>
            );
          })}
        </div>
      );
    },
  },

  steps: {
    h: (e) => e.items.length * 145,
    R: ({ e }) => (
      <div style={{ position: "relative", width: W, height: e.items.length * 145 }}>
        {e.items.map((it: any, i: number) => (
          <Reveal key={i} at={it.at} dim={e.items[i + 1]?.at ?? e.dim_at} style={{ position: "absolute", left: 0, top: i * 145 }}>
            <Card w={W} h={125} glow={COL.gold} glowAt={it.at} shineAt={it.at + 0.1}>
              <div style={{ position: "absolute", left: 32, top: 0, bottom: 0, display: "flex", alignItems: "center", gap: 30 }}>
                <Mono s={38} c={COL.gold} w={800}>{String(i + 1).padStart(2, "0")}</Mono>
                <div style={{ font: `800 ${fit(it.text, it.ill ? 640 : 760, 52, 0.55)}px ${SANS}`, color: COL.txt, letterSpacing: -1, whiteSpace: "nowrap" }}>{it.text}</div>
              </div>
              {it.ill && <div style={{ position: "absolute", right: 22, top: 12 }}><Ill name={it.ill} size={100} at={it.at + 0.1} /></div>}
            </Card>
          </Reveal>
        ))}
      </div>
    ),
  },

  ledger: {
    h: (e) => 130 + e.rows.length * 74,
    R: ({ e }) => {
      const f = useCurrentFrame();
      const h = 130 + e.rows.length * 74;
      return (
        <div style={{ rotate: "-1.2deg" }}>
          <Card w={W} h={h} fill="linear-gradient(180deg,#F4ECD6,#E8DDBF)" shineAt={e.at + 0.1}>
            <div style={{ position: "absolute", left: 30, top: 26, font: `800 30px ${MONO}`, color: "#8C3228", letterSpacing: 3 }}>{e.title}</div>
            <div style={{ position: "absolute", left: 120, top: 0, bottom: 0, width: 3, background: "#E9A0A0" }} />
            {e.rows.map((_: any, i: number) => <div key={i} style={{ position: "absolute", left: 0, right: 0, top: 104 + i * 74, height: 2, background: "#BCC6DA" }} />)}
            {e.rows.map((r: any, i: number) => {
              if (f < fx(r.at)) return null;
              const w = interpolate(f, [fx(r.at), fx(r.at + 0.3)], [0, 100], clamp);
              const st = spring({ frame: f - fx(r.at + 0.15), fps: FPS, config: { damping: 9, stiffness: 220 } });
              return (
                <React.Fragment key={i}>
                  <div style={{ position: "absolute", left: 44, top: 112 + i * 74, font: `italic 700 ${fit(r.text, 640, 50)}px ${SANS}`, color: "#2A2A44", whiteSpace: "nowrap", clipPath: `inset(0 ${100 - w}% 0 0)` }}>{r.text}</div>
                  {r.mark && <div style={{ position: "absolute", right: 46, top: 108 + i * 74, font: `900 42px ${MONO}`, color: COL.red, scale: `${2 - st}`, opacity: st, rotate: "-8deg", border: `4px solid ${COL.red}`, padding: "0 14px", borderRadius: 10 }}>{r.mark}</div>}
                </React.Fragment>
              );
            })}
          </Card>
        </div>
      );
    },
  },

  calculator: {
    h: () => 520,
    R: ({ e }) => {
      const f = useCurrentFrame();
      const va = e.value_at ?? e.at + 0.8;
      return centerRow(
        <Card w={620} h={520} fill="linear-gradient(180deg,#24262B,#17181B)" shineAt={e.at + 0.1}>
          <div style={{ position: "absolute", left: 34, top: 34, width: 552, height: 160, borderRadius: 18, background: "linear-gradient(180deg,#1A2E1F,#13221A)",
            boxShadow: "inset 0 3px 14px rgba(0,0,0,.7)", display: "flex", justifyContent: "flex-end", alignItems: "center", paddingRight: 28 }}>
            <Big s={fit(e.value, 500, 120, 0.62)} c={COL.green} at={va - 0.8} dur={1.1}>{e.value}</Big>
          </div>
          {Array.from({ length: 8 }).map((_, i) => {
            const r = Math.floor(i / 4), q = i % 4, press = e.at + i * 0.13;
            const k = interpolate(f, [fx(press), fx(press) + 3, fx(press) + 8], [0, 1, 0], clamp);
            const eq = i === 7;
            return <div key={i} style={{ position: "absolute", left: 44 + q * 138, top: 228 + r * 128, width: 116, height: 104, borderRadius: 20,
              background: eq ? `linear-gradient(180deg,#FFD976,${COL.gold})` : "linear-gradient(180deg,#3C3F46,#2C2E33)",
              boxShadow: `inset 0 1px 0 rgba(255,255,255,.15), 0 ${8 - k * 6}px ${16 - k * 8}px rgba(0,0,0,.5)`, translate: `0 ${k * 5}px`,
              display: "flex", alignItems: "center", justifyContent: "center", font: `800 40px ${SANS}`, color: eq ? COL.ink : "#9A9AA0" }}>{["7", "8", "9", "÷", "4", "5", "6", "="][i]}</div>;
          })}
          <Mono s={24} style={{ position: "absolute", left: 0, right: 0, bottom: 22, textAlign: "center" }}>{e.label || ""}</Mono>
        </Card>,
      );
    },
  },

  title_slam: {
    h: (e) => 400 + (e.sub ? 110 : 0),
    R: ({ e }) => {
      const f = useCurrentFrame();
      const sh = interpolate(f, [fx(e.at), fx(e.at) + 10], [1, 0], clamp);
      return (
        <div style={{ width: W, display: "flex", flexDirection: "column", alignItems: "center", translate: `${Math.sin(f * 2.3) * 14 * sh}px ${Math.cos(f * 3.1) * 10 * sh}px` }}>
          <Big s={fit(e.text, 920, 360, 0.62)} c={col(e.color, COL.red)} roll={false}>{e.text}</Big>
          {e.sub && <Reveal at={e.at + 0.15} style={{ marginTop: 20 }}><Mono s={fit(e.sub, 900, 80, 0.66)} c={COL.txt} w={800}>{e.sub}</Mono></Reveal>}
        </div>
      );
    },
  },

  illustration: {
    h: (e) => (e.size === "l" ? 420 : 300) + (e.caption ? 70 : 0),
    R: ({ e }) => (
      <div style={{ width: W, display: "flex", flexDirection: "column", alignItems: "center" }}>
        <div style={{ position: "relative" }}>
          <div style={{ position: "absolute", inset: "10%", borderRadius: "50%", background: `radial-gradient(closest-side, ${col(e.glow, COL.gold)}40, transparent)`, scale: "1.6" }} />
          <Ill name={e.name} size={e.size === "l" ? 400 : 280} at={e.at} />
        </div>
        {e.caption && <Mono s={fit(e.caption, 900, 34, 0.66)} c={COL.txt} w={800} style={{ marginTop: 16 }}>{e.caption}</Mono>}
      </div>
    ),
  },

  object3d: { h: () => 480, R: ({ e }) => centerRow(<div style={{ width: 480, height: 480 }}><Object3D kind={e.kind} at={e.at} size={480} /></div>) },

  money_rain: { h: () => 0, R: () => null },
};

/** falling ₹ notes over the whole frame (rendered at scene level, not in the stack) */
export const MoneyRain: React.FC<{ at: number }> = ({ at }) => {
  const f = useCurrentFrame();
  if (f < fx(at)) return null;
  return (
    <>
      {Array.from({ length: 16 }).map((_, i) => {
        const t = (f - fx(at) - i * 2.5) / FPS;
        if (t < 0 || t > 2.2) return null;
        const x = 100 + random(`nx${i}`) * 860, y = 100 + t * (520 + random(`ny${i}`) * 260);
        return <div key={i} style={{ position: "absolute", left: x + Math.sin(t * 4 + i) * 30, top: y, width: 110, height: 56, borderRadius: 8, rotate: `${t * 120 * (random(`r${i}`) - 0.5) + 20}deg`,
          background: "linear-gradient(135deg,#7FD49B,#4FAF73)", border: "2px solid #2E7A4A", opacity: interpolate(t, [0, 0.2, 1.6, 2], [0, 0.9, 0.9, 0], clamp),
          filter: `blur(${random(`b${i}`) > 0.6 ? 3 : 0}px)`, display: "flex", alignItems: "center", justifyContent: "center", font: `900 30px ${SANS}`, color: "#1E5A34" }}>₹</div>;
      })}
    </>
  );
};
