// components/ui/markdown-renderer.tsx
import { marked } from 'marked';
import DOMPurify from 'dompurify'; // npm install dompurify @types/dompurify

export function MarkdownRenderer({ content }: { content: string }) {
  // Важно! DOMPurify защищает от XSS-атак, очищая HTML.
  const sanitizedHtml = DOMPurify.sanitize(marked.parse(content));
  return <div dangerouslySetInnerHTML={{ __html: sanitizedHtml }} />;
}