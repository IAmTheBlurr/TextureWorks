# Material field algorithms

These additions leave the six legacy generators and their defaults intact. The
new API is `textureworks.{cupy_ref,ptx}.material_fields`. Arrays are contiguous
float32 CuPy data in [0,1]. Inputs may be odd or non-square but each dimension
must be at least 2. Scalars have shape (H,W); color/normals have shape (H,W,3).
Nonfinite values, unsupported shapes and out-of-range parameters are errors.
Both backends implement the formulas below. Maximum absolute difference is
**1/255** for every output, with stricter analytic assertions in tests.

## Frequency separation

`generate_detail(color, radius=4, boundary="wrap")` takes **linear** RGB.
Radius is an integer support half-width in source texels, 1 through 64. The
separable Gaussian has sigma = radius/3, support [-radius,radius] and normalized
weights. Let L be the filtered color; the output is D = 0.5 + (color-L)/2.
Reconstruct color as L + 2D - 1. No normalization or contrast stretch occurs.
Flat input gives 0.5; a high-pass filter only extracts frequencies already present.
An external detail image may have different dimensions and an independent
physical texture size. It follows the same linearization and filtering rules.

Detail normals use `generate_surface_normal` on the luminance of D, with twice
the requested detail relief depth (because D encodes half the residual).

## Physical normals and signed curvature

`generate_surface_normal(height, texel_size=(1,1), relief_depth=1,
boundary="clamp")` and `generate_curvature(height, texel_size=(1,1),
relief_depth=1, curvature_range=1, boundary="clamp")` take an explicit height.
Texel size is (x,y) in meters, both finite and >= 1e-6. Relief depth is meters,
finite in [0,100]. Height is not renormalized. Physical elevation is
z = relief_depth * (height - 1); the constant reference plane cancels in derivatives.
Image rows increase downwards; tangent +V points upwards. Central differences:

```
hx = (zR-zL)/(2 dx); hy = (zD-zU)/(2 dy)
hxx = (zR-2zC+zL)/dx²; hyy = (zD-2zC+zU)/dy²
hxy = (zDR-zDL-zUR+zUL)/(4 dx dy)
N = normalize(-hx, +hy, 1)
K = -((1+hy²)hxx - 2hx hy hxy + (1+hx²)hyy)
    / (2 (1+hx²+hy²)^(3/2))
C = 0.5 + 0.5 clamp(K/curvature_range, -1, 1)
```

Normal output is N/2+0.5 (OpenGL +Y, tangent-space XYZ). Curvature is the signed
mean curvature of the sampled height graph, in inverse meters before encoding.
`curvature_range` is finite in [1e-6,1e6] inverse meters. Positive/bright means
convex/exposed relief, negative/dark means concave, 0.5 is flat. A planar ramp
has zero interior curvature regardless of gradient magnitude. A paraboloid bump
has positive curvature at its summit; its inverted depression has negative curvature.

All new neighborhood operations support `clamp` (replicate border texels) and
`wrap` (periodic indices). Clamp can introduce curvature at the edge of a ramp;
wrap can introduce a discontinuity at a source seam. Neither creates seamless
imagery. UV relief says nothing about mesh silhouette curvature.

## Deterministic wear

`generate_wear(curvature, edge_amount=0.35, cavity_amount=0.5,
threshold=0.1, variation=0.35, seed=0, edge_mask=None, cavity_mask=None)` returns
RGB = (edge chipping, cavity grime, their maximum). Masks are linear [0,1].
An authored edge/cavity mask replaces that inferred signal before controls.

```
s = 2 curvature - 1
edge = clamp((s-threshold)/(1-threshold), 0, 1)
cavity = clamp((-s-threshold)/(1-threshold), 0, 1)
edge_out = edge_amount * edge * (1-variation + variation*noise)
cavity_out = cavity_amount * cavity * (1-variation + variation*noise)
```

Amounts and variation are [0,1], threshold is [0,0.999], seed is uint32. For
row-major pixel index i, uint32 wraparound hash starts with i XOR seed, followed
by xor-right-shift 16, multiply 0x7feb352d, xor-right-shift 15, multiply
0x846ca68b, xor-right-shift 16. Noise is the low 24 bits divided by 16777215.
Controls never mutate source fields. Zero amounts give exact zero. No world dust,
streaks, mesh curvature or material identity is inferred from albedo.

## Two-material composition

`generate_layer_weight(height_a, height_b, mask, coverage=0.5,
blend_width=0.2, height_bias=0.5)` returns the B weight. All fields share dimensions,
meters per UV, relief depth and reference plane. Parameters are finite [0,1].

```
m = clamp(mask + 2*coverage - 1, 0, 1)
s = m + height_bias * (height_b-height_a) * m*(1-m)
t = smoothstep(0.5-blend_width/2, 0.5+blend_width/2, s)
```

At zero width use t = 1 if s >= 0.5, else 0. Coverage 0/1 and effective mask
0/1 are exact A/B endpoints. Heights are never independently normalized.
Compose height, linear albedo, roughness, metallic and AO with lerp(A,B,t).
Runtime POM evaluates this exact height composition at every march/refinement
sample and shades every channel at the intersection UV, using original UV gradients.

For height-derived normals, differentiate the **composed** height, including
the spatially varying weight. For authored normals, transition their slopes
(-Nx/Nz,-Ny/Nz) and add the weight-gradient term from the height composition;
the runtime profile expresses this as the composed geometric normal plus the
interpolated authored-minus-height slope residual. This reproduces authored
endpoints and avoids using RNM to crossfade material orientations.

Detail uses RNM: normalize(T*dot(T,U) - U*T.z), T = base+(0,0,1),
U = detail*(-1,-1,1). Strength multiplies detail XY before normalization;
zero strength explicitly returns base. This is the shortest-arc rotation from
+Z to the base normal, as derived by
[Barré-Brisebois and Hill](https://blog.selfshadow.com/publications/blending-in-detail/).
Normals must be in the upper hemisphere. RGB residual adds to linear albedo;
roughness modulation adds luminance residual, clamped to [0,1]. Detail strength
uses a smoothstep distance fade. Equal/reversed bounds disable that distance fade.
At/beyond a valid fade end, base is exact. Explicit gradients scaled by tiling,
trilinear mipmaps and anisotropic filtering are required by the import profile.
