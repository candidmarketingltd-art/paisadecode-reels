import React, { useMemo } from "react";
import { ThreeCanvas } from "@remotion/three";
import * as THREE from "three";
import { useCurrentFrame, spring, interpolate } from "remotion";
import { FPS, clamp, fx } from "./lib";

const lathe = (prof: [number, number][], seg = 96) => new THREE.LatheGeometry(prof.map(([x, y]) => new THREE.Vector2(x, y)), seg);

const Jar: React.FC<{ fill: number }> = ({ fill }) => {
  const body = useMemo(() => lathe([[0, -1.5], [0.82, -1.5], [0.95, -1.42], [1.0, -1.25], [1.0, -0.6], [0.94, -0.45], [1.0, -0.3], [1.0, 0.35], [0.94, 0.5], [1.0, 0.65], [1.0, 0.95], [0.9, 1.2], [0.6, 1.42], [0.34, 1.52], [0.3, 1.7]]), []);
  const top = -1.45 + 2.6 * fill;
  const water = useMemo(() => lathe([[0, -1.45], [0.9, -1.45], [0.94, -1.25], [0.94, top], [0, top]], 64), [top]);
  return (
    <group>
      <mesh geometry={body}><meshPhysicalMaterial color="#5FB4FF" transparent opacity={0.42} roughness={0.08} clearcoat={1} side={THREE.DoubleSide} emissive="#0b3a66" emissiveIntensity={0.35} /></mesh>
      <mesh geometry={water}><meshStandardMaterial color="#2E8CF0" transparent opacity={0.55} roughness={0.2} emissive="#103a70" emissiveIntensity={0.5} /></mesh>
      <mesh position={[0, 1.82, 0]}><cylinderGeometry args={[0.36, 0.36, 0.26, 48]} /><meshStandardMaterial color="#1F6FD1" roughness={0.35} /></mesh>
      <mesh position={[0, -0.05, 0]}><cylinderGeometry args={[1.012, 1.012, 0.5, 96, 1, true]} /><meshStandardMaterial color="#F5C242" roughness={0.4} emissive="#4a3500" emissiveIntensity={0.3} side={THREE.DoubleSide} /></mesh>
    </group>
  );
};

const Coin: React.FC = () => (
  <group rotation={[Math.PI / 2, 0, 0]}>
    <mesh><cylinderGeometry args={[1.4, 1.4, 0.24, 96]} /><meshStandardMaterial color="#F5C242" metalness={0.85} roughness={0.25} emissive="#5a3c00" emissiveIntensity={0.25} /></mesh>
    <mesh position={[0, 0.125, 0]}><torusGeometry args={[1.18, 0.06, 16, 96]} /><meshStandardMaterial color="#FFE08A" metalness={0.9} roughness={0.2} /></mesh>
    <mesh position={[0, -0.125, 0]}><torusGeometry args={[1.18, 0.06, 16, 96]} /><meshStandardMaterial color="#FFE08A" metalness={0.9} roughness={0.2} /></mesh>
  </group>
);

const Box: React.FC = () => (
  <group>
    <mesh><boxGeometry args={[2.2, 1.6, 1.6]} /><meshStandardMaterial color="#C8955A" roughness={0.75} /></mesh>
    <mesh position={[0, 0.81, 0]}><boxGeometry args={[0.45, 0.02, 1.62]} /><meshStandardMaterial color="#E9D3A6" roughness={0.5} /></mesh>
    <mesh position={[0, 0, 0.81]}><boxGeometry args={[0.45, 1.62, 0.02]} /><meshStandardMaterial color="#E9D3A6" roughness={0.5} /></mesh>
  </group>
);

export const Object3D: React.FC<{ kind: string; at: number; size: number }> = ({ kind, at, size }) => {
  const f = useCurrentFrame();
  const s = spring({ frame: f - fx(at), fps: FPS, config: { damping: 12, stiffness: 120 } });
  const spin = -0.9 + s * 0.9 + f * (kind === "coin" ? 0.05 : 0.012);
  const fill = interpolate(f, [fx(at + 0.2), fx(at + 0.2) + 24], [0.02, 0.8], clamp);
  return (
    <ThreeCanvas width={size} height={size} camera={{ position: [0, 0.4, 6.2], fov: 38 }} gl={{ antialias: true, alpha: true, preserveDrawingBuffer: true }}>
      <ambientLight intensity={0.55} />
      <directionalLight position={[3, 4, 5]} intensity={2.2} />
      <directionalLight position={[-4, 1, -2]} intensity={1.4} color="#6EBEFF" />
      <pointLight position={[0, -2, 3]} intensity={6} color="#F5C242" distance={9} />
      <group scale={0.2 + 0.8 * s} position={[0, (1 - s) * -1.2, 0]} rotation={[0.18, spin, -0.06]}>
        {kind === "coin" ? <Coin /> : kind === "box" ? <Box /> : <Jar fill={fill} />}
      </group>
    </ThreeCanvas>
  );
};
