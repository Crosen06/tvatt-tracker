"""Write a tiny ONNX image classifier by hand (protobuf wire format), so tests need no onnx package."""
import struct
import numpy as np

def _varint(n):
    out = b""
    n &= (1 << 64) - 1
    while True:
        b = n & 0x7F; n >>= 7
        if n: out += bytes([b | 0x80])
        else: return out + bytes([b])

def _key(field, wire): return _varint(field << 3 | wire)
def f_int(field, v): return _key(field, 0) + _varint(v)
def f_bytes(field, b): return _key(field, 2) + _varint(len(b)) + b
def f_str(field, s): return f_bytes(field, s.encode())

def tensor(name, arr):
    arr = np.asarray(arr, np.float32)
    return b"".join(f_int(1, d) for d in arr.shape) + f_int(2, 1) + f_str(8, name) + f_bytes(9, arr.tobytes())

def value_info(name, shape):
    dims = b"".join(f_bytes(1, f_int(1, d)) for d in shape)
    ttype = f_int(1, 1) + f_bytes(2, dims)
    return f_str(1, name) + f_bytes(2, f_bytes(1, ttype))

def attr_int(name, v): return f_str(1, name) + f_int(3, v) + f_int(20, 2)
def attr_ints(name, vs): return f_str(1, name) + b"".join(f_int(8, v) for v in vs) + f_int(20, 7)

def node(op, inputs, outputs, name, attrs=()):
    return (b"".join(f_str(1, i) for i in inputs) + b"".join(f_str(2, o) for o in outputs) + f_str(3, name)
            + f_str(4, op) + b"".join(f_bytes(5, a) for a in attrs))

def tiny_classifier(path, seed=0, size=32, feat=4, classes=5):
    rng = np.random.default_rng(seed)
    nodes = [
        node("Conv", ["x", "w1", "b1"], ["c1"], "conv1", [attr_ints("kernel_shape", [3, 3]), attr_ints("pads", [1, 1, 1, 1]), attr_ints("strides", [2, 2])]),
        node("Relu", ["c1"], ["r1"], "relu1"),
        node("GlobalAveragePool", ["r1"], ["gap"], "pool"),
        node("Flatten", ["gap"], ["flat"], "flatten", [attr_int("axis", 1)]),
        node("Gemm", ["flat", "w2", "b2"], ["y"], "fc", [attr_int("transB", 1)]),
    ]
    inits = [tensor("w1", rng.normal(size=(feat, 3, 3, 3))), tensor("b1", rng.normal(size=feat)),
             tensor("w2", rng.normal(size=(classes, feat))), tensor("b2", rng.normal(size=classes))]
    graph = (b"".join(f_bytes(1, n) for n in nodes) + f_str(2, "tiny") + b"".join(f_bytes(5, t) for t in inits)
             + f_bytes(11, value_info("x", [1, 3, size, size])) + f_bytes(12, value_info("y", [1, classes])))
    model = f_int(1, 7) + f_str(2, "test") + f_bytes(7, graph) + f_bytes(8, f_str(1, "") + f_int(2, 13))
    with open(path, "wb") as fh:
        fh.write(model)
