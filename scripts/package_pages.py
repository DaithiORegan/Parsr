"""Package freshly built Pages assets; reject a stale provider backend."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
BASE = Path(__file__).resolve().parents[1]
DIST = BASE / 'web' / 'pages-dist'
ZIP = BASE / 'downloads' / 'AI-JobParser-ATS-Screening-Tool-Cloudflare-Upload.zip'

def package():
    worker = (DIST / '_worker.js').read_text()
    required = ['generativelanguage.googleapis.com', 'GEMINI_API_KEY', 'gemini-3.5-flash-lite', 'responseJsonSchema']
    if not all(term in worker for term in required) or 'api.openai.com' in worker:
        raise ValueError('Pages backend is missing Gemini; run build:pages first.')
    for name in ['index.html', 'app.js', 'jobs.json', '_routes.json']:
        if not (DIST / name).is_file():
            raise ValueError(f'Missing built Pages asset: {name}')
    ZIP.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(ZIP, 'w', ZIP_DEFLATED) as archive:
        for path in sorted(DIST.rglob('*')):
            if path.is_file():
                archive.write(path, path.relative_to(DIST))
    with ZipFile(ZIP) as archive:
        if archive.testzip() is not None:
            raise ValueError('Pages ZIP failed integrity validation.')
    print(f'Verified Gemini Pages upload ZIP: {ZIP.name}')

if __name__ == '__main__':
    package()
