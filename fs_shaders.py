"""THE ANULMENT: GLSL shaders (from the earlier EX Inc. game) for car paint and skin/cloth characters.
Valdora grade: cool clear night (slightly damp streets), sodium street light from above, filmic tone curve. No bloom, no glow."""
from panda3d.core import Shader

VERT = """#version 120
uniform mat4 p3d_ModelViewProjectionMatrix;
uniform mat4 p3d_ModelMatrix;
uniform mat3 p3d_NormalMatrix;
uniform mat4 p3d_ModelViewMatrix;
attribute vec4 p3d_Vertex;
attribute vec3 p3d_Normal;
attribute vec2 p3d_MultiTexCoord0;
attribute vec4 p3d_Tangent;
attribute vec4 p3d_Color;
varying vec4 vcol;
uniform vec3 wspos_view;
varying vec3 wpos; varying vec3 wnrm; varying vec2 uv; varying vec3 wtan; varying float vdist; varying float tsign;
uniform vec4 morph;     // head shape per character: width, depth, height, jaw (1 = unchanged)
uniform float morph_on;
void main() {
  vec4 P = p3d_Vertex;
  if (morph_on > 0.5) {
    float s = smoothstep(1.47, 1.53, P.z);
    float zc = 1.6;
    P.x *= 1.0 + s * (morph.x - 1.0);
    P.y = 0.03 + (P.y - 0.03) * (1.0 + s * (morph.y - 1.0));
    P.z = zc + (P.z - zc) * (1.0 + s * (morph.z - 1.0));
    float j = s * (1.0 - smoothstep(1.53, 1.6, P.z));
    P.x *= 1.0 + j * (morph.w - 1.0);
  }
  gl_Position = p3d_ModelViewProjectionMatrix * P;
  wpos = (p3d_ModelMatrix * P).xyz;
  wnrm = normalize(mat3(p3d_ModelMatrix) * p3d_Normal);
  wtan = mat3(p3d_ModelMatrix) * p3d_Tangent.xyz; tsign = p3d_Tangent.w; vcol = p3d_Color;
  uv = p3d_MultiTexCoord0;
  vdist = length((p3d_ModelViewMatrix * P).xyz);
}
"""

FRAG = """#version 120
uniform sampler2D p3d_Texture0;
uniform sampler2D envmap;
uniform sampler2D normalmap;
uniform vec4 p3d_ColorScale;
uniform struct { vec4 baseColor; vec4 emission; float roughness; float metallic; } p3d_Material;
uniform vec3 campos;
uniform vec3 fogcol; uniform float fogden;
uniform float gloss; uniform float use_tex; uniform float use_nmap; uniform float sheen; uniform float emitboost;
uniform vec4 tint;
uniform float dayk; uniform vec3 fogday; uniform vec3 sundir; uniform sampler2D envday;
varying vec3 wpos; varying vec3 wnrm; varying vec2 uv; varying vec3 wtan; varying float vdist; varying float tsign; varying vec4 vcol;
void main() {
  vec3 N = normalize(wnrm);
  if (use_nmap > 0.5 && dot(wtan, wtan) > 1e-6) {
    // v1.0.0.2: tangent frame rebuilt per pixel from screen-space derivatives (cotangent frame), so the
    // mirrored half of a face/body gets the same lighting as the other half (stored tangent signs were wrong)
    vec3 dp1 = dFdx(wpos); vec3 dp2 = dFdy(wpos); vec2 du1 = dFdx(uv); vec2 du2 = dFdy(uv);
    vec3 dp2p = cross(dp2, N); vec3 dp1p = cross(N, dp1);
    vec3 T = dp2p * du1.x + dp1p * du2.x; vec3 B = dp2p * du1.y + dp1p * du2.y;
    float im = inversesqrt(max(max(dot(T, T), dot(B, B)), 1e-20)); T *= im; B *= im;
    vec3 nm = texture2D(normalmap, uv).xyz * 2.0 - 1.0; nm.xy *= 0.6;   // softer skin grain
    N = normalize(T * nm.x + B * nm.y + N * nm.z);
  }
  vec3 V = normalize(campos - wpos);
  if (dot(N, V) < 0.0) N = -N;
  vec4 base = p3d_Material.baseColor * vcol;
  if (use_tex > 0.5) base *= texture2D(p3d_Texture0, uv);
  base.rgb *= tint.rgb;
  vec3 c = base.rgb;
  // night lighting: cool moon key + purple/orange hemisphere fill + neon rim
  vec3 L = normalize(vec3(0.35, -0.45, 0.82));
  float ndl = max(dot(N, L), 0.0);
  float wrap = max((dot(N, L) + 0.45) / 1.45, 0.0);
  // Valdora night: cool overcast sky fill, wet-street bounce from below, sodium street light from above
  vec3 hemi = mix(vec3(0.17, 0.15, 0.14), vec3(0.17, 0.20, 0.27), N.z * 0.5 + 0.5);
  vec3 diff = c * (hemi * 2.2 + vec3(0.58, 0.64, 0.78) * mix(ndl, wrap, sheen) * 1.0 + vec3(0.09, 0.09, 0.10));
  diff += c * vec3(1.0, 0.66, 0.36) * 0.42 * max(N.z * 0.7 + 0.3, 0.0);
  // daylight: warm sun key + blue sky / warm ground bounce
  vec3 Ls = normalize(sundir);
  float sdl = max(dot(N, Ls), 0.0); float swr = max((dot(N, Ls) + 0.45) / 1.45, 0.0);
  vec3 dhemi = mix(vec3(0.42, 0.38, 0.34), vec3(0.55, 0.66, 0.85), N.z * 0.5 + 0.5);
  vec3 ddiff = c * (dhemi * 1.0 + vec3(1.15, 1.05, 0.92) * mix(sdl, swr, sheen) * 1.0);   // v1.0.4: no over-exposure
  diff = mix(diff, ddiff, dayk); L = normalize(mix(L, Ls, dayk));
  vec3 R = reflect(-V, N);
  vec2 euv = vec2(atan(R.y, R.x) / 6.2831 + 0.5, clamp(0.5 - asin(clamp(R.z, -1.0, 1.0)) / 3.1416, 0.01, 0.99));
  vec3 env = mix(texture2D(envmap, euv).rgb, texture2D(envday, vec2(euv.x, 1.0 - euv.y)).rgb, dayk);
  float fres = 0.04 + 0.96 * pow(1.0 - max(dot(N, V), 0.0), 5.0);
  float spec_amt = gloss * mix(0.25, 1.0, p3d_Material.metallic);
  // v1.0.4: skin / cloth (sheen) get only a faint grazing reflection - no glowing white outline on arms and legs
  float fk = fres * gloss * (1.0 - 0.85 * clamp(sheen, 0.0, 1.0));
  vec3 col = diff * (1.0 - spec_amt * 0.5) + env * (fk + spec_amt * 0.35) * mix(vec3(1.0), c + 0.25, p3d_Material.metallic);
  vec3 H = normalize(L + V);
  col += vec3(0.7, 0.75, 1.0) * pow(max(dot(N, H), 0.0), mix(8.0, 90.0, gloss)) * gloss * 0.6;
  // (v1.0.4: the pink skin/cloth rim light was removed - it made legs and arms look like they were glowing)
  col += p3d_Material.emission.rgb * emitboost;
  col *= p3d_ColorScale.rgb;
  col = min(col, vec3(0.82) + 0.18 * (1.0 - exp(-(max(col - vec3(0.82), vec3(0.0))) * 4.0)));   // soft highlight roll-off instead of clipping to white
  // filmic grade: slightly desaturated, cool shadows, warm highlights (no bloom)
  float lum = dot(col, vec3(0.299, 0.587, 0.114));
  col = mix(vec3(lum), col, 0.86);
  col += (vec3(-0.012, 0.0, 0.022) * (1.0 - smoothstep(0.0, 0.35, lum))) + vec3(0.02, 0.008, -0.012) * smoothstep(0.35, 0.9, lum);
  col = max(col, vec3(0.0));
  float f = 1.0 - exp(-fogden * fogden * vdist * vdist);
  col = mix(col, mix(fogcol, fogday, dayk), clamp(f, 0.0, 1.0));
  gl_FragColor = vec4(col, base.a * p3d_ColorScale.a);
}
"""

_cache = {}


def shader():
    if "s" not in _cache:
        _cache["s"] = Shader.make(Shader.SL_GLSL, VERT, FRAG)
    return _cache["s"]


def apply(np_, app, gloss=0.6, tex=False, nmap=None, sheen=0.0, emitboost=1.0, tint=(1, 1, 1, 1)):
    np_.set_shader(shader())
    np_.set_shader_input("envmap", app.envtex)
    np_.set_shader_input("normalmap", nmap or app.flat_nmap)
    np_.set_shader_input("campos", app.campos_np)
    np_.set_shader_input("fogcol", app.fogcol)
    np_.set_shader_input("fogden", app.fogden)
    np_.set_shader_input("gloss", gloss)
    np_.set_shader_input("use_tex", 1.0 if tex else 0.0)
    np_.set_shader_input("use_nmap", 1.0 if nmap is not None else 0.0)
    np_.set_shader_input("sheen", sheen)
    np_.set_shader_input("emitboost", emitboost)
    np_.set_shader_input("tint", tint)
    np_.set_shader_input("wspos_view", (0, 0, 0))
    np_.set_shader_input("morph", (1, 1, 1, 1))
    np_.set_shader_input("morph_on", 0.0)
