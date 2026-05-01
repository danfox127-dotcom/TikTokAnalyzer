# Download Export Button Design

## Goal

Add an inline "Download for LLM →" button to the results views that calls `POST /api/export/llm` with the original uploaded file and triggers a browser download of the privacy-safe JSON.

## Architecture

The `File` object is captured in `page.tsx` state at upload time and passed down as an optional prop to both results views. A new `DownloadExportButton` component handles the fetch and download mechanics independently.

## Components

### `page.tsx` changes
- Add `const [uploadedFile, setUploadedFile] = useState<File | null>(null)`
- In `handleFile`, store `setUploadedFile(file)` before calling `analyze(file)`
- In `handleReset`, add `setUploadedFile(null)`
- Pass `sourceFile={uploadedFile ?? undefined}` to both `TheGlassHouse` and `GhostProfileHUD`

### New: `algorithmic-mirror/app/components/DownloadExportButton.tsx`
- Props: `{ file: File; apiUrl: string }`
- Internal state: `"idle" | "loading" | "error"`
- On click:
  1. POST `file` as `FormData` to `${apiUrl}/api/export/llm`
  2. On success: `blob = await res.blob()`, create object URL, programmatically click a hidden `<a download>`, revoke URL
  3. On error: show inline error message for 3 seconds, return to idle
- Disabled during loading; spinner replaces arrow during loading
- Styling: matches existing dark surveillance aesthetic (same ghost/dim button style as secondary actions)

### `TheGlassHouse.tsx` changes
- Add `sourceFile?: File` to `Props` interface
- Render `<DownloadExportButton>` inline near the reset button in the top nav area (~line 403)

### `GhostProfileHUD.tsx` changes
- Add `sourceFile?: File` to `Props` interface
- Render `<DownloadExportButton>` inline near the reset button in the header (~line 706)

## Data Flow

```
user uploads file
  → handleFile stores File in uploadedFile state
  → analyze(file) POSTs to /api/analyze → profile rendered
  → DownloadExportButton receives File as prop
  → user clicks → POSTs same File to /api/export/llm
  → browser downloads tiktok_analysis_YYYY-MM-DD.json
```

## Error Handling

- Network/parse errors: show "Export failed" inline for 3s, return to idle
- Button is not rendered if `sourceFile` is undefined (natural after reset)

## Testing

- Unit test `DownloadExportButton`: mock fetch, verify blob download triggered
- Integration: existing `tests/test_llm_export.py` covers the backend endpoint

## Out of Scope

- Combining the export into the initial `/api/analyze` call
- Caching the export result
- Any changes to the export endpoint itself
