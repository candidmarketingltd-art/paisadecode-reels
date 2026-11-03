import React, { useEffect, useMemo } from "react";
import { ThreeCanvas } from "@remotion/three";
import { useThree } from "@react-three/fiber";
import * as THREE from "three";
import { RoundedBoxGeometry } from "three/examples/jsm/geometries/RoundedBoxGeometry.js";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";
import { useCurrentFrame, spring, interpolate, random, Easing } from "remotion";
import { FPS, clamp, fx } from "./lib";

/* Hero 3D objects, built in code (free, no image generation) and animated with simple physics:
   things drop with gravity and bounce, stacks grow piece by piece, locks open, doors swing, trucks drive in.
   Every object takes `t` = seconds since its cue, so the action lands on the spoken word. */

export const KINDS = ["coin", "coin_stack", "coin_rain", "cash_stack", "gold_bars", "padlock", "vault", "funnel", "chart_up", "chart_down",
  "building", "shop", "truck", "fuel_pump", "gas_cylinder", "pizza_box", "phone", "house", "box", "jar"] as const;

const G = 22; // gravity (scene units / s^2)
/** height above the floor for something dropped from h at time t (seconds), with two decaying bounces */
const drop = (t: number, h = 4) => {
  if (t <= 0) return h;
  const t1 = Math.sqrt((2 * h) / G);
  if (t < t1) return h - 0.5 * G * t * t;
  let v = G * t1 * 0.38, tt = t - t1;
  for (let b = 0; b < 2; b++) {
    const tb = (2 * v) / G;
    if (tt < tb) return v * tt - 0.5 * G * tt * tt;
    tt -= tb; v *= 0.35;
  }
  return 0;
};
const ease = (t: number, a: number, b: number) => interpolate(t, [a, b], [0, 1], { ...clamp, easing: Easing.bezier(0.2, 0.8, 0.2, 1) });

const GOLD = { color: "#F7C64A", metalness: 0.55, roughness: 0.28, emissive: "#6a4300", emissiveIntensity: 0.55 };
const CHARCOAL = { color: "#4A4E57", metalness: 0.35, roughness: 0.38 };

const rbox = (w: number, h: number, d: number, r = 0.08) => new RoundedBoxGeometry(w, h, d, 4, r);

/* --------------------------------------------------------------------------- objects */
const Coin: React.FC<{ r?: number }> = ({ r = 1 }) => (
  <group rotation={[Math.PI / 2, 0, 0]}>
    <mesh><cylinderGeometry args={[r, r, r * 0.16, 64]} /><meshStandardMaterial {...GOLD} /></mesh>
    <mesh position={[0, r * 0.085, 0]}><torusGeometry args={[r * 0.82, r * 0.05, 12, 64]} /><meshStandardMaterial {...GOLD} roughness={0.12} /></mesh>
    <mesh position={[0, -r * 0.085, 0]}><torusGeometry args={[r * 0.82, r * 0.05, 12, 64]} /><meshStandardMaterial {...GOLD} roughness={0.12} /></mesh>
  </group>
);

const CoinStack: React.FC<{ t: number; n?: number }> = ({ t, n = 12 }) => (
  <group position={[0, -1.2, 0]} rotation={[0.35, 0, 0]}>
    {Array.from({ length: n }).map((_, i) => {
      const ti = t - i * 0.09;
      if (ti < 0) return null;
      return <group key={i} position={[(random(`cx${i}`) - 0.5) * 0.1, i * 0.15 + drop(ti, 3), 0]} rotation={[0, random(`cr${i}`) * 3, 0]}>
        <group rotation={[-Math.PI / 2, 0, 0]}><Coin r={0.9} /></group></group>;
    })}
  </group>
);

const CoinRain: React.FC<{ t: number; n?: number }> = ({ t, n = 46 }) => (
  <group position={[0, -1.7, 0]}>
    {Array.from({ length: n }).map((_, i) => {
      const ti = t - i * 0.035;
      if (ti < 0) return null;
      const ring = Math.sqrt(random(`pr${i}`)) * 1.6, a = random(`pa${i}`) * 6.28;
      const rest = Math.max(0, 1.2 - ring * 0.7) + (i / n) * 0.3;
      return <group key={i} position={[Math.cos(a) * ring, rest + drop(ti, 5), Math.sin(a) * ring * 0.6]}
        rotation={[random(`rx${i}`) * 1.2 - 0.6 + (ti < 0.5 ? ti * 9 : 0), random(`ry${i}`) * 6, random(`rz${i}`) * 1.2 - 0.6]}>
        <group rotation={[-Math.PI / 2, 0, 0]}><Coin r={0.42} /></group></group>;
    })}
  </group>
);

const Bundle: React.FC = () => {
  const g = useMemo(() => rbox(2.2, 0.32, 1.1, 0.04), []);
  return (
    <group>
      <mesh geometry={g}><meshStandardMaterial color="#5FBF7E" roughness={0.6} /></mesh>
      <mesh><boxGeometry args={[0.42, 0.335, 1.115]} /><meshStandardMaterial color="#F2E3B3" roughness={0.5} /></mesh>
    </group>
  );
};
const CashStack: React.FC<{ t: number; n?: number }> = ({ t, n = 7 }) => (
  <group position={[0, -1.6, 0]}>
    {Array.from({ length: n }).map((_, i) => {
      const ti = t - i * 0.14;
      if (ti < 0) return null;
      return <group key={i} position={[(random(`bx${i}`) - 0.5) * 0.15, i * 0.33 + drop(ti, 3.5), 0]} rotation={[0, (random(`by${i}`) - 0.5) * 0.25, 0]}><Bundle /></group>;
    })}
  </group>
);

const GoldBars: React.FC<{ t: number }> = ({ t }) => {
  const bar = useMemo(() => {
    const s = new THREE.Shape(); s.moveTo(-0.75, 0); s.lineTo(0.75, 0); s.lineTo(0.6, 0.42); s.lineTo(-0.6, 0.42); s.closePath();
    const geo = new THREE.ExtrudeGeometry(s, { depth: 0.7, bevelEnabled: true, bevelSize: 0.03, bevelThickness: 0.03, bevelSegments: 3 });
    geo.translate(0, 0, -0.35); return geo;
  }, []);
  const pos: [number, number][] = [[-1.6, 0], [0, 0], [1.6, 0], [-0.8, 0.45], [0.8, 0.45], [0, 0.9]];
  return (
    <group position={[0, -1.4, 0]}>
      {pos.map(([x, y], i) => {
        const ti = t - i * 0.12;
        if (ti < 0) return null;
        return <mesh key={i} geometry={bar} position={[x, y + drop(ti, 3), 0]}><meshStandardMaterial {...GOLD} /></mesh>;
      })}
    </group>
  );
};

const Padlock: React.FC<{ t: number }> = ({ t }) => {
  const body = useMemo(() => rbox(2, 1.7, 0.8, 0.18), []);
  const open = ease(t, 0.5, 0.75);           // shackle pops up
  const fall = Math.max(0, t - 1.1);          // then the lock drops away
  return (
    <group position={[0, -0.4 - 0.5 * G * fall * fall * 0.3, 0]} rotation={[0, 0, fall * 1.2]}>
      <mesh geometry={body}><meshStandardMaterial {...CHARCOAL} /></mesh>
      <mesh position={[0, 0, 0.41]}><cylinderGeometry args={[0.16, 0.16, 0.05, 32]} /><meshStandardMaterial {...GOLD} /></mesh>
      <group position={[0.45 * open, 0.85 + 0.55 * open, 0]} rotation={[0, open * 0.9, 0]}>
        <mesh rotation={[0, 0, 0]}><torusGeometry args={[0.62, 0.14, 16, 48, Math.PI]} /><meshStandardMaterial color="#D8DCE3" metalness={0.5} roughness={0.25} emissive="#30343a" emissiveIntensity={0.4} /></mesh>
        <mesh position={[-0.62, -0.3, 0]}><cylinderGeometry args={[0.14, 0.14, 0.6, 24]} /><meshStandardMaterial color="#D8DCE3" metalness={0.5} roughness={0.25} emissive="#30343a" emissiveIntensity={0.4} /></mesh>
        <mesh position={[0.62, -0.3, 0]}><cylinderGeometry args={[0.14, 0.14, 0.6, 24]} /><meshStandardMaterial color="#D8DCE3" metalness={0.5} roughness={0.25} emissive="#30343a" emissiveIntensity={0.4} /></mesh>
      </group>
    </group>
  );
};

const Vault: React.FC<{ t: number }> = ({ t }) => {
  const body = useMemo(() => rbox(2.6, 2.6, 2.2, 0.15), []);
  const door = useMemo(() => rbox(2.2, 2.2, 0.25, 0.08), []);
  const open = ease(t, 0.5, 1.3);
  return (
    <group position={[0, -0.2, 0]}>
      <mesh geometry={body}><meshStandardMaterial {...CHARCOAL} /></mesh>
      <mesh position={[0, 0, 1.05]}><boxGeometry args={[2.0, 2.0, 0.05]} /><meshStandardMaterial color="#F5C242" emissive="#F5C242" emissiveIntensity={1.4 * open} /></mesh>
      <group position={[-1.1, 0, 1.2]} rotation={[0, -open * 1.9, 0]}>
        <group position={[1.1, 0, 0]}>
          <mesh geometry={door}><meshStandardMaterial color="#5A5E68" metalness={0.45} roughness={0.3} /></mesh>
          <mesh position={[0, 0, 0.18]} rotation={[Math.PI / 2, t * 3, 0]}><torusGeometry args={[0.45, 0.07, 12, 40]} /><meshStandardMaterial {...GOLD} /></mesh>
        </group>
      </group>
    </group>
  );
};

const Funnel: React.FC<{ t: number }> = ({ t }) => (
  <group position={[0, 0.2, 0]}>
    <mesh position={[0, 0.4, 0]}><cylinderGeometry args={[1.8, 0.35, 1.8, 48, 1, true]} /><meshStandardMaterial color="#AEB6C2" metalness={0.45} roughness={0.3} side={THREE.DoubleSide} transparent opacity={0.85} /></mesh>
    <mesh position={[0, -0.9, 0]}><cylinderGeometry args={[0.35, 0.35, 0.8, 32, 1, true]} /><meshStandardMaterial color="#AEB6C2" metalness={0.45} roughness={0.3} side={THREE.DoubleSide} /></mesh>
    {Array.from({ length: 18 }).map((_, i) => {
      const tt = ((t - i * 0.16) % 1.6 + 1.6) % 1.6;
      if (t - i * 0.16 < 0) return null;
      const y = 3.2 - 0.5 * G * 0.35 * tt * tt;
      const r = Math.max(0, 1.4 * (y - 0.4) / 2.8) * (random(`fr${i}`) - 0.5);
      return <group key={i} position={[r, y, 0.2]} rotation={[tt * 6, i, 0]}><Coin r={0.28} /></group>;
    })}
  </group>
);

const Chart: React.FC<{ t: number; up: boolean }> = ({ t, up }) => {
  const hs = up ? [0.8, 1.3, 1.9, 2.7, 3.6] : [3.6, 2.8, 2.0, 1.3, 0.7];
  return (
    <group position={[-2, -1.8, 0]}>
      {hs.map((h, i) => {
        const k = spring({ frame: (t - i * 0.15) * FPS, fps: FPS, config: { damping: 11, stiffness: 120 } });
        const hh = Math.max(0.001, h * k);
        return <mesh key={i} position={[i * 1.0, hh / 2, 0]}><boxGeometry args={[0.7, hh, 0.7]} />
          <meshStandardMaterial color={up ? (i === 4 ? "#54D68C" : "#3D8F63") : (i === 4 ? "#EE5454" : "#9C3B3B")} roughness={0.35} metalness={0.2} /></mesh>;
      })}
    </group>
  );
};

const Building: React.FC<{ t: number }> = ({ t }) => {
  const floors = 7, cols = 4;
  const body = useMemo(() => rbox(2.4, 4.6, 2, 0.06), []);
  return (
    <group position={[0, -0.2, 0]}>
      <mesh geometry={body}><meshStandardMaterial color="#3A4150" metalness={0.4} roughness={0.35} /></mesh>
      {Array.from({ length: floors * cols }).map((_, i) => {
        const f = Math.floor(i / cols), c = i % cols;
        const on = t > 0.25 + f * 0.12 + random(`w${i}`) * 0.25;
        return <mesh key={i} position={[-0.81 + c * 0.54, -1.9 + f * 0.62, 1.005]}><planeGeometry args={[0.36, 0.4]} />
          <meshStandardMaterial color={on ? "#FFD976" : "#1A1D24"} emissive={on ? "#F5C242" : "#000"} emissiveIntensity={on ? 1.2 : 0} /></mesh>;
      })}
    </group>
  );
};

const Shop: React.FC<{ t: number }> = ({ t }) => {
  const up = ease(t, 0.4, 1.0);
  return (
    <group position={[0, -0.6, 0]}>
      <mesh><boxGeometry args={[3.2, 2.4, 1.6]} /><meshStandardMaterial color="#E8E2D2" roughness={0.6} /></mesh>
      {Array.from({ length: 8 }).map((_, i) => (
        <mesh key={i} position={[-1.4 + i * 0.4, 1.35, 0.95]} rotation={[0.5, 0, 0]}><boxGeometry args={[0.4, 0.08, 0.9]} />
          <meshStandardMaterial color={i % 2 ? "#F5C242" : "#FFFFFF"} roughness={0.5} /></mesh>))}
      <mesh position={[0, -0.35, 0.81]}><planeGeometry args={[2.2, 1.6]} /><meshStandardMaterial color="#F5C242" emissive="#F5C242" emissiveIntensity={0.9} /></mesh>
      <mesh position={[0, 0.45 - 0.8 * (1 - up), 0.82]} scale={[1, Math.max(0.02, 1 - up), 1]}><planeGeometry args={[2.2, 1.6]} /><meshStandardMaterial color="#6E737D" metalness={0.6} roughness={0.4} /></mesh>
    </group>
  );
};

const Wheel: React.FC<{ x: number; z: number; spin: number }> = ({ x, z, spin }) => (
  <mesh position={[x, -0.75, z]} rotation={[Math.PI / 2, 0, spin]}><cylinderGeometry args={[0.42, 0.42, 0.3, 32]} /><meshStandardMaterial color="#111" roughness={0.8} /></mesh>
);
const Truck: React.FC<{ t: number }> = ({ t }) => {
  const k = ease(t, 0, 1.0), x = -9 * (1 - k);
  const cargo = useMemo(() => rbox(3, 1.9, 1.7, 0.06), []), cab = useMemo(() => rbox(1.2, 1.4, 1.6, 0.15), []);
  return (
    <group position={[x, -0.2, 0]} rotation={[0, -0.35, 0]}>
      <mesh geometry={cargo} position={[-0.6, 0.35, 0]}><meshStandardMaterial color="#F2F0EA" roughness={0.5} /></mesh>
      <mesh position={[-0.6, 0.35, 0.86]}><planeGeometry args={[2.6, 0.35]} /><meshStandardMaterial color="#F5C242" /></mesh>
      <mesh geometry={cab} position={[1.55, 0.1, 0]}><meshStandardMaterial color="#E85A3C" roughness={0.35} metalness={0.3} /></mesh>
      <mesh position={[2.16, 0.35, 0]}><boxGeometry args={[0.02, 0.6, 1.3]} /><meshStandardMaterial color="#9BD4FF" metalness={0.5} roughness={0.1} /></mesh>
      {[-1.6, 0.3, 1.6].map((wx) => [-0.8, 0.8].map((wz) => <Wheel key={`${wx}${wz}`} x={wx} z={wz} spin={-x * 2.4} />))}
    </group>
  );
};

const FuelPump: React.FC<{ t: number }> = ({ t }) => {
  const body = useMemo(() => rbox(1.6, 3.4, 1.0, 0.12), []);
  const glow = 0.6 + 0.4 * Math.sin(t * 8);
  return (
    <group position={[0, -0.2, 0]}>
      <mesh geometry={body}><meshStandardMaterial color="#2E3138" metalness={0.4} roughness={0.35} /></mesh>
      <mesh position={[0, 1.95, 0]}><boxGeometry args={[1.8, 0.4, 1.1]} /><meshStandardMaterial {...GOLD} metalness={0.6} /></mesh>
      <mesh position={[0, 0.8, 0.51]}><planeGeometry args={[1.1, 0.7]} /><meshStandardMaterial color="#54D68C" emissive="#54D68C" emissiveIntensity={glow} /></mesh>
      <mesh position={[0.95, 0.2, 0.2]} rotation={[0, 0, 0.3]}><boxGeometry args={[0.25, 0.9, 0.3]} /><meshStandardMaterial color="#111" roughness={0.6} /></mesh>
      <mesh position={[0.95, -0.9, 0.2]}><torusGeometry args={[0.5, 0.06, 10, 30, Math.PI]} /><meshStandardMaterial color="#111" /></mesh>
    </group>
  );
};

const GasCylinder: React.FC = () => {
  const g = useMemo(() => new THREE.LatheGeometry([[0, -1.9], [0.95, -1.9], [1.05, -1.6], [1.1, -1.2], [1.1, 1.0], [0.9, 1.5], [0.4, 1.75], [0.4, 2.0], [0, 2.0]].map(([x, y]) => new THREE.Vector2(x, y)), 64), []);
  return (
    <group position={[0, -0.1, 0]}>
      <mesh geometry={g}><meshStandardMaterial color="#D23A30" metalness={0.3} roughness={0.25} /></mesh>
      <mesh position={[0, 2.15, 0]}><cylinderGeometry args={[0.3, 0.3, 0.3, 24]} /><meshStandardMaterial color="#C9CCD3" metalness={1} roughness={0.2} /></mesh>
      <mesh position={[0, -1.95, 0]}><cylinderGeometry args={[1.0, 1.0, 0.2, 48, 1, true]} /><meshStandardMaterial color="#2A2C31" side={THREE.DoubleSide} /></mesh>
    </group>
  );
};

const PizzaBox: React.FC<{ t: number }> = ({ t }) => {
  const open = ease(t, 0.5, 1.1);
  return (
    <group position={[0, -0.8, 0]} rotation={[0.45, 0, 0]}>
      <mesh><boxGeometry args={[3, 0.35, 3]} /><meshStandardMaterial color="#C9955A" roughness={0.8} /></mesh>
      <mesh position={[0, 0.2, 0]}><cylinderGeometry args={[1.25, 1.25, 0.08, 48]} /><meshStandardMaterial color="#E9B44C" roughness={0.6} /></mesh>
      {Array.from({ length: 9 }).map((_, i) => <mesh key={i} position={[Math.cos(i * 0.7) * (0.3 + (i % 3) * 0.3), 0.26, Math.sin(i * 0.7) * (0.3 + (i % 3) * 0.3)]}>
        <cylinderGeometry args={[0.14, 0.14, 0.04, 20]} /><meshStandardMaterial color="#B5332A" roughness={0.5} /></mesh>)}
      <group position={[0, 0.18, -1.5]} rotation={[-open * 1.9, 0, 0]}>
        <mesh position={[0, 0, 1.5]}><boxGeometry args={[3, 0.06, 3]} /><meshStandardMaterial color="#D7A66B" roughness={0.8} /></mesh>
      </group>
    </group>
  );
};

const Phone: React.FC<{ t: number }> = ({ t }) => {
  const g = useMemo(() => rbox(2, 4, 0.22, 0.28), []);
  return (
    <group rotation={[0.1, -0.4 + ease(t, 0, 0.8) * 0.4, 0]}>
      <mesh geometry={g}><meshStandardMaterial color="#1C1E23" metalness={0.7} roughness={0.25} /></mesh>
      <mesh position={[0, 0, 0.115]}><planeGeometry args={[1.8, 3.75]} /><meshStandardMaterial color="#6EBEFF" emissive="#3E7FD0" emissiveIntensity={0.9} /></mesh>
      <mesh position={[0, 0.6, 0.12]}><planeGeometry args={[1.3, 0.5]} /><meshStandardMaterial color="#F5C242" emissive="#F5C242" emissiveIntensity={0.8} /></mesh>
    </group>
  );
};

const House: React.FC = () => {
  const roof = useMemo(() => { const s = new THREE.Shape(); s.moveTo(-1.9, 0); s.lineTo(1.9, 0); s.lineTo(0, 1.4); s.closePath();
    const g = new THREE.ExtrudeGeometry(s, { depth: 2.4, bevelEnabled: false }); g.translate(0, 0, -1.2); return g; }, []);
  return (
    <group position={[0, -1, 0]}>
      <mesh><boxGeometry args={[3, 2, 2]} /><meshStandardMaterial color="#EFE6D2" roughness={0.6} /></mesh>
      <mesh geometry={roof} position={[0, 1, 0]}><meshStandardMaterial color="#C8553D" roughness={0.5} /></mesh>
      <mesh position={[0, -0.4, 1.01]}><planeGeometry args={[0.7, 1.2]} /><meshStandardMaterial color="#6B4A2B" /></mesh>
      <mesh position={[0.95, 0.2, 1.01]}><planeGeometry args={[0.6, 0.6]} /><meshStandardMaterial color="#FFD976" emissive="#F5C242" emissiveIntensity={0.8} /></mesh>
    </group>
  );
};

const Parcel: React.FC = () => (
  <group>
    <mesh><boxGeometry args={[2.2, 1.6, 1.6]} /><meshStandardMaterial color="#C8955A" roughness={0.75} /></mesh>
    <mesh position={[0, 0.81, 0]}><boxGeometry args={[0.45, 0.02, 1.62]} /><meshStandardMaterial color="#E9D3A6" roughness={0.5} /></mesh>
  </group>
);

const Jar: React.FC<{ fill: number }> = ({ fill }) => {
  const lathe = (p: [number, number][], s = 96) => new THREE.LatheGeometry(p.map(([x, y]) => new THREE.Vector2(x, y)), s);
  const body = useMemo(() => lathe([[0, -1.5], [0.82, -1.5], [0.95, -1.42], [1.0, -1.25], [1.0, -0.6], [0.94, -0.45], [1.0, -0.3], [1.0, 0.35], [0.94, 0.5], [1.0, 0.65], [1.0, 0.95], [0.9, 1.2], [0.6, 1.42], [0.34, 1.52], [0.3, 1.7]]), []);
  const top = -1.45 + 2.6 * fill;
  const water = useMemo(() => lathe([[0, -1.45], [0.9, -1.45], [0.94, -1.25], [0.94, top], [0, top]], 64), [top]);
  return (
    <group>
      <mesh geometry={body}><meshPhysicalMaterial color="#5FB4FF" transparent opacity={0.42} roughness={0.08} clearcoat={1} side={THREE.DoubleSide} emissive="#0b3a66" emissiveIntensity={0.35} /></mesh>
      <mesh geometry={water}><meshStandardMaterial color="#2E8CF0" transparent opacity={0.55} roughness={0.2} emissive="#103a70" emissiveIntensity={0.5} /></mesh>
      <mesh position={[0, 1.82, 0]}><cylinderGeometry args={[0.36, 0.36, 0.26, 48]} /><meshStandardMaterial color="#1F6FD1" roughness={0.35} /></mesh>
      <mesh position={[0, -0.05, 0]}><cylinderGeometry args={[1.012, 1.012, 0.5, 96, 1, true]} /><meshStandardMaterial color="#F5C242" roughness={0.4} side={THREE.DoubleSide} /></mesh>
    </group>
  );
};

/* reflective studio environment so metals (gold, chrome) actually shine */
const Env: React.FC = () => {
  const { gl, scene } = useThree();
  useEffect(() => {
    const pm = new THREE.PMREMGenerator(gl);
    const tex = pm.fromScene(new RoomEnvironment(), 0.04).texture;
    scene.environment = tex;
    return () => { tex.dispose(); pm.dispose(); };
  }, [gl, scene]);
  return null;
};

/* objects that drop in as a whole (the stacks animate their own pieces) */
const SELF_ANIMATED = new Set(["coin_stack", "coin_rain", "cash_stack", "gold_bars", "truck", "chart_up", "chart_down", "funnel"]);

export const Object3D: React.FC<{ kind: string; at: number; size: number }> = ({ kind, at, size }) => {
  const f = useCurrentFrame();
  const t = (f - fx(at)) / FPS;
  const s = spring({ frame: f - fx(at), fps: FPS, config: { damping: 12, stiffness: 120 } });
  const self = SELF_ANIMATED.has(kind);
  const y = self ? 0 : drop(t, 5);                       // whole object falls in and bounces
  const wobble = self ? 0 : Math.sin(t * 9) * Math.exp(-t * 3) * 0.12;
  const spin = kind === "coin" ? t * 3.2 : -0.6 + Math.min(1, t * 1.4) * 0.6 + Math.sin(f / 45) * 0.12;
  const fill = interpolate(t, [0.2, 1.0], [0.02, 0.8], clamp);
  const obj = (() => {
    switch (kind) {
      case "coin": return <Coin r={1.5} />;
      case "coin_stack": return <CoinStack t={t} />;
      case "coin_rain": return <CoinRain t={t} />;
      case "cash_stack": return <CashStack t={t} />;
      case "gold_bars": return <GoldBars t={t} />;
      case "padlock": return <Padlock t={t} />;
      case "vault": return <Vault t={t} />;
      case "funnel": return <Funnel t={t} />;
      case "chart_up": return <Chart t={t} up />;
      case "chart_down": return <Chart t={t} up={false} />;
      case "building": return <Building t={t} />;
      case "shop": return <Shop t={t} />;
      case "truck": return <Truck t={t} />;
      case "fuel_pump": return <FuelPump t={t} />;
      case "gas_cylinder": return <GasCylinder />;
      case "pizza_box": return <PizzaBox t={t} />;
      case "phone": return <Phone t={t} />;
      case "house": return <House />;
      case "jar": return <Jar fill={fill} />;
      default: return <Parcel />;
    }
  })();
  return (
    <ThreeCanvas width={size} height={size} camera={{ position: [0, 1.2, 8.5], fov: 38 }} gl={{ antialias: true, alpha: true, preserveDrawingBuffer: true }}>
      <Env />
      <ambientLight intensity={0.6} />
      <hemisphereLight args={["#FFF1D6", "#1A1D24", 0.9]} />
      <directionalLight position={[3, 5, 6]} intensity={2.4} color="#FFF4DD" />
      <directionalLight position={[-5, 2, -3]} intensity={1.6} color="#6EBEFF" />
      <pointLight position={[0, -2.5, 3]} intensity={8} color="#F5C242" distance={10} />
      <group scale={self ? 1 : 0.35 + 0.65 * s} position={[0, y, 0]} rotation={[0.12 + wobble, spin, wobble * 0.6]}>
        {obj}
      </group>
    </ThreeCanvas>
  );
};
