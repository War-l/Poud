"""Ensambla la descripción de un fotograma para Engine.render()."""
import numpy as np

from .director import draw_actors, draw_shadows

SHUTTER = 1 / 48   # obturador de 180° a 24 fps


def build(eng, aset, actors, cam, t, overrides=None, subframes=(-0.33, 0.0, 0.33), shadows=True,
          extra_items=(), env_mod=None, post_mod=None):
    W, H = eng.W, eng.H
    cv = cam(t)
    a, b = cam(t - SHUTTER / 2), cam(t + SHUTTER / 2)
    cam_vel = tuple(np.array(b["cam"]) - np.array(a["cam"]))
    if np.linalg.norm(cam_vel) > 0.5:  # corte de plano dentro del obturador: sin estela
        cam_vel = (0.0, 0.0, 0.0)
    env = aset.env(t)
    if env_mod:
        env = env_mod(env, t)
    # ¿se mueve algún actor? solo entonces se submuestrea el obturador
    moving = False
    for ac in actors:
        if ac.visible(t):
            p0, p1 = ac.at(t - SHUTTER / 2), ac.at(t + SHUTTER / 2)
            if getattr(ac, "moving", False) or abs(p0[0] - p1[0]) + abs(p0[2] - p1[2]) > 0.002 or \
                    p0[4].get("walk") is not None:
                moving = True
            else:
                # gestos rápidos (brazos, cabeza) también piden desenfoque de movimiento
                for k, v in p1[4].items():
                    if k in ("mouth", "blink", "breath", "hair_lag", "hem_lag"):
                        continue
                    v0 = p0[4].get(k)
                    if isinstance(v, (int, float)) and isinstance(v0, (int, float)) and abs(v - v0) > 0.6:
                        moving = True
                    elif isinstance(v, tuple) and isinstance(v0, tuple) and \
                            sum(abs(a - b) for a, b in zip(v, v0)) > 1.0:
                        moving = True
    sfs = subframes if moving else (0.0,)
    light = aset.light_screen()
    layers, depths = draw_actors(actors, t, cam, W, H, light, subframes=sfs, shutter=SHUTTER)
    items = []
    for i, (g, frames) in enumerate(sorted(layers.items())):
        tex = eng.char_layer(i, frames)
        ov = dict(rim=getattr(aset, "char_rim", 1.0))
        items.append((depths[g], ("chars", tex, depths[g], ov)))
    shadow = None
    sun = env.get("sun_dir")
    if shadows and sun is not None and getattr(aset, "cast_shadows", True) and sun[1] > 0.02:
        shadow = draw_shadows(actors, t, cv, W, H, sun, strength=getattr(aset, "shadow_strength", 0.85))
    plist = aset.compose(items, extra_items)
    # los planos de suelo reciben las sombras de los personajes
    plist2 = []
    for it in plist:
        if it[0] == "plane" and it[1].axis == 1 and it[1].value < 0.05:
            ov = dict(it[2]) if len(it) > 2 else {}
            ov["receive_shadow"] = True
            plist2.append(("plane", it[1], ov))
        else:
            plist2.append(it)
    post = dict(aset.post(t))
    if post_mod:
        post = post_mod(post, t)
    rays = post.get("rays")
    src = getattr(aset, "ray_source", None)
    if rays is not None:
        rays = dict(rays)
        if "pos" not in rays:
            d = np.array(src(t) if src else (sun if sun is not None else (0, 1, 1)), dtype=float)
            if callable(src):
                # punto del mundo
                p = np.array(src(t)) - np.array(cv["cam"])
            else:
                p = d
            z = max(p[2], 1e-3)
            sx = W / 2 + cv["shift"][0] + p[0] / z * cv["f"]
            sy = H / 2 + cv["shift"][1] + p[1] / z * cv["f"]
            rays["pos"] = (sx / W, sy / H)
        post["rays"] = rays
    sky = aset.sky(t) if hasattr(aset, "sky") else None
    f = dict(t=t, cam=cv["cam"], f=cv["f"], shift=cv["shift"], focus=cv["focus"], coc_k=cv["coc_k"],
             cam_vel=cam_vel, env=env, sky=sky, items=plist2, shadow=shadow, post=post, shutter=SHUTTER)
    if overrides:
        f.update(overrides)
    return f
