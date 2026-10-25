"""Shaders GLSL (OpenGL 4.3). Todo el trabajo de color se hace en luz lineal HDR (float16)."""

VS_FULL = """#version 430
in vec2 in_pos;
void main(){ gl_Position = vec4(in_pos, 0.0, 1.0); }
"""

COMMON = """
uniform vec2 uRes;        // resolución de salida (px)
uniform vec3 uCam;        // posición de la cámara (m)
uniform float uF;         // focal en píxeles
uniform vec2 uShift;      // desplazamiento del punto principal (px), como un objetivo descentrable
vec3 rayDir(vec2 px){ return vec3((px - 0.5*uRes - uShift)/uF, 1.0); }
float hash12(vec2 p){ vec3 p3 = fract(vec3(p.xyx) * .1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }
float luma(vec3 c){ return dot(c, vec3(0.2126, 0.7152, 0.0722)); }
"""

# ---------------------------------------------------------------- cielo (Nishita, dispersión simple)
FS_SKY = """#version 430
out vec4 frag;
""" + COMMON + """
uniform vec3 uSunDir;
uniform float uHaze;
uniform float uSunDisk;   // multiplicador del disco solar
uniform float uSkyGain;
uniform float uScale;     // el cielo se calcula a resolución reducida
const float RE = 6360e3, RA = 6420e3, HR = 7994.0, HM = 1200.0;
const vec3 BR = vec3(5.8e-6, 13.5e-6, 33.1e-6);
const float BM = 21e-6;
vec2 rs(vec3 o, vec3 d, float r){ float b = dot(o,d); float c = dot(o,o)-r*r; float h = b*b-c; if(h<0.0) return vec2(-1.0); h = sqrt(h); return vec2(-b-h, -b+h); }
void main(){
  vec2 px = gl_FragCoord.xy * uScale;
  vec3 v = normalize(rayDir(px));
  vec3 o = vec3(0.0, RE + 2.0, 0.0);
  vec3 vv = v; vv.y = max(vv.y, -0.02);
  vv = normalize(vv);
  float t1 = rs(o, vv, RA).y;
  const int N = 16, NL = 8;
  float ds = t1 / float(N);
  float mu = dot(vv, uSunDir);
  float pr = 3.0/(16.0*3.14159265)*(1.0+mu*mu);
  float g = 0.76;
  float pm = 3.0/(8.0*3.14159265)*((1.0-g*g)*(1.0+mu*mu))/((2.0+g*g)*pow(1.0+g*g-2.0*g*mu, 1.5));
  vec3 sr = vec3(0), sm = vec3(0); float odr = 0.0, odm = 0.0;
  for(int i=0;i<N;i++){
    vec3 p = o + vv*(ds*(float(i)+0.5));
    float h = length(p) - RE;
    float hr = exp(-h/HR)*ds, hm = exp(-h/HM)*ds;
    odr += hr; odm += hm;
    float tl = rs(p, uSunDir, RA).y; float dl = tl/float(NL); float lr=0.0, lm=0.0; bool ok = true;
    for(int j=0;j<NL;j++){ vec3 q = p + uSunDir*(dl*(float(j)+0.5)); float hh = length(q)-RE; if(hh<0.0){ok=false;break;} lr += exp(-hh/HR)*dl; lm += exp(-hh/HM)*dl; }
    if(ok){ vec3 tau = BR*(odr+lr) + BM*1.1*(odm+lm)*uHaze; vec3 att = exp(-tau); sr += att*hr; sm += att*hm; }
  }
  vec3 col = 20.0*(sr*BR*pr + sm*BM*uHaze*pm);
  // disco solar con oscurecimiento del limbo, atenuado por la atmósfera
  float cosA = dot(v, uSunDir);
  float ang = acos(clamp(cosA, -1.0, 1.0));
  float R = 0.0093;  // radio angular exagerado ~2x para que se lea en pantalla
  if(ang < R){
    float r = ang / R; float limb = 1.0 - 0.6*(1.0 - sqrt(1.0 - r*r));
    vec3 tau = BR*odr + BM*1.1*odm*uHaze;
    col += uSunDisk * 600.0 * limb * exp(-tau*0.35) * smoothstep(1.0, 0.92, r);
  }
  frag = vec4(col * uSkyGain, 1.0);
}
"""

# ---------------------------------------------------------------- planos con trazado de rayos
FS_PLANE = """#version 430
out vec4 frag;
""" + COMMON + """
uniform sampler2D uTex;      // albedo lineal premultiplicado (float16, con mipmaps)
uniform sampler2D uEmit;     // emisión (lineal, premultiplicada por cobertura)
uniform float uHasEmit;
uniform float uEmitGain;
uniform int uAxis;           // 0: plano x=cte, 1: y=cte (suelo/techo), 2: z=cte (frente a cámara)
uniform float uValue;
uniform vec4 uExt;           // extensión en las dos coordenadas del plano: (u0, u1, v0, v1)
uniform vec2 uTexSize;
uniform int uScreenSpace;    // 1 = textura ya en espacio de pantalla (personajes)
// iluminación
uniform float uFlat;         // 0 = superficie real (usa su normal), 1 = recorte ilustrado
uniform vec3 uAmbTop, uAmbBot;
uniform vec3 uSunCol; uniform vec3 uSunDir; uniform float uSunOn;
uniform int uNL; uniform vec4 uLPos[6]; uniform vec4 uLCol[6];   // luces puntuales: pos+radio, color*intensidad
uniform int uWinAxis; uniform float uWinValue; uniform int uNW; uniform vec4 uWin[6]; uniform vec4 uBlinds; // ventanas
uniform vec4 uCanopy;        // proyección de copa de árbol: (centro x, z, radio, altura); radio 0 = sin copa
uniform float uTime;
uniform sampler2D uShadow;   // sombras de personajes en espacio de pantalla (r)
uniform float uShadowOn; uniform float uShadowSoft;
uniform vec3 uRimCol; uniform float uRim; uniform vec2 uRimDir;
uniform float uSelfLit;      // 1 = no recibe luz (ya emisivo / cielo pintado)
// atmósfera
uniform vec3 uSigma;         // coeficiente de extinción (1/m) por canal
uniform vec3 uFogCol;        // luz dispersada hacia el ojo
uniform vec3 uFogSun;        // dispersión Mie hacia el sol
// cámara
uniform float uCocK;         // CoC(px) = uCocK * |1 - focus/d|  (lente delgada)
uniform float uFocus;
uniform vec2 uVel;           // velocidad de cámara (px por obturación a 1/d=1): dx = uVel * (1/d)
uniform vec3 uCamVel;        // desplazamiento de cámara durante la obturación (m)
uniform int uMaxTaps;
uniform float uPxScale;      // 2 = este plano se calcula a media resolución
uniform vec3 uDetail;        // detalle procedural: (intensidad, escala 1/m, anisotropía)
uniform vec3 uInflate;       // normales infladas desde la silueta: (radio px, intensidad, envoltura)

vec2 planeUV(vec3 hit){
  vec2 w = uAxis==0 ? hit.zy : (uAxis==1 ? hit.xz : hit.xy);
  return vec2((w.x-uExt.x)/(uExt.y-uExt.x), (w.y-uExt.z)/(uExt.w-uExt.z));
}
bool hitPlane(vec2 px, vec3 cam, out vec3 hit, out float dist){
  vec3 d = rayDir(px);
  float denom = d[uAxis];
  if(abs(denom) < 1e-6) return false;
  float s = (uValue - cam[uAxis]) / denom;
  if(s <= 0.0) return false;
  hit = cam + d*s; dist = s*length(d);
  return true;
}
vec2 g_dx, g_dy;   // gradientes de uv por píxel de pantalla (anisotropía)
bool uvAt(vec2 px, out vec2 uv){
  if(uScreenSpace==1){ uv = vec2(px.x, px.y)/uRes; return true; }
  vec3 hit; float dist;
  if(!hitPlane(px, uCam, hit, dist)) return false;
  uv = planeUV(hit);
  return !(uv.x<0.0||uv.x>1.0||uv.y<0.0||uv.y>1.0);
}
vec4 sampleAt(vec2 px, float k){
  vec2 uv; if(!uvAt(px, uv)) return vec4(0);
  return textureGrad(uTex, uv, g_dx*k, g_dy*k);
}
vec4 sampleEmit(vec2 px, float k){
  vec2 uv; if(!uvAt(px, uv)) return vec4(0);
  return textureGrad(uEmit, uv, g_dx*k, g_dy*k);
}
// luz solar que atraviesa ventanas: proyecta el punto hacia el sol hasta el muro de las ventanas
float windowLight(vec3 P){
  if(uNW==0) return 1.0;
  float denom = uSunDir[uWinAxis];
  if(abs(denom) < 1e-4) return 0.0;
  float s = (uWinValue - P[uWinAxis]) / denom;
  if(s < 0.0) return 0.0;
  vec3 q = P + uSunDir*s;
  vec2 w = uWinAxis==0 ? q.zy : (uWinAxis==1 ? q.xz : q.xy);
  float m = 0.0;
  for(int i=0;i<6;i++){ if(i>=uNW) break; vec4 r = uWin[i];
    // borde suave proporcional a la distancia (penumbra del sol, ~0.5°)
    float pen = 0.0047*s + 0.01;
    float a = smoothstep(r.x-pen, r.x+pen, w.x)*smoothstep(r.y+pen, r.y-pen, w.x)*smoothstep(r.z-pen, r.z+pen, w.y)*smoothstep(r.w+pen, r.w-pen, w.y);
    // parteluces / persianas
    if(uBlinds.x > 0.0){ float f = fract((w.y - r.z) * uBlinds.x); a *= mix(1.0, smoothstep(uBlinds.y-0.08, uBlinds.y+0.08, f), uBlinds.z); }
    if(uBlinds.w > 0.0){ float c = abs(fract((w.x - r.x)/(r.y-r.x)*uBlinds.w + 0.5) - 0.5)*(r.y-r.x)/uBlinds.w; a *= smoothstep(0.02, 0.035 + pen*0.5, c); }
    m = max(m, a);
  }
  return m;
}
float noise2(vec2 p){ vec2 i = floor(p), f = fract(p); f = f*f*(3.0-2.0*f);
  return mix(mix(hash12(i), hash12(i+vec2(1,0)), f.x), mix(hash12(i+vec2(0,1)), hash12(i+vec2(1,1)), f.x), f.y); }
float canopyShadow(vec3 P){
  if(uCanopy.z <= 0.0) return 1.0;
  float s = (uCanopy.w - P.y) / max(uSunDir.y, 0.05);
  if(s < 0.0) return 1.0;
  vec3 q = P + uSunDir*s;
  vec2 d = (q.xz - uCanopy.xy) / uCanopy.z;
  float inside = smoothstep(1.05, 0.75, length(d*vec2(1.0, 1.4)));
  vec2 wind = vec2(sin(uTime*0.9)*0.08, cos(uTime*0.7)*0.05);
  float n = noise2(q.xz*3.1 + wind*4.0)*0.6 + noise2(q.xz*7.3 - wind*6.0)*0.4;
  float leaves = smoothstep(0.35, 0.62, n);
  return 1.0 - inside*leaves*0.92;
}
vec3 lighting(vec3 P, vec3 N, vec2 px){
  if(uSelfLit > 0.5) return vec3(1.0);
  // cielo: hemisferio (arriba/abajo)
  float up = mix(N.y*0.5+0.5, clamp(P.y/2.2, 0.0, 1.0)*0.5+0.5, uFlat);
  vec3 L = mix(uAmbBot, uAmbTop, up);
  // sol
  if(uSunOn > 0.0){
    float w = uInflate.z;
    float ndl = mix(max((dot(N, uSunDir) + w)/(1.0 + w), 0.0), 0.75, uFlat);
    float vis = windowLight(P) * canopyShadow(P);
    // penumbra: la sombra se ablanda con un nivel de mip mayor
    if(uShadowOn > 0.5) vis *= 1.0 - textureLod(uShadow, px/uRes, uShadowSoft).r;
    L += uSunCol * ndl * vis * uSunOn;
  }
  // luces puntuales: inverso del cuadrado de la distancia, suman
  for(int i=0;i<6;i++){ if(i>=uNL) break;
    vec3 d = uLPos[i].xyz - P; float r2 = dot(d,d);
    float w = uInflate.z;
    float ndl = mix(max((dot(N, normalize(d)) + w)/(1.0 + w), 0.0), 0.5+0.5*clamp(-d.z/sqrt(r2)+0.3,0.0,1.0), uFlat);
    L += uLCol[i].rgb * ndl / (r2 + uLPos[i].w*uLPos[i].w);
  }
  return L;
}
void main(){
  vec2 px = gl_FragCoord.xy * uPxScale;
  vec3 hit; float dist;
  if(uScreenSpace==1){ dist = uValue - uCam.z; hit = uCam + rayDir(px)*dist; }
  else if(!hitPlane(px, uCam, hit, dist)) discard;
  // círculo de confusión (lente delgada) y desplazamiento por movimiento de cámara
  float coc = uCocK * abs(1.0 - uFocus/dist);
  // desplazamiento en pantalla durante la obturación: traslación lateral + avance (dolly)
  vec2 mv = (uVel + (px - 0.5*uRes - uShift)*uCamVel.z) / dist;
  float rad = 0.5*coc;
  float spread = max(rad, 0.5*length(mv));
  int taps = spread < 0.6 ? 1 : int(clamp(6.0 + spread*(uPxScale > 1.5 ? 2.4 : 1.1), 8.0, float(uMaxTaps)));
  // gradientes de uv en el centro (diferencias finitas de 1 px)
  vec2 uv0, uvx, uvy;
  if(uvAt(px, uv0) || true){
    uvAt(px, uv0); uvAt(px + vec2(1,0), uvx); uvAt(px + vec2(0,1), uvy);
    g_dx = uvx - uv0; g_dy = uvy - uv0;
    if(uScreenSpace==1){ g_dx = vec2(1.0/uRes.x, 0); g_dy = vec2(0, 1.0/uRes.y); }
    if(abs(g_dx.x)+abs(g_dx.y) > 0.5 || abs(g_dy.x)+abs(g_dy.y) > 0.5){ g_dx = vec2(1e-4,0); g_dy = vec2(0,1e-4); }
  }
  // salida temprana: fuera de la extensión del plano o en zona totalmente transparente (con margen = desenfoque)
  {
    vec2 uvc; uvAt(px, uvc);
    float pxu = max(length(g_dx), length(g_dy));
    float margin = (spread + 3.0) * pxu;
    if(uScreenSpace == 0 && (uvc.x < -margin || uvc.x > 1.0 + margin || uvc.y < -margin || uvc.y > 1.0 + margin)) discard;
    float texPerPx = pxu * max(uTexSize.x, uTexSize.y);
    float lodc = log2(max((spread * 2.0 + 10.0 + uInflate.x * 2.0) * texPerPx, 1.0)) + 1.0;
    vec2 uvcl = clamp(uvc, 0.0, 1.0);
    float cov = textureLod(uTex, uvcl, lodc).a + (uHasEmit > 0.5 ? textureLod(uEmit, uvcl, lodc - 1.0).a : 0.0);
    if(cov < 1e-4) discard;
  }
  // al desenfocar, el filtro se ensancha con el radio de cada muestra
  float k = taps>1 ? max(1.0, spread*2.6/sqrt(float(taps))) : 1.0;
  vec4 acc = vec4(0); vec4 accE = vec4(0);
  float jit = hash12(floor(px*0.5) + fract(uTime)*91.0)*0.8;  // rotación casi fija: sin ruido de alta frecuencia
  for(int i=0;i<64;i++){ if(i>=taps) break;
    float fi = float(i)+0.5;
    float r = taps>1 ? sqrt(fi/float(taps))*rad : 0.0;
    float a = fi*2.39996323 + jit;
    vec2 o = vec2(cos(a), sin(a))*r + (taps>1 ? mv*(fract(fi*0.618034 + jit*0.159)-0.5) : vec2(0));
    acc += sampleAt(px+o, k);
    if(uHasEmit>0.5) accE += sampleEmit(px+o, k);
  }
  acc /= float(taps); accE /= float(taps);
  if(acc.a < 0.002 && accE.a < 0.002 && length(accE.rgb) < 0.002) discard;
  vec3 N = vec3(0); N[uAxis] = -sign(rayDir(px)[uAxis]); if(uAxis==2) N = vec3(0,0,-1);
  if(uInflate.x > 0.0 && acc.a > 0.01){
    float r = uInflate.x; float kb = max(1.0, r*0.8);
    float axp = sampleAt(px + vec2(r,0), kb).a, axm = sampleAt(px - vec2(r,0), kb).a;
    float ayp = sampleAt(px + vec2(0,r), kb).a, aym = sampleAt(px - vec2(0,r), kb).a;
    vec2 gr = vec2(axp - axm, ayp - aym);
    N = normalize(vec3(-gr*uInflate.y, -1.0));
  }
  if(uDetail.x > 0.0){
    vec2 w = uAxis==0 ? hit.zy : (uAxis==1 ? hit.xz : hit.xy);
    w *= uDetail.y; w.y *= uDetail.z;
    float fade = clamp(1.0 - dist/40.0, 0.0, 1.0);
    float n = noise2(w)*0.5 + noise2(w*2.7+7.1)*0.3 + noise2(w*7.3+3.3)*0.2;
    acc.rgb *= 1.0 + uDetail.x*fade*(n-0.5)*2.0;
  }
  // difuso lambertiano: radiancia = albedo/pi * irradiancia total (las luces se suman)
  vec3 lit = acc.rgb * lighting(hit, N, px) * (uSelfLit > 0.5 ? 1.0 : 0.31831);
  if(uInflate.x > 0.0){ // retroiluminación translúcida en los bordes (hojas, pelo, tela fina)
    float back = max(dot(-N, uSunDir), 0.0) * (1.0 - abs(N.z));
    lit += acc.rgb * uSunCol * back * back * uSunOn * 0.25;
  }
  // luz de contorno: borde iluminado del lado de la fuente (diferencia de cobertura)
  if(uRim > 0.0){
    float aHere = acc.a;
    float aOut = sampleAt(px + uRimDir, k).a;
    float rim = clamp(aHere - aOut, 0.0, 1.0);
    lit += uRimCol * rim * uRim;
  }
  lit += accE.rgb * uEmitGain;
  // perspectiva atmosférica: extinción + dispersión hacia el ojo
  vec3 T = exp(-uSigma * dist);
  vec3 v = normalize(rayDir(px));
  float mu = dot(v, uSunDir); float g = 0.7;
  float hg = (1.0-g*g)/(4.0*3.14159*pow(1.0+g*g-2.0*g*mu, 1.5));
  vec3 inscat = (uFogCol + uFogSun*hg) * (1.0 - T);
  float alpha = clamp(max(acc.a, accE.a), 0.0, 1.0);
  frag = vec4(lit*T + inscat*alpha, alpha);
}
"""

# ---------------------------------------------------------------- partículas
VS_PART = """#version 430
in vec4 in_p;     // x, y, z, semilla
in vec4 in_v;     // velocidad deriva (m/s) + brillo
uniform vec3 uCam; uniform float uF; uniform vec2 uRes; uniform vec2 uShift;
uniform float uTime; uniform float uCocK; uniform float uFocus;
uniform vec3 uBoxMin, uBoxMax;
uniform float uTurb;
uniform vec3 uBeamO, uBeamD; uniform float uBeamR; uniform float uBeamOn;  // haz de luz que hace visible el polvo
uniform vec3 uCol; uniform float uGain; uniform float uSizeM; uniform float uMaxPt;
uniform vec3 uSigma; uniform vec3 uFogCol;
uniform vec3 uSunDirP; uniform vec2 uPhase;   // (g, activado): dispersión Mie hacia el ojo
uniform int uWinAxis; uniform float uWinValue; uniform int uNW; uniform vec4 uWin[6]; uniform vec4 uBlinds;
uniform float uWinMode;  // 1 = el polvo solo es visible dentro de los haces que entran por las ventanas
float winLightP(vec3 P){
  float denom = uSunDirP[uWinAxis];
  if(abs(denom) < 1e-4) return 0.0;
  float s = (uWinValue - P[uWinAxis]) / denom;
  if(s < 0.0) return 0.0;
  vec3 q = P + uSunDirP*s;
  vec2 w = uWinAxis==0 ? q.zy : (uWinAxis==1 ? q.xz : q.xy);
  float m = 0.0;
  for(int i=0;i<6;i++){ if(i>=uNW) break; vec4 r = uWin[i]; float pen = 0.0047*s + 0.01;
    float a = smoothstep(r.x-pen, r.x+pen, w.x)*smoothstep(r.y+pen, r.y-pen, w.x)*smoothstep(r.z-pen, r.z+pen, w.y)*smoothstep(r.w+pen, r.w-pen, w.y);
    if(uBlinds.x > 0.0){ float f = fract((w.y - r.z) * uBlinds.x); a *= mix(1.0, smoothstep(uBlinds.y-0.08, uBlinds.y+0.08, f), uBlinds.z); }
    m = max(m, a); }
  return m;
}
out vec3 vCol; out float vSize;
void main(){
  vec3 size = uBoxMax - uBoxMin;
  float s = in_p.w;
  vec3 p = in_p.xyz + in_v.xyz*uTime;
  // turbulencia suave (campo de velocidades por senos desfasados)
  p += uTurb*vec3(sin(uTime*0.37 + s*6.1 + p.y*1.7), sin(uTime*0.29 + s*4.3 + p.x*1.3)*0.6, sin(uTime*0.31 + s*2.9 + p.y*1.1));
  p = uBoxMin + mod(p - uBoxMin, size);
  vec3 d = p - uCam;
  if(d.z < 0.15){ gl_Position = vec4(2,2,2,1); gl_PointSize = 1.0; vCol = vec3(0); vSize = 1.0; return; }
  vec2 sp = d.xy/d.z*uF + 0.5*uRes + uShift;
  gl_Position = vec4(sp/uRes*2.0-1.0, 0.0, 1.0);
  float coc = uCocK*abs(1.0 - uFocus/d.z);
  float core = max(uSizeM*uF/d.z, 1.0);
  float sz = max(core, coc);
  gl_PointSize = min(sz, uMaxPt);
  vSize = gl_PointSize;
  float beam = 1.0;
  if(uBeamOn > 0.5){ vec3 w = p - uBeamO; float along = dot(w, uBeamD); vec3 perp = w - uBeamD*along; beam = smoothstep(uBeamR, uBeamR*0.4, length(perp)) * step(0.0, along); }
  if(uWinMode > 0.5) beam *= winLightP(p);
  float twinkle = 0.6 + 0.4*sin(uTime*(1.0+s*3.0) + s*40.0);
  // energía conservada: el disco desenfocado reparte la misma luz en más área
  float energy = (core*core)/(gl_PointSize*gl_PointSize);
  vec3 T = exp(-uSigma*length(d));
  vCol = uCol*uGain*in_v.w*beam*twinkle*energy*T;
  if(uPhase.y > 0.5){
    float mu = dot(normalize(d), uSunDirP); float g = uPhase.x;
    float hg = (1.0-g*g)/pow(1.0+g*g-2.0*g*mu, 1.5);
    vCol *= hg*0.25;
  }
  // descarta motas sin aportación visible (ahorra relleno de píxeles)
  if(max(vCol.r, max(vCol.g, vCol.b)) < 0.0015){ gl_Position = vec4(2,2,2,1); gl_PointSize = 1.0; }
}
"""
FS_PART = """#version 430
in vec3 vCol; in float vSize; out vec4 frag;
void main(){
  vec2 q = gl_PointCoord*2.0-1.0; float r = length(q);
  if(r > 1.0) discard;
  // bokeh: disco con borde ligeramente más brillante cuando está desenfocado
  float disc = vSize > 3.0 ? (smoothstep(1.0, 0.85, r)*(0.85 + 0.25*smoothstep(0.5, 0.95, r))) : exp(-r*r*3.0);
  frag = vec4(vCol*disc, 0.0);
}
"""

# lluvia: segmentos con longitud = velocidad x tiempo de obturación (desenfoque de movimiento físico)
VS_RAIN = """#version 430
in vec4 in_p; in float in_end;
uniform vec3 uCam; uniform float uF; uniform vec2 uRes; uniform vec2 uShift; uniform float uTime;
uniform vec3 uBoxMin, uBoxMax; uniform vec3 uVelR; uniform float uShutter; uniform vec3 uCol;
uniform float uCocK; uniform float uFocus;
out vec3 vCol;
void main(){
  vec3 size = uBoxMax-uBoxMin;
  vec3 p = in_p.xyz + uVelR*(uTime + in_p.w*7.0);
  p = uBoxMin + mod(p-uBoxMin, size);
  p += uVelR*uShutter*in_end;
  vec3 d = p-uCam;
  vec2 sp = d.xy/d.z*uF + 0.5*uRes + uShift;
  gl_Position = vec4(sp/uRes*2.0-1.0, 0.0, 1.0);
  // una gota desenfocada reparte su luz en un disco mayor: se atenúa en proporción
  float coc = uCocK*abs(1.0 - uFocus/max(d.z, 0.1));
  vCol = uCol * (0.5 + in_p.w) / max(d.z, 1.0) / (1.0 + coc*0.6);
}
"""
FS_RAIN = """#version 430
in vec3 vCol; out vec4 frag; void main(){ frag = vec4(vCol, 0.0); }
"""

# ---------------------------------------------------------------- post: rayos volumétricos (dispersión en espacio de pantalla)
FS_GODRAYS = """#version 430
out vec4 frag;
uniform sampler2D uSrc; uniform vec2 uLight; uniform vec2 uSize; uniform float uThresh;
uniform float uDecay; uniform float uDensity; uniform float uWeight; uniform float uTime;
float hash12(vec2 p){ vec3 p3 = fract(vec3(p.xyx) * .1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }
void main(){
  vec2 uv = gl_FragCoord.xy/uSize;
  vec2 delta = (uv - uLight) * uDensity / 72.0;
  vec3 acc = vec3(0); float w = 1.0;
  vec2 p = uv - delta*hash12(gl_FragCoord.xy + uTime);
  for(int i=0;i<72;i++){
    vec3 c = textureLod(uSrc, p, 0.0).rgb;
    float l = dot(c, vec3(0.2126,0.7152,0.0722));
    acc += c * max(l - uThresh, 0.0)/max(l, 1e-4) * w;
    w *= uDecay; p -= delta;
  }
  frag = vec4(acc*uWeight/72.0, 1.0);
}
"""

# ---------------------------------------------------------------- post: bloom (Jimenez 2014)
FS_DOWN = """#version 430
out vec4 frag; uniform sampler2D uSrc; uniform vec2 uTexel; uniform int uFirst; uniform float uThresh;
vec3 s(vec2 uv){ return textureLod(uSrc, uv, 0.0).rgb; }
void main(){
  vec2 uv = gl_FragCoord.xy * 2.0 * uTexel;   // destino a la mitad de resolución
  vec2 t = uTexel;
  vec3 a = s(uv+t*vec2(-2,2)), b = s(uv+t*vec2(0,2)), c = s(uv+t*vec2(2,2));
  vec3 d = s(uv+t*vec2(-2,0)), e = s(uv), f = s(uv+t*vec2(2,0));
  vec3 g = s(uv+t*vec2(-2,-2)), h = s(uv+t*vec2(0,-2)), i = s(uv+t*vec2(2,-2));
  vec3 j = s(uv+t*vec2(-1,1)), k = s(uv+t*vec2(1,1)), l = s(uv+t*vec2(-1,-1)), m = s(uv+t*vec2(1,-1));
  vec3 col = e*0.125 + (a+c+g+i)*0.03125 + (b+d+f+h)*0.0625 + (j+k+l+m)*0.125;
  if(uFirst==1){ float br = max(col.r, max(col.g, col.b)); float soft = clamp(br - uThresh + 0.5, 0.0, 1.0); soft = soft*soft*0.5;
    float contrib = max(soft, br - uThresh)/max(br, 1e-4); col *= contrib; col = min(col, vec3(200.0)); }
  frag = vec4(col, 1.0);
}
"""
FS_UP = """#version 430
out vec4 frag; uniform sampler2D uSrc; uniform sampler2D uBase; uniform vec2 uTexel; uniform float uRadius; uniform vec2 uDst;
void main(){
  vec2 uv = gl_FragCoord.xy * uTexel * 0.5;  // fuente a la mitad de resolución
  vec2 t = uTexel*0.5*uRadius;
  vec3 c = textureLod(uSrc, uv, 0.0).rgb*4.0;
  c += (textureLod(uSrc, uv+vec2(-t.x,0),0.0).rgb + textureLod(uSrc, uv+vec2(t.x,0),0.0).rgb + textureLod(uSrc, uv+vec2(0,-t.y),0.0).rgb + textureLod(uSrc, uv+vec2(0,t.y),0.0).rgb)*2.0;
  c += textureLod(uSrc, uv+vec2(-t.x,-t.y),0.0).rgb + textureLod(uSrc, uv+vec2(t.x,-t.y),0.0).rgb + textureLod(uSrc, uv+vec2(-t.x,t.y),0.0).rgb + textureLod(uSrc, uv+vec2(t.x,t.y),0.0).rgb;
  frag = vec4(c/16.0 + textureLod(uBase, gl_FragCoord.xy/uDst, 0.0).rgb, 1.0);
}
"""

# ---------------------------------------------------------------- final: lente, ACES, gradación, grano
FS_FINAL = """#version 430
out vec4 frag;
uniform sampler2D uHDR, uBloom, uRays, uOverlay;
uniform vec2 uRes; uniform float uExposure; uniform float uBloomK; uniform float uRaysK;
uniform vec3 uWB;          // ganancias de balance de blancos (von Kries, ya calculadas)
uniform float uSat; uniform float uContrast; uniform vec3 uLift; uniform vec3 uGain;
uniform vec3 uShadowTint, uHighTint;
uniform float uVignette; uniform float uCA; uniform float uGrain; uniform float uTime; uniform float uFade;
uniform float uFlash;  // destello de memoria (escena del recuerdo)
float hash12(vec2 p){ vec3 p3 = fract(vec3(p.xyx) * .1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }
// ACES ajustado (Stephen Hill): sRGB -> AP1 -> RRT+ODT -> sRGB
const mat3 ACESIn = mat3(0.59719, 0.07600, 0.02840, 0.35458, 0.90834, 0.13383, 0.04823, 0.01566, 0.83777);
const mat3 ACESOut = mat3(1.60475, -0.10208, -0.00327, -0.53108, 1.10813, -0.07276, -0.07367, -0.00605, 1.07602);
vec3 RRTODT(vec3 v){ vec3 a = v*(v+0.0245786)-0.000090537; vec3 b = v*(0.983729*v+0.4329510)+0.238081; return a/b; }
vec3 aces(vec3 c){ c = ACESIn*c; c = RRTODT(c); c = ACESOut*c; return clamp(c, 0.0, 1.0); }
vec3 toSRGB(vec3 c){ return mix(c*12.92, 1.055*pow(c, vec3(1.0/2.4))-0.055, step(0.0031308, c)); }
float luma(vec3 c){ return dot(c, vec3(0.2126,0.7152,0.0722)); }
void main(){
  vec2 uv = gl_FragCoord.xy/uRes;
  vec2 cc = uv - 0.5;
  float r2 = dot(cc*vec2(uRes.x/uRes.y,1.0), cc*vec2(uRes.x/uRes.y,1.0));
  // aberración cromática lateral (crece con el radio)
  vec2 ca = cc * uCA * r2;
  vec3 hdr;
  hdr.r = texture(uHDR, uv - ca).r; hdr.g = texture(uHDR, uv).g; hdr.b = texture(uHDR, uv + ca).b;
  // la luz dispersada por la lente se suma (energía conservada con mezcla lineal)
  vec3 bloom = texture(uBloom, uv).rgb;
  hdr = mix(hdr, bloom, uBloomK) + texture(uRays, uv).rgb*uRaysK;
  // viñeteado natural cos^4
  float cosT = 1.0/sqrt(1.0 + r2*uVignette);
  hdr *= pow(cosT, 4.0);
  hdr *= uWB * uExposure;
  hdr += uFlash;
  vec3 c = aces(hdr);
  // gradación (en espacio de visualización)
  float l = luma(c);
  c = mix(vec3(l), c, uSat);
  c = (c - 0.5)*uContrast + 0.5;
  c = c*uGain + uLift*(1.0-c);
  c += uShadowTint*(1.0-smoothstep(0.0, 0.45, l)) + uHighTint*smoothstep(0.55, 1.0, l);
  c = clamp(c, 0.0, 1.0);
  vec3 s = toSRGB(c);
  // grano de película dependiente de la luminancia + tramado
  float n = (hash12(gl_FragCoord.xy + fract(uTime*7.13)*1000.0) + hash12(gl_FragCoord.xy*1.37 + fract(uTime*3.7)*500.0) - 1.0);
  s += n*uGrain*(0.6 - 0.5*l);
  s += (hash12(gl_FragCoord.xy*0.71 + uTime) - 0.5)/255.0;
  s *= uFade;
  vec4 ov = texture(uOverlay, vec2(uv.x, 1.0-uv.y));
  s = s*(1.0-ov.a) + ov.bgr;   // superposición (Cairo BGRA premultiplicado, sRGB)
  frag = vec4(clamp(s, 0.0, 1.0), 1.0);
}
"""

# Cairo (BGRA premultiplicado, sRGB, origen arriba) -> lineal premultiplicado (origen abajo)
FS_LINEARIZE = """#version 430
out vec4 frag; uniform sampler2D uSrc; uniform vec2 uSize; uniform float uWeight; uniform float uFlip;
vec3 dec(vec3 c){ return mix(c/12.92, pow((c+0.055)/1.055, vec3(2.4)), step(0.04045, c)); }
void main(){
  vec2 uv = gl_FragCoord.xy/uSize; if(uFlip > 0.5) uv.y = 1.0-uv.y;
  vec4 c = textureLod(uSrc, uv, 0.0);
  float a = c.a; vec3 st = a > 0.0 ? c.bgr/a : vec3(0);
  frag = vec4(dec(clamp(st,0.0,1.0))*a, a)*uWeight;
}
"""

FS_UPCOMP = """#version 430
out vec4 frag; uniform sampler2D uSrc; uniform vec2 uSize;
void main(){ frag = texture(uSrc, gl_FragCoord.xy/uSize); }
"""

# luz volumétrica: integración a lo largo del rayo (ventanas + luces puntuales), por rodajas de profundidad
FS_VOLUME = """#version 430
out vec4 frag;
""" + COMMON + """
uniform vec3 uSunDir; uniform vec3 uSunCol; uniform float uSigmaS; uniform float uSigmaT; uniform float uG;
uniform int uWinAxis; uniform float uWinValue; uniform int uNW; uniform vec4 uWin[6]; uniform vec4 uBlinds;
uniform vec3 uBoxMin, uBoxMax; uniform vec2 uZRange; uniform float uTime; uniform int uSteps;
uniform int uNL; uniform vec4 uLPos[6]; uniform vec4 uLCol[6]; uniform float uLightK;
uniform float uNoise;
float noise3(vec3 p){ vec3 i = floor(p), f = fract(p); f = f*f*(3.0-2.0*f);
  float n = dot(i, vec3(1.0, 57.0, 113.0));
  vec4 a = fract(sin(vec4(n, n+1.0, n+57.0, n+58.0))*43758.5453);
  vec4 b = fract(sin(vec4(n+113.0, n+114.0, n+170.0, n+171.0))*43758.5453);
  vec4 m = mix(a, b, f.z); vec2 m2 = mix(m.xy, m.zw, f.y); return mix(m2.x, m2.y, f.x); }
float winLight(vec3 P){
  float denom = uSunDir[uWinAxis];
  if(abs(denom) < 1e-4) return 0.0;
  float s = (uWinValue - P[uWinAxis]) / denom;
  if(s < 0.0) return 0.0;
  vec3 q = P + uSunDir*s;
  vec2 w = uWinAxis==0 ? q.zy : (uWinAxis==1 ? q.xz : q.xy);
  float m = 0.0;
  for(int i=0;i<6;i++){ if(i>=uNW) break; vec4 r = uWin[i]; float pen = 0.0047*s + 0.015;
    float a = smoothstep(r.x-pen, r.x+pen, w.x)*smoothstep(r.y+pen, r.y-pen, w.x)*smoothstep(r.z-pen, r.z+pen, w.y)*smoothstep(r.w+pen, r.w-pen, w.y);
    if(uBlinds.x > 0.0){ float f = fract((w.y - r.z) * uBlinds.x); a *= mix(1.0, smoothstep(uBlinds.y-0.08, uBlinds.y+0.08, f), uBlinds.z); }
    if(uBlinds.w > 0.0){ float c = abs(fract((w.x - r.x)/(r.y-r.x)*uBlinds.w + 0.5) - 0.5)*(r.y-r.x)/uBlinds.w; a *= smoothstep(0.02, 0.035 + pen*0.5, c); }
    m = max(m, a); }
  return m;
}
void main(){
  vec2 px = gl_FragCoord.xy * 2.0;   // se calcula a media resolución
  vec3 d = rayDir(px); float dl = length(d); vec3 v = d/dl;
  // tramo del rayo dentro de la caja y de la rodaja [z0, z1]
  vec3 inv = 1.0/v;
  vec3 t0 = (uBoxMin - uCam)*inv, t1 = (uBoxMax - uCam)*inv;
  vec3 tmin = min(t0, t1), tmax = max(t0, t1);
  float a = max(max(tmin.x, tmin.y), max(tmin.z, 0.0));
  float b = min(min(tmax.x, tmax.y), tmax.z);
  float za = (uZRange.x - uCam.z)/v.z, zb = (uZRange.y - uCam.z)/v.z;
  a = max(a, za); b = min(b, zb);
  vec3 col = vec3(0);
  if(b > a){
    float ds = (b-a)/float(uSteps);
    float j = hash12(gl_FragCoord.xy + fract(uTime*13.1)*77.0);
    float mu = dot(v, uSunDir);
    float hg = (1.0-uG*uG)/(4.0*3.14159*pow(1.0+uG*uG-2.0*uG*mu, 1.5));
    float acc = 0.0;
    for(int i=0;i<64;i++){ if(i>=uSteps) break;
      float s = a + (float(i)+j)*ds;
      vec3 P = uCam + v*s;
      float dens = 1.0 + uNoise*(noise3(P*1.7 + vec3(uTime*0.05, uTime*0.02, 0.0)) - 0.5)*2.0;
      acc += winLight(P) * exp(-uSigmaT*s) * dens * ds;
    }
    col += uSunCol * hg * uSigmaS * acc;
    // resplandor de luces puntuales: integral analítica de I/r^2 a lo largo del tramo
    for(int i=0;i<6;i++){ if(i>=uNL) break;
      vec3 L = uLPos[i].xyz - uCam; float s0 = dot(L, v); float h = max(length(L - v*s0), 0.02);
      float I = (atan((b - s0)/h) - atan((a - s0)/h))/h;
      col += uLCol[i].rgb * I * uSigmaS * uLightK / (4.0*3.14159);
    }
  }
  frag = vec4(col, 0.0);
}
"""

FS_COPY = """#version 430
out vec4 frag; uniform sampler2D uSrc; uniform vec2 uSize;
void main(){ frag = textureLod(uSrc, gl_FragCoord.xy/uSize, 0.0); }
"""
