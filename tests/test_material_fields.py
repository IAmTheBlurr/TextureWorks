"""Analytic semantics as well as parity for the material cluster fields."""

import importlib

import cupy as cp
import numpy as np
import pytest

from textureworks.cupy_ref import material_fields as ref
from textureworks.ptx import material_fields as ptx


@pytest.fixture(params=[ref, ptx], ids=["cupy", "ptx"])
def backend(request):
    return request.param


def gpu(a):
    return cp.asarray(a, dtype=cp.float32)


@pytest.mark.parametrize("shape", [(2,3),(17,31),(64,64)])
@pytest.mark.parametrize("boundary", ["clamp", "wrap"])
def test_parity(shape, boundary):
    rng = np.random.default_rng(413)
    h = gpu(rng.uniform(.1,.9,shape))
    color = gpu(rng.random((*shape,3)))
    calls = [
        ("generate_detail", (color,), dict(radius=7,boundary=boundary)),
        ("generate_surface_normal", (h,), dict(texel_size=(.003,.007),relief_depth=.035,boundary=boundary)),
        ("generate_curvature", (h,), dict(texel_size=(.003,.007),relief_depth=.035,curvature_range=30,boundary=boundary)),
        ("generate_wear", (h,), dict(seed=0xffffffff,threshold=.4,variation=1)),
        ("generate_layer_weight", (h,1-h,h), dict(coverage=.63,blend_width=.08,height_bias=1)),
    ]
    for name,args,kwargs in calls:
        a,b = getattr(ref,name)(*args,**kwargs),getattr(ptx,name)(*args,**kwargs)
        assert float(cp.max(cp.abs(a-b))) <= 1/255, name
        assert bool(cp.all(cp.isfinite(b) & (b >= 0) & (b <= 1))), name


@pytest.mark.parametrize("boundary", ["clamp","wrap"])
def test_flat_and_zero_depth(backend, boundary):
    h = cp.full((9,13),.4,cp.float32)
    np.testing.assert_allclose(cp.asnumpy(backend.generate_curvature(h,boundary=boundary)),.5,atol=1e-7)
    n = backend.generate_surface_normal(h,relief_depth=0,boundary=boundary)
    np.testing.assert_array_equal(cp.asnumpy(n), np.broadcast_to([.5,.5,1],n.shape))
    detail = backend.generate_detail(cp.repeat(h[:,:,None],3,axis=2),radius=64,boundary=boundary)
    np.testing.assert_allclose(cp.asnumpy(detail),.5,atol=2e-6)
    assert not bool(cp.any(backend.generate_wear(cp.full_like(h,.5))))


def test_bump_depression_and_independent_normal(backend):
    # Independent paraboloid: physical z = -.4*(x²+y²), K(origin)=.8 / meter.
    x,y = np.meshgrid(np.linspace(-.4,.4,41),np.linspace(-.3,.3,31))
    h = .8-.4*(x*x+y*y)
    k = cp.asnumpy(backend.generate_curvature(gpu(h),texel_size=(.02,.02),curvature_range=2))
    assert abs((2*k[15,20]-1)*2-.8) < 2e-3
    depression = cp.asnumpy(backend.generate_curvature(gpu(1-h),texel_size=(.02,.02),curvature_range=2))
    np.testing.assert_allclose(k+depression,1,atol=3e-4)
    normal = cp.asnumpy(backend.generate_surface_normal(gpu(h),texel_size=(.02,.02)))*2-1
    expected = np.stack((.8*x,-.8*y,np.ones_like(x)),axis=2)
    expected /= np.linalg.norm(expected,axis=2,keepdims=True)
    np.testing.assert_allclose(normal[1:-1,1:-1], expected[1:-1,1:-1],atol=3e-6)
    wear = cp.asnumpy(backend.generate_wear(gpu(k),edge_amount=1,cavity_amount=1,variation=0,threshold=0))
    assert wear[15,20,0] > .39 and wear[15,20,1] == 0
    wear_d = cp.asnumpy(backend.generate_wear(gpu(depression),variation=0,threshold=0))
    assert wear_d[15,20,0] == 0 and wear_d[15,20,1] > .19


def test_ramp_is_not_an_exposed_edge(backend):
    x,y = np.meshgrid(np.arange(27,dtype=np.float32),np.arange(15,dtype=np.float32))
    h = gpu(.15+x*.007+y*.011)
    curvature = backend.generate_curvature(h)
    np.testing.assert_allclose(cp.asnumpy(curvature[1:-1,1:-1]),.5,atol=1e-7)
    assert float(cp.max(backend.generate_wear(curvature)[1:-1,1:-1])) == 0
    n = cp.asnumpy(backend.generate_surface_normal(h,texel_size=(.02,.05),relief_depth=.1))[7,13]*2-1
    expected = np.array([-.035,.022,1]); expected /= np.linalg.norm(expected)
    np.testing.assert_allclose(n,expected,atol=3e-7)


def test_frequency_response_and_boundaries(backend):
    w = 65
    x = np.arange(w)
    source = .5+.2*np.cos(2*np.pi*x/w)+.1*np.cos(2*np.pi*16*x/w)
    color = gpu(np.broadcast_to(source[None,:,None],(7,w,3)).copy())
    residual = cp.asnumpy(backend.generate_detail(color,6,"wrap"))[3,:,0]*2-1
    spectrum = abs(np.fft.rfft(residual))
    assert spectrum[16] > 15*spectrum[1]
    assert abs(residual.mean()) < 1e-6
    # Independent double-precision periodic Gaussian at one pixel.
    taps = np.arange(-6,7); weights = np.exp(-taps*taps/8); weights /= weights.sum()
    expected = source[0]-np.dot(weights,source[taps%w])
    assert abs(residual[0]-expected) < 1e-6
    impulse = cp.zeros((3,5,3),cp.float32); impulse[:,0] = 1
    a,b = backend.generate_detail(impulse,4,"wrap"),backend.generate_detail(impulse,4,"clamp")
    assert float(cp.max(cp.abs(a-b))) > .01


def test_wear_controls_authored_masks_seed(backend):
    h = cp.full((7,11),.5,cp.float32)
    ones = cp.ones_like(h)
    args = dict(edge_mask=ones,cavity_mask=ones,edge_amount=.8,cavity_amount=.2,variation=1,seed=42)
    first = backend.generate_wear(h,**args)
    np.testing.assert_array_equal(cp.asnumpy(first),cp.asnumpy(backend.generate_wear(h,**args)))
    np.testing.assert_allclose(cp.asnumpy(first[:,:,0]),cp.asnumpy(first[:,:,1])*4,atol=1e-7)
    assert not bool(cp.all(first == backend.generate_wear(h,**{**args,"seed":43})))
    assert not bool(cp.any(backend.generate_wear(h,edge_amount=0,cavity_amount=0,edge_mask=ones,cavity_mask=ones)))
    # Independent integer hash, including unsigned wraparound.
    hashed = 42
    for shift,mul in ((16,0x7feb352d),(15,0x846ca68b)):
        hashed = ((hashed ^ (hashed >> shift))*mul)&0xffffffff
    hashed ^= hashed >> 16
    assert abs(float(first[0,0,0])-.8*(hashed&0xffffff)/16777215) < 1e-7


@pytest.mark.parametrize("width", [0, .0001,.2,1])
def test_layer_endpoints_and_formula(backend, width):
    a = gpu(np.linspace(0,1,77).reshape(7,11)); b = 1-a
    for coverage,target in ((0,0),(1,1)):
        out = backend.generate_layer_weight(a,b,a,coverage,width,1)
        assert bool(cp.all(out == target))
    for mask,target in ((cp.zeros_like(a),0),(cp.ones_like(a),1)):
        assert bool(cp.all(backend.generate_layer_weight(a,b,mask,.5,width,1) == target))
    if width == 0:
        out = backend.generate_layer_weight(a,a,cp.full_like(a,.5),.5,0)
        assert bool(cp.all(out == 1))
    else:
        m = cp.asnumpy(a); score = m+(cp.asnumpy(b)-cp.asnumpy(a))*m*(1-m)
        t = np.clip((score-(.5-width/2))/width,0,1); expected=t*t*(3-2*t)
        np.testing.assert_allclose(cp.asnumpy(backend.generate_layer_weight(a,b,a,.5,width,1)),expected,atol=2e-6)


def test_composed_height_geometric_orientation(backend):
    # Constant materials with a spatial mask create a slope entirely from dt/dx.
    mask = gpu(np.broadcast_to(np.linspace(.3,.7,81),(13,81)).copy())
    a,b = cp.full_like(mask,.2),cp.full_like(mask,.8)
    t = backend.generate_layer_weight(a,b,mask,.5,1,0)
    height = a+(b-a)*t
    n = cp.asnumpy(backend.generate_surface_normal(height,texel_size=(.01,.01),relief_depth=.04))*2-1
    # At m=.5 smoothstep derivative is 1.5, dm/dx=.5/m.
    slope = .6*1.5*.5*.04
    expected = np.array([-slope,0,1]); expected /= np.linalg.norm(expected)
    np.testing.assert_allclose(n[6,40],expected,atol=2e-6)


@pytest.mark.parametrize("kwargs", [dict(radius=0),dict(radius=1.5),dict(boundary="mirror")])
def test_invalid_detail_parameters(backend,kwargs):
    with pytest.raises(ValueError): backend.generate_detail(cp.zeros((7,9,3),cp.float32),**kwargs)


def test_invalid_fields_and_controls(backend):
    h = cp.ones((7,9),cp.float32)
    for bad in (h.astype(cp.float64),cp.zeros((1,9),cp.float32),h*float("nan"),h*2):
        with pytest.raises(ValueError): backend.generate_curvature(bad)
    for kwargs in (dict(texel_size=(0,1)),dict(relief_depth=-1),dict(curvature_range=0)):
        with pytest.raises(ValueError): backend.generate_curvature(h,**kwargs)
    with pytest.raises(ValueError): backend.generate_wear(h,seed=-1)
    with pytest.raises(ValueError): backend.generate_wear(h,threshold=1)
    with pytest.raises(ValueError): backend.generate_wear(h,edge_mask=cp.ones((3,4),cp.float32))
    with pytest.raises(ValueError): backend.generate_layer_weight(h,h,h,blend_width=-.1)
    with pytest.raises(ValueError): backend.generate_layer_weight(h,h,h,coverage=float("nan"))


def test_signatures_match():
    import inspect
    for name in ("generate_detail","generate_surface_normal","generate_curvature","generate_wear","generate_layer_weight"):
        assert inspect.signature(getattr(ref,name)) == inspect.signature(getattr(ptx,name))


def test_physical_parameter_extrema_remain_finite(backend):
    h = gpu([[0,1,0],[1,0,1]])
    for spacing,depth,limit in (((1e-6,1e-6),100,1e-6),((1e6,1e6),0,1e6)):
        normal = backend.generate_surface_normal(h,spacing,depth,"wrap")
        curvature = backend.generate_curvature(h,spacing,depth,limit,"wrap")
        assert bool(cp.all(cp.isfinite(normal))) and bool(cp.all(cp.isfinite(curvature)))
        masks = backend.generate_wear(curvature,1,1,.999,1,0xffffffff)
        assert bool(cp.all(cp.isfinite(masks) & (masks >= 0) & (masks <= 1)))
