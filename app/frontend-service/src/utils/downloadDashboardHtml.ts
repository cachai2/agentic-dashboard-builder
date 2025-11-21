const sanitizeFilename = (value: string) => value.replace(/[<>:"/\\|?*]+/g, '-').trim();

const ensureHtmlExtension = (value: string) => {
  const trimmed = value.trim();
  return trimmed.toLowerCase().endsWith('.html') ? trimmed : `${trimmed}.html`;
};

const parseContentDisposition = (headerValue: string | null): string | null => {
  if (!headerValue) {
    return null;
  }

  const starMatch = headerValue.match(/filename\*=(?:UTF-8''|)([^;]+)/i);
  if (starMatch && starMatch[1]) {
    try {
      return sanitizeFilename(decodeURIComponent(starMatch[1].replace(/^\s*"?|"?\s*$/g, '')));
    } catch {
      // Fall through to try the basic filename matcher.
    }
  }

  const filenameMatch = headerValue.match(/filename="?([^";]+)"?/i);
  if (filenameMatch && filenameMatch[1]) {
    return sanitizeFilename(filenameMatch[1]);
  }

  return null;
};

const triggerBrowserDownload = (blob: Blob, filename: string) => {
  const objectUrl = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = objectUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(objectUrl);
};

export const downloadDashboardHtml = async (url: string, options?: { suggestedName?: string }) => {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error('Unable to download dashboard HTML.');
  }

  const blob = await response.blob();
  const suggested = options?.suggestedName ? sanitizeFilename(options.suggestedName) : null;
  const headerName = parseContentDisposition(response.headers.get('Content-Disposition'));
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
  const fallbackName = ensureHtmlExtension(suggested ?? `dashboard-${timestamp}`);
  const filename = ensureHtmlExtension(headerName ?? fallbackName);

  triggerBrowserDownload(blob, filename);
};
