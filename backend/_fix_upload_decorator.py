from pathlib import Path
p = Path('backend/app/api/routes/videos.py')
lines = p.read_text(encoding='utf-8').splitlines()
if len(lines) > 16:
    lines[16] = '@router.post("/upload", response_model=VideoUploadResponse, status_code=status.HTTP_201_CREATED)'
p.write_text('\n'.join(lines), encoding='utf-8')
print('fixed')
