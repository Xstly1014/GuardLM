"""One-off: convert real loss series (m0-v3, 46 points) into SVG polyline coords.

Chart area: x 50-740 (steps 0-230), y 20-260 (loss 5-0). Output -> paste into HTML.
"""
series = [(5, 4.9125), (10, 4.7887), (15, 4.586), (20, 3.2108), (25, 2.3776),
          (30, 1.9219), (35, 1.6452), (40, 1.1766), (45, 1.3189), (50, 0.975),
          (55, 0.9454), (60, 0.7886), (65, 0.9391), (70, 0.7451), (75, 0.9696),
          (80, 1.0858), (85, 0.8163), (90, 0.5846), (95, 0.7727), (100, 0.7578),
          (105, 0.547), (110, 0.6332), (115, 0.7113), (120, 0.5504), (125, 0.6206),
          (130, 0.8615), (135, 0.4014), (140, 0.5961), (145, 0.4286), (150, 0.4295),
          (155, 0.3391), (160, 0.4729), (165, 0.5433), (170, 0.5021), (175, 0.4253),
          (180, 0.3604), (185, 0.2772), (190, 0.3147), (195, 0.2466), (200, 0.4226),
          (205, 0.3593), (210, 0.4438), (215, 0.2349), (220, 0.4308), (225, 0.4256),
          (230, 0.3257)]

X0, X1, Y0, Y1 = 50.0, 740.0, 260.0, 20.0  # px bounds; y0=bottom, y1=top
S_MAX, L_MAX = 230.0, 5.0

pts = []
for step, loss in series:
    x = X0 + (step / S_MAX) * (X1 - X0)
    y = Y0 - (loss / L_MAX) * (Y0 - Y1)
    pts.append(f"{x:.1f},{y:.1f}")

print(" ".join(pts))
print()
# also smoothed (EMA a=0.6) for the smoothing illustration
ema, smooth = series[0][1], []
for _, loss in series:
    ema = 0.6 * ema + 0.4 * loss
    smooth.append(ema)
spts = []
for (step, _), sv in zip(series, smooth):
    x = X0 + (step / S_MAX) * (X1 - X0)
    y = Y0 - (sv / L_MAX) * (Y0 - Y1)
    spts.append(f"{x:.1f},{y:.1f}")
print(" ".join(spts))
