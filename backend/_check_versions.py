modules = {
    "fastapi": "__version__",
    "uvicorn": "__version__",
    "sqlalchemy": "__version__",
    "pydantic": "__version__",
    "pydantic_settings": "__version__",
    "jose": "__version__",
    "mediapipe": "__version__",
    "cv2": "__version__",
    "numpy": "__version__",
    "pandas": "__version__",
    "cryptography": "__version__",
}

def main():
    for name, attr in modules.items():
        try:
            m = __import__(name)
            ver = getattr(m, attr, None)
            print(f"{name}={ver if ver is not None else 'UNKNOWN'}")
        except Exception as e:
            print(f"{name}=NOT_INSTALLED ({type(e).__name__}: {e})")

if __name__ == "__main__":
    main()
