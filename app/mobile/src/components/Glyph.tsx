import React from 'react';
import Svg, { Circle, Line, Path, Polyline, G, Rect } from 'react-native-svg';

interface GlyphProps {
  size?: number;
  color?: string;
  active?: boolean;
}

// PORTHOLE — concentric rings with a pupil dot (eye-of-the-instrument)
export function PortholeGlyph({ size = 24, color = '#fff', active = false }: GlyphProps) {
  const s = size;
  return (
    <Svg width={s} height={s} viewBox="0 0 24 24">
      <Circle cx="12" cy="12" r="10" stroke={color} strokeWidth={active ? 1.5 : 1} fill="none" opacity={0.4} />
      <Circle cx="12" cy="12" r="6.5" stroke={color} strokeWidth={active ? 1.75 : 1.25} fill="none" />
      <Circle cx="12" cy="12" r="2.5" fill={color} />
      <Line x1="12" y1="2" x2="12" y2="4.5" stroke={color} strokeWidth={1.5} strokeLinecap="round" opacity={0.7} />
      <Line x1="12" y1="19.5" x2="12" y2="22" stroke={color} strokeWidth={1.5} strokeLinecap="round" opacity={0.7} />
      <Line x1="2" y1="12" x2="4.5" y2="12" stroke={color} strokeWidth={1.5} strokeLinecap="round" opacity={0.7} />
      <Line x1="19.5" y1="12" x2="22" y2="12" stroke={color} strokeWidth={1.5} strokeLinecap="round" opacity={0.7} />
    </Svg>
  );
}

// CONTROL — four-arrow directional rune
export function ControlGlyph({ size = 24, color = '#fff', active = false }: GlyphProps) {
  const s = size;
  const sw = active ? 1.75 : 1.5;
  return (
    <Svg width={s} height={s} viewBox="0 0 24 24">
      <Circle cx="12" cy="12" r="2.25" fill={color} />
      <Polyline points="12,3 9,6 12,3 15,6" stroke={color} strokeWidth={sw} fill="none" strokeLinecap="round" strokeLinejoin="round" />
      <Polyline points="12,21 9,18 12,21 15,18" stroke={color} strokeWidth={sw} fill="none" strokeLinecap="round" strokeLinejoin="round" />
      <Polyline points="3,12 6,9 3,12 6,15" stroke={color} strokeWidth={sw} fill="none" strokeLinecap="round" strokeLinejoin="round" />
      <Polyline points="21,12 18,9 21,12 18,15" stroke={color} strokeWidth={sw} fill="none" strokeLinecap="round" strokeLinejoin="round" />
      <Line x1="12" y1="8" x2="12" y2="6" stroke={color} strokeWidth={sw} strokeLinecap="round" opacity={0.55} />
      <Line x1="12" y1="16" x2="12" y2="18" stroke={color} strokeWidth={sw} strokeLinecap="round" opacity={0.55} />
      <Line x1="8" y1="12" x2="6" y2="12" stroke={color} strokeWidth={sw} strokeLinecap="round" opacity={0.55} />
      <Line x1="16" y1="12" x2="18" y2="12" stroke={color} strokeWidth={sw} strokeLinecap="round" opacity={0.55} />
    </Svg>
  );
}

// TALK — sound waves emanating from a dot (no traditional mic)
export function TalkGlyph({ size = 24, color = '#fff', active = false }: GlyphProps) {
  const s = size;
  const sw = active ? 1.75 : 1.5;
  return (
    <Svg width={s} height={s} viewBox="0 0 24 24">
      <Circle cx="12" cy="12" r="2" fill={color} />
      <Path d="M 7 12 Q 7 9 9 7" stroke={color} strokeWidth={sw} fill="none" strokeLinecap="round" />
      <Path d="M 7 12 Q 7 15 9 17" stroke={color} strokeWidth={sw} fill="none" strokeLinecap="round" />
      <Path d="M 17 12 Q 17 9 15 7" stroke={color} strokeWidth={sw} fill="none" strokeLinecap="round" />
      <Path d="M 17 12 Q 17 15 15 17" stroke={color} strokeWidth={sw} fill="none" strokeLinecap="round" />
      <Path d="M 4 12 Q 4 7 7 4" stroke={color} strokeWidth={sw} fill="none" strokeLinecap="round" opacity={0.55} />
      <Path d="M 4 12 Q 4 17 7 20" stroke={color} strokeWidth={sw} fill="none" strokeLinecap="round" opacity={0.55} />
      <Path d="M 20 12 Q 20 7 17 4" stroke={color} strokeWidth={sw} fill="none" strokeLinecap="round" opacity={0.55} />
      <Path d="M 20 12 Q 20 17 17 20" stroke={color} strokeWidth={sw} fill="none" strokeLinecap="round" opacity={0.55} />
    </Svg>
  );
}

// WAND — radar sweep with crosshair
export function WandGlyph({ size = 24, color = '#fff', active = false }: GlyphProps) {
  const s = size;
  const sw = active ? 1.75 : 1.5;
  return (
    <Svg width={s} height={s} viewBox="0 0 24 24">
      <Circle cx="12" cy="12" r="9.5" stroke={color} strokeWidth={sw} fill="none" opacity={0.45} />
      <Circle cx="12" cy="12" r="5.5" stroke={color} strokeWidth={sw} fill="none" opacity={0.75} />
      <Line x1="12" y1="12" x2="19" y2="6" stroke={color} strokeWidth={sw + 0.25} strokeLinecap="round" />
      <Path d="M 12 12 L 19 6 L 19 12 Z" fill={color} opacity={0.18} />
      <Circle cx="12" cy="12" r="1.6" fill={color} />
    </Svg>
  );
}

// ZEN — lotus-arc breathing glyph
export function ZenGlyph({ size = 24, color = '#fff', active = false }: GlyphProps) {
  const s = size;
  const sw = active ? 1.75 : 1.5;
  return (
    <Svg width={s} height={s} viewBox="0 0 24 24">
      <Path d="M 12 4 Q 4 12 12 20 Q 20 12 12 4 Z" stroke={color} strokeWidth={sw} fill="none" strokeLinejoin="round" />
      <Path d="M 6 12 Q 12 6 18 12 Q 12 18 6 12 Z" stroke={color} strokeWidth={sw} fill="none" strokeLinejoin="round" opacity={0.6} />
      <Circle cx="12" cy="12" r="1.6" fill={color} />
    </Svg>
  );
}

// SETTINGS — hexagonal frame (cyber-organic, not the gear cliché)
export function SettingsGlyph({ size = 24, color = '#fff', active = false }: GlyphProps) {
  const s = size;
  const sw = active ? 1.5 : 1.25;
  return (
    <Svg width={s} height={s} viewBox="0 0 24 24">
      <Path d="M 12 3 L 20 7.5 L 20 16.5 L 12 21 L 4 16.5 L 4 7.5 Z" stroke={color} strokeWidth={sw} fill="none" strokeLinejoin="round" />
      <Circle cx="12" cy="12" r="3" stroke={color} strokeWidth={sw} fill="none" />
      <Circle cx="12" cy="12" r="0.8" fill={color} />
    </Svg>
  );
}

// STOP — hexagonal stop badge
export function StopGlyph({ size = 24, color = '#fff' }: GlyphProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24">
      <Path d="M 8 3 L 16 3 L 21 8 L 21 16 L 16 21 L 8 21 L 3 16 L 3 8 Z" stroke={color} strokeWidth={1.75} fill="none" strokeLinejoin="round" />
      <Rect x="8" y="8" width="8" height="8" fill={color} rx="1" />
    </Svg>
  );
}

// BATTERY — minimal cell with bars
export function BatteryGlyph({ size = 18, color = '#fff', level = 100 }: GlyphProps & { level?: number }) {
  const filled = Math.round((level / 100) * 3);
  return (
    <Svg width={size} height={size} viewBox="0 0 24 14">
      <Rect x="1" y="2" width="20" height="10" stroke={color} strokeWidth={1.5} fill="none" rx="2" />
      <Rect x="22" y="5" width="1.5" height="4" fill={color} rx="0.5" />
      {Array.from({ length: 3 }).map((_, i) => (
        <Rect
          key={i}
          x={3 + i * 6}
          y={4}
          width="4"
          height="6"
          rx="0.5"
          fill={color}
          opacity={i < filled ? 1 : 0.18}
        />
      ))}
    </Svg>
  );
}

// ALERT — triangle with dot
export function AlertGlyph({ size = 18, color = '#fff' }: GlyphProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24">
      <Path d="M 12 3 L 22 20 L 2 20 Z" stroke={color} strokeWidth={1.75} fill="none" strokeLinejoin="round" />
      <Line x1="12" y1="9" x2="12" y2="14" stroke={color} strokeWidth={1.75} strokeLinecap="round" />
      <Circle cx="12" cy="17" r="1" fill={color} />
    </Svg>
  );
}

// PERSON glyph — abstract figure
export function PersonGlyph({ size = 18, color = '#fff' }: GlyphProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24">
      <Circle cx="12" cy="7" r="3" stroke={color} strokeWidth={1.5} fill="none" />
      <Path d="M 4 21 Q 4 14 12 14 Q 20 14 20 21" stroke={color} strokeWidth={1.5} fill="none" strokeLinecap="round" />
    </Svg>
  );
}

// CONNECTION dot — ring
export function ConnectionGlyph({ size = 12, color = '#fff' }: GlyphProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 12 12">
      <Circle cx="6" cy="6" r="5" stroke={color} strokeWidth={1.25} fill="none" opacity={0.4} />
      <Circle cx="6" cy="6" r="2.5" fill={color} />
    </Svg>
  );
}

// CHEVRON — for back / forward
export function ChevronGlyph({ size = 20, color = '#fff', direction = 'left' as 'left' | 'right' | 'down' | 'up' }: GlyphProps & { direction?: 'left' | 'right' | 'down' | 'up' }) {
  const rotation = { left: 0, up: 90, right: 180, down: 270 }[direction];
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24">
      <G rotation={rotation} originX={12} originY={12}>
        <Polyline points="14,6 8,12 14,18" stroke={color} strokeWidth={1.75} fill="none" strokeLinecap="round" strokeLinejoin="round" />
      </G>
    </Svg>
  );
}
