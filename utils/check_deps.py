import importlib

REQUIRED_DEPS = [
    ("sentence_transformers", "sentence-transformers"),
    ("faiss", "faiss-cpu"),
    ("pymilvus", "pymilvus")
]

def check_dependencies():
    missing = []
    for attr, pkg in REQUIRED_DEPS:
        try:
            importlib.import_module(attr)
        except ImportError:
            missing.append(pkg)
    return missing 